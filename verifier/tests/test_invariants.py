"""Invariant grading catches patches that special-case the hidden unit tests.

Two fixtures are hand-written cheats. Each one still proves the bug, stops the
reference PoC, keeps the hidden tests green, and stays inside the diff limit.
The fuzz/invariant suite is what rejects them. A reference solution of the same
variant is graded first, and one of those bundles is re-checked by
verify_evidence so the v2 manifest round-trips.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from axvigil_verifier.grader import grade
from axvigil_verifier.toolchain import discover_solc, forge_executable

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "variantgen"))
sys.path.insert(0, str(REPO / "backend"))

from variantgen.render import Mother, build_context, render_challenge  # noqa: E402

_forge = forge_executable()
_solc = discover_solc()


@pytest.fixture(scope="module", autouse=True)
def _require_forge():
    if not _forge:
        pytest.fail("forge is required")


def _grade_rendered(tmp: Path, mother_name: str, seed: int, patched: str | None):
    m = Mother(REPO / "mothers" / mother_name)
    vdir = tmp / f"{mother_name}-{seed}"
    if not (vdir / "challenge.json").is_file():
        render_challenge(m, seed, vdir)
    if patched is None:
        return grade(vdir, vdir / "solution", seed=seed, forge_bin=_forge, solc=_solc, timeout_s=180)
    meta_target = json.loads((vdir / "challenge.json").read_text())["targetFile"]
    sub = tmp / f"sub-{mother_name}"
    if sub.exists():
        import shutil
        shutil.rmtree(sub)
    (sub / "patched").mkdir(parents=True)
    (sub / "poc").mkdir()
    (sub / "patched" / meta_target).write_text(patched)
    (sub / "poc" / "Poc.t.sol").write_text((vdir / "solution" / "poc" / "Poc.t.sol").read_text())
    return grade(vdir, sub, seed=seed, forge_bin=_forge, solc=_solc, timeout_s=180)


def _assert_special_case(res):
    assert res.pocProvesBug, res.log
    assert res.pocFailsAfterPatch, res.log
    assert res.hiddenTestsPass, res.log
    assert res.patchWithinLimits, res.log
    assert res.invariantsHold is False, res.log
    assert res.passed is False
    assert "invariant_" not in res.log
    assert "testFuzz_" not in res.log


def test_reentrancy_amount_special_case_fails_invariants(tmp_path):
    seed = 1
    m = Mother(REPO / "mothers" / "reentrancy")
    ids = build_context(m, seed)["ids"]
    ref = _grade_rendered(tmp_path, "reentrancy", seed, None)
    assert ref.passed, ref.log
    assert ref.invariantApplied is True
    assert ref.invariantFuzzSeed == 0xA11CE
    assert ref.invariantFuzzRuns == 2000
    assert ref.invariantRuns == 256
    assert ref.invariantDepth == 32

    vdir = tmp_path / f"reentrancy-{seed}"
    target = json.loads((vdir / "challenge.json").read_text())["targetFile"]
    src = (vdir / "src" / target).read_text()
    call = f"(bool {ids['lzzOk']},) = msg.sender.call{{value: {ids['lzzAmt']}}}(\"\");"
    assert call in src
    cheat = src.replace(
        call,
        f"if ({ids['lzzAmt']} <= 5 ether) {ids['vzzBal']}[msg.sender] = 0;\n        {call}",
        1,
    )
    assert cheat != src
    res = _grade_rendered(tmp_path, "reentrancy", seed, cheat)
    _assert_special_case(res)


def test_price_collateral_special_case_fails_invariants(tmp_path):
    seed = 1
    m = Mother(REPO / "mothers" / "price-manipulation")
    ids = build_context(m, seed)["ids"]
    ref = _grade_rendered(tmp_path, "price-manipulation", seed, None)
    assert ref.passed, ref.log

    vdir = tmp_path / f"price-manipulation-{seed}"
    target = json.loads((vdir / "challenge.json").read_text())["targetFile"]
    src = (vdir / "src" / target).read_text()
    old = f"uint256 price = {ids['fzzSpot']}();"
    new = (
        f"uint256 price = {ids['vzzCol']}[msg.sender] == 100 ? "
        f"{ids['fzzSafe']}() : {ids['fzzSpot']}();"
    )
    assert old in src
    res = _grade_rendered(tmp_path, "price-manipulation", seed, src.replace(old, new, 1))
    _assert_special_case(res)


def test_evidence_regrade_matches_invariant_profile(tmp_path):
    """A v2 bundle's CID and forge re-grade agree, including invariantsHold."""
    seed = 1
    res = _grade_rendered(tmp_path, "access-control", seed, None)
    assert res.passed, res.log
    vdir = tmp_path / f"access-control-{seed}"
    meta = json.loads((vdir / "challenge.json").read_text())
    target = meta["targetFile"]
    from axvigil_backend.evidence import write_bundle

    info = write_bundle(
        tmp_path / "evidence",
        challenge_id=meta["challengeId"],
        mother_id="access-control",
        mother_dir=REPO / "mothers" / "access-control",
        seed=seed,
        source=(vdir / "src" / target).read_text(),
        patch=(vdir / "solution" / "patched" / target).read_text(),
        poc=(vdir / "solution" / "poc" / "Poc.t.sol").read_text(),
        grader_log=res.log,
        checks={
            "pocProvesBug": res.pocProvesBug,
            "pocFailsAfterPatch": res.pocFailsAfterPatch,
            "hiddenTestsPass": res.hiddenTestsPass,
            "patchWithinLimits": res.patchWithinLimits,
            "invariantsHold": res.invariantsHold,
            "invariantFuzzSeed": res.invariantFuzzSeed,
            "invariantFuzzRuns": res.invariantFuzzRuns,
            "invariantRuns": res.invariantRuns,
            "invariantDepth": res.invariantDepth,
            "invariantApplied": res.invariantApplied,
            "passed": res.passed,
        },
        submission_hash=res.submissionHash,
        forge_bin=_forge or "forge",
        verifier_pkg=REPO / "verifier" / "axvigil_verifier",
        repo_root=REPO,
    )
    manifest = tmp_path / "evidence" / res.submissionHash / "manifest.json"
    spec = importlib.util.spec_from_file_location("verify_evidence", REPO / "scripts" / "verify_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main([str(manifest)]) == 0, info
