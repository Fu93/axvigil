"""Evidence CID, submission hash, deal-time checks, and tier replay."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "verifier"))
sys.path.insert(0, str(REPO / "variantgen"))

from axvigil_backend.config import Settings
from axvigil_backend.evidence import (
    bundle_grade_matches,
    canonical_json,
    cid_v1_raw_sha256,
    recompute_submission_hash,
    seed_commitment,
    write_bundle,
)
from axvigil_backend.protocol import Platform, ProtocolError
from axvigil_backend.rarity_replay import draw_tier, hidden_roll_hits, replay, weight_multiplier
from axvigil_backend.registry import MemoryRegistry
from axvigil_backend.store import Store


def test_repo_commit_marks_a_dirty_worktree(tmp_path):
    import subprocess
    from axvigil_backend.evidence import repo_commit
    subprocess.check_call(["git", "init"], cwd=tmp_path, stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "config", "user.email", "t@example.com"], cwd=tmp_path)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=tmp_path)
    (tmp_path / "a.txt").write_text("a\n")
    subprocess.check_call(["git", "add", "a.txt"], cwd=tmp_path)
    subprocess.check_call(["git", "commit", "-m", "a"], cwd=tmp_path, stdout=subprocess.DEVNULL)
    clean = repo_commit(tmp_path)
    assert clean and not clean.endswith("-dirty")
    (tmp_path / "a.txt").write_text("b\n")
    assert repo_commit(tmp_path).endswith("-dirty")


def test_cid_is_deterministic_and_raw_sha256():
    body = canonical_json({"b": 1, "a": "x"})
    assert body == b'{"a":"x","b":1}\n'
    cid = cid_v1_raw_sha256(body)
    assert cid == cid_v1_raw_sha256(body)
    assert cid.startswith("bafkrei")
    assert cid == cid.lower()


def test_bundle_submission_hash_and_seed_commitment(tmp_path):
    mother = REPO / "mothers" / "reentrancy"
    info = write_bundle(
        tmp_path,
        challenge_id="reentrancy-7",
        mother_id="reentrancy",
        mother_dir=mother,
        seed=7,
        source="contract V {}\n",
        patch="contract V { function f() external {} }\n",
        poc="contract T {}\n",
        grader_log="hiddenTestsPass: 1/1 tests passed",
        checks={"pocProvesBug": True, "pocFailsAfterPatch": True, "hiddenTestsPass": True,
                "patchWithinLimits": True, "invariantsHold": True, "passed": True,
                "invariantFuzzSeed": 659918, "invariantFuzzRuns": 2000,
                "invariantRuns": 256, "invariantDepth": 32, "invariantApplied": True},
        submission_hash="0x" + "11" * 32,
        forge_bin="forge",
        verifier_pkg=REPO / "verifier" / "axvigil_verifier",
        repo_root=REPO,
    )
    manifest = json.loads((tmp_path / info["evidenceCid"] and tmp_path.joinpath(
        "0x" + "11" * 32, "manifest.json")).read_text())
    # The hash stored above is a placeholder. Recompute must differ, and the
    # commitment must match the seed that is inside the bundle.
    assert manifest["seed"] == 7
    assert manifest["seedCommitment"] == seed_commitment(7)
    assert recompute_submission_hash(manifest) != manifest["submissionHash"]
    manifest["submissionHash"] = recompute_submission_hash(manifest)
    assert recompute_submission_hash(manifest) == manifest["submissionHash"]
    assert info["evidenceCid"].startswith("bafkrei")
    assert info["seedCommitment"] == seed_commitment(7)
    assert manifest["bundleVersion"] == 2
    assert manifest["checks"]["invariantsHold"] is True
    assert manifest["invariantProfile"] == {
        "fuzzSeed": 659918, "fuzzRuns": 2000, "invariantRuns": 256,
        "invariantDepth": 32, "applied": True,
    }


def test_v1_bundle_skips_the_invariant_check():
    checks = {"passed": True, "pocProvesBug": True, "pocFailsAfterPatch": True,
              "hiddenTestsPass": True, "patchWithinLimits": True}
    manifest = {"bundleVersion": 1, "checks": checks}
    grade = dict(checks, invariantsHold=False, invariantProfile={
        "fuzzSeed": 1, "fuzzRuns": 1, "invariantRuns": 1, "invariantDepth": 1, "applied": True,
    })
    rows = bundle_grade_matches(manifest, grade)
    assert "invariantsHold" not in {key for key, _ in rows}
    assert all(ok for _, ok in rows)


def test_v2_bundle_requires_the_invariant_schedule():
    profile = {"fuzzSeed": 659918, "fuzzRuns": 2000, "invariantRuns": 256,
               "invariantDepth": 32, "applied": True}
    checks = {"passed": True, "pocProvesBug": True, "pocFailsAfterPatch": True,
              "hiddenTestsPass": True, "patchWithinLimits": True, "invariantsHold": True}
    manifest = {"bundleVersion": 2, "checks": checks, "invariantProfile": profile}
    assert all(ok for _, ok in bundle_grade_matches(manifest, {"invariantProfile": profile, **checks}))
    drifted = dict(profile, fuzzSeed=1)
    rows = bundle_grade_matches(manifest, {"invariantProfile": drifted, **checks})
    assert ("invariantProfile.fuzzSeed", False) in rows


def test_weight_and_hidden_roll_match_the_contract():
    assert weight_multiplier(0, 3) == 1
    assert weight_multiplier(1, 1) == 2
    assert weight_multiplier(1, 3) == 8
    assert weight_multiplier(2, 3) == 16
    assert weight_multiplier(2, 4) == 0
    assert hidden_roll_hits(24, 2) is True
    assert hidden_roll_hits(25, 2) is False
    assert hidden_roll_hits(24, 0) is False
    drawn = [0, 0, 0, 0, 0]
    ok, tier = draw_tier(0, 2, 24, drawn)
    assert ok and tier == 4 and drawn[4] == 1


def test_replay_assigns_art_id_in_order():
    rows = replay([
        {"id": 1, "pool": 0, "vulnClass": 2, "rand": 0},
        {"id": 2, "pool": 0, "vulnClass": 2, "rand": 0},
    ])
    assert rows[0]["artId"] == 20000
    assert rows[1]["artId"] == 20001
    assert rows[0]["tier"] == 0


def _platform(tmp_path, *, reference_check: bool) -> Platform:
    settings = Settings(
        signer_key=None, chain_id=97, verifying_contract=None,
        challenges_dir=REPO / "challenges",
        verifier_dir=REPO / "verifier",
        variantgen_dir=REPO / "variantgen",
        mothers_dir=REPO / "mothers",
        challenge_cache_dir=tmp_path / "cache",
        db_path=":memory:",
        session_secret="s",
        forge_bin="forge",
        solc_bin=None,
        grade_timeout_s=30,
        auth_ttl_s=60,
        session_ttl_s=60,
        start_rate_per_min=100,
        submit_rate_per_min=100,
        reference_check=reference_check,
        dev_skip_ownership=True,
    )
    reg = MemoryRegistry()
    reg.set_owner(1, "0x00000000000000000000000000000000000000aA")
    return Platform(settings, Store(":memory:"), None, registry=reg)


def test_deal_skips_a_fingerprint_it_already_issued(tmp_path, monkeypatch):
    from variantgen.fingerprint import fingerprint
    from variantgen.render import build_context, render_src

    platform = _platform(tmp_path, reference_check=False)
    mother = platform.mothers["reentrancy"]
    base = fingerprint(render_src(mother, build_context(mother, 3)))
    other = next(
        s for s in range(4, 80)
        if fingerprint(render_src(mother, build_context(mother, s))) != base
    )
    platform._fingerprints[mother.mother_id] = {base}
    seeds = iter([3, other])
    monkeypatch.setattr("axvigil_backend.protocol.secrets.randbelow", lambda _n: next(seeds))
    seed, _out, _meta, _src = platform._deal(mother)
    assert seed == other


def test_reference_check_resamples_until_the_reference_passes(tmp_path, monkeypatch):
    platform = _platform(tmp_path, reference_check=True)
    mother = platform.mothers["access-control"]
    seeds = iter([1, 2])
    monkeypatch.setattr("axvigil_backend.protocol.secrets.randbelow", lambda _n: next(seeds))
    answers = iter([False, True])
    monkeypatch.setattr(platform, "_reference_ok", lambda *_a, **_k: next(answers))
    seed, _out, _meta, _src = platform._deal(mother)
    assert seed == 2


def test_reference_check_failure_is_a_protocol_error(tmp_path, monkeypatch):
    platform = _platform(tmp_path, reference_check=True)
    mother = platform.mothers["reentrancy"]
    monkeypatch.setattr("axvigil_backend.protocol.secrets.randbelow", lambda _n: 1)
    monkeypatch.setattr(platform, "_reference_ok", lambda *_a, **_k: False)
    with pytest.raises(ProtocolError) as raised:
        platform._deal(mother)
    assert raised.value.status == 503
