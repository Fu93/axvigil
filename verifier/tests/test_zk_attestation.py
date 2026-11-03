"""Unit tests for zkVM capability attestation bundle generator."""

from __future__ import annotations

import json
from axvigil_verifier.zk_attestation import (
    compute_checks_bitmap,
    generate_zk_attestation_bundle,
)


def test_compute_checks_bitmap():
    assert compute_checks_bitmap(True, True, True, True, True) == 31
    assert compute_checks_bitmap(True, True, True, True, False) == 15
    assert compute_checks_bitmap(True, False, False, False, False) == 1
    assert compute_checks_bitmap(False, False, False, False, False) == 0


def test_generate_zk_attestation_bundle_passing():
    bundle = generate_zk_attestation_bundle(
        agent_id=101,
        challenge_id="0x" + "11" * 32,
        original_code="contract Vault { ... }",
        patched_code="contract Vault { bool locked; ... }",
        poc_proves_bug=True,
        poc_fails_after_patch=True,
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=True,
        timestamp=1700000000,
    )
    assert bundle.agentId == 101
    assert bundle.passed is True
    assert bundle.checksBitmap == 31
    assert bundle.patchCommitment.startswith("0x")
    assert bundle.originalCodeHash.startswith("0x")
    assert bundle.proofBytes.startswith("0x")

    # JSON round-trip
    data = json.loads(bundle.to_json())
    assert data["agentId"] == 101
    assert data["checksBitmap"] == 31
    assert data["passed"] is True


def test_generate_zk_attestation_bundle_failing():
    bundle = generate_zk_attestation_bundle(
        agent_id=101,
        challenge_id="0x" + "11" * 32,
        original_code="contract Vault { ... }",
        patched_code="contract Vault { ... }",
        poc_proves_bug=True,
        poc_fails_after_patch=False,  # Failed to neutralize PoC!
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=True,
        timestamp=1700000000,
    )
    assert bundle.passed is False
    assert bundle.checksBitmap == 29  # 31 - 2
