"""Variant generator tests.

The fast tests (no forge) check determinism, uniqueness and that the reference
fix is a small, interface-preserving diff. The forge test grades a couple of
rendered variants per mother end-to-end and fails if forge is not installed.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from variantgen.fingerprint import fingerprint
from variantgen.render import Mother, build_context, render_src, render_challenge
from variantgen.__main__ import _unique_variants

REPO_ROOT = Path(__file__).resolve().parents[2]
MOTHERS = [p for p in sorted((REPO_ROOT / "mothers").iterdir()) if (p / "mother.json").is_file()]

import sys
sys.path.insert(0, str(REPO_ROOT / "verifier"))
from axvigil_verifier.toolchain import discover_solc, forge_executable  # noqa: E402

_forge = forge_executable()
_solc = discover_solc()


REAL_INCIDENT = {
    "bridge-phantom-deposit",
    "empty-market-inflation",
    "platypus-emergency-withdraw",
    "nomad-unproven-message",
    "beanstalk-flash-governance",
}


def test_identifier_assignments_do_not_collide():
    for mdir in MOTHERS:
        m = Mother(mdir)
        for seed in range(30):
            vals = list(build_context(m, seed)["ids"].values())
            assert len(vals) == len(set(vals)), f"{m.mother_id} seed {seed} reused a name"


def test_real_incident_mothers_cite_checked_sources():
    import json
    for mdir in MOTHERS:
        meta = json.loads((mdir / "mother.json").read_text())
        if mdir.name not in REAL_INCIDENT:
            assert meta.get("track", "synthetic") == "synthetic"
            continue
        assert meta["track"] == "real-incident"
        incident = meta["realWorld"]
        assert incident["incident"] and incident["lossReported"] and incident["sources"]
        assert all(src.startswith("https://") for src in incident["sources"])
        assert (mdir / "invariant.t.sol.tmpl").is_file()


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_render_is_deterministic(mdir):
    m = Mother(mdir)
    a = render_src(m, build_context(m, 123))
    b = render_src(m, build_context(m, 123))
    assert a == b, "same seed must render identically"


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_twenty_unique_variants(mdir):
    m = Mother(mdir)
    fps = [fp for _seed, fp in _unique_variants(m, 20)]
    assert len(fps) == 20
    assert len(set(fps)) == 20, "fingerprints must be distinct"


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_reference_fix_is_small_and_preserves_interface(mdir, tmp_path):
    m = Mother(mdir)
    ch = render_challenge(m, 5, tmp_path)
    target = ch["targetFile"]
    src = (tmp_path / "src" / target).read_text()
    patched = (tmp_path / "solution" / "patched" / target).read_text()

    assert src != patched, "the fix must change something"
    # interface preserved: contract + required functions still present
    assert re.search(rf"\bcontract\s+{re.escape(ch['contractName'])}\b", patched)
    for fn in ch["requiredFunctions"]:
        assert re.search(rf"\bfunction\s+{re.escape(fn)}\b", patched), f"{fn} removed by fix"

    # changed lines within the mother's declared limit
    import difflib
    changed = sum(
        1 for ln in difflib.unified_diff(src.splitlines(), patched.splitlines(), lineterm="", n=0)
        if (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---"))
    )
    assert changed <= ch["limits"]["maxChangedLines"], f"fix too large: {changed} lines"


def test_identifiers_are_renamed_across_seeds(tmp_path):
    # Different seeds should choose different contract names, proving renaming varies.
    m = Mother(MOTHERS[0])
    names = {render_challenge(m, s, tmp_path / f"s{s}")["contractName"] for s in range(8)}
    assert len(names) >= 3, "contract name should vary across seeds"


def test_access_control_hidden_test_accepts_a_role_named_revert(tmp_path):
    """The hidden test must not demand the literal "not owner".

    Seed rendering renames the role (manager, governor, ...). That word is not
    in the vulnerable source, so a correct `require(msg.sender == manager)`
    that reverts with "not manager" has to pass, and the unpatched sweep must
    still fail.
    """
    if not _forge:
        pytest.fail("forge is required. Install foundry; solc is discovered from svm if needed.")
    import sys
    sys.path.insert(0, str(REPO_ROOT / "verifier"))
    from axvigil_verifier.grader import grade

    m = Mother(REPO_ROOT / "mothers" / "access-control")
    seed = ctx = None
    for s in range(40):
        c = build_context(m, s)
        if c["ids"]["vzzOwner"] != "owner":
            seed, ctx = s, c
            break
    assert seed is not None and ctx is not None
    role = ctx["ids"]["vzzOwner"]
    vdir = tmp_path / "ac"
    render_challenge(m, seed, vdir)
    contract = ctx["contract"]
    src_path = vdir / "src" / f"{contract}.sol"
    src = src_path.read_text()
    assert "not owner" not in src
    assert role in src

    ref = (vdir / "solution" / "patched" / f"{contract}.sol").read_text()
    role_patch = ref.replace('"not owner"', f'"not {role}"', 1)
    assert role_patch != ref
    poc = (vdir / "solution" / "poc" / "Poc.t.sol").read_text()

    def _grade(patched: str):
        sub = tmp_path / "sub"
        if sub.exists():
            shutil.rmtree(sub)
        (sub / "patched").mkdir(parents=True)
        (sub / "poc").mkdir()
        (sub / "patched" / f"{contract}.sol").write_text(patched)
        (sub / "poc" / "Poc.t.sol").write_text(poc)
        return grade(vdir, sub, seed=seed, forge_bin=_forge, solc=_solc, timeout_s=120)

    ok = _grade(role_patch)
    assert ok.passed, ok.log

    bare = _grade(src)
    assert bare.hiddenTestsPass is False, bare.log
    assert bare.passed is False

    # A patch that reverts for everyone, including the owner, is not a fix.
    blocked = role_patch.replace(
        f'require(msg.sender == {role}, "not {role}");',
        'require(false, "closed");',
        1,
    )
    assert blocked != role_patch
    everyone = _grade(blocked)
    assert everyone.hiddenTestsPass is False, everyone.log


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_rendered_variants_grade_as_solved(mdir, tmp_path):
    if not _forge:
        pytest.fail("forge is required. Install foundry; solc is discovered from svm if needed.")
    import sys
    sys.path.insert(0, str(REPO_ROOT / "verifier"))
    from axvigil_verifier.grader import grade

    m = Mother(mdir)
    seeds = [s for s, _ in _unique_variants(m, 2)]
    for seed in seeds:
        vdir = tmp_path / f"{m.mother_id}-{seed}"
        render_challenge(m, seed, vdir)
        res = grade(vdir, vdir / "solution", seed=seed, forge_bin=_forge, solc=_solc, timeout_s=120)
        assert res.passed, f"{m.mother_id} seed {seed}: {res.log}"
