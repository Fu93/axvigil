"""Threshold signatures: a validator signs only its own passing grade."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "verifier"))

from axvigil_backend.evidence import recompute_submission_hash
from axvigil_backend.validators import GradeRefused, LocalValidator, collect_signatures

# Public Anvil keys. Not used on a network with real funds.
KEYS = [
    "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
    "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
]
CONTRACT = "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a"


def _manifest() -> dict:
    manifest = {
        "challengeId": "reentrancy-1",
        "seed": 1,
        "patch": "contract V {}\n",
        "poc": "contract T {}\n",
        "submissionHash": "0x" + "00" * 32,
    }
    manifest["submissionHash"] = recompute_submission_hash(manifest)
    return manifest


def _auth(manifest: dict) -> dict:
    return {
        "agentId": 1,
        "to": "0x00000000000000000000000000000000000000aA",
        "vulnClass": 0,
        "difficulty": 0,
        "pool": 0,
        "submissionHash": manifest["submissionHash"],
        "nonce": 7,
        "deadline": 4_000_000_000,
    }


def _validators() -> list[LocalValidator]:
    return [LocalValidator(key, 97, CONTRACT) for key in KEYS]


def test_validator_refuses_a_failing_grade():
    manifest = _manifest()
    with pytest.raises(GradeRefused):
        _validators()[0].consider(manifest, _auth(manifest), lambda _m: {"passed": False})


def test_validator_refuses_a_hash_mismatch():
    manifest = _manifest()
    manifest["submissionHash"] = "0x" + "11" * 32
    with pytest.raises(GradeRefused):
        _validators()[0].consider(manifest, _auth(manifest), lambda _m: {"passed": True})


def test_coordinator_collects_two_of_three_and_skips_a_refusal():
    manifest = _manifest()
    auth = _auth(manifest)
    calls = {"n": 0}

    def grade(_m):
        calls["n"] += 1
        return {"passed": calls["n"] != 1}

    sigs = collect_signatures(_validators(), manifest, auth, 2, grade)
    assert len(sigs) == 2
    assert len({row["signer"] for row in sigs}) == 2
    assert all(row["signature"].startswith("0x") for row in sigs)
    # Same digest: they signed one MintAuth.
    assert sigs[0]["digest"] == sigs[1]["digest"]


def test_coordinator_fails_closed_when_only_one_agrees():
    manifest = _manifest()
    with pytest.raises(GradeRefused):
        collect_signatures(_validators(), manifest, _auth(manifest), 2, lambda _m: {"passed": False})
