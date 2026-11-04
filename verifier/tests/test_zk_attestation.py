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
        vuln_class=1,
        difficulty=2,
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
    assert bundle.vulnClass == 1
    assert bundle.difficulty == 2
    assert bundle.patchCommitment.startswith("0x")
    assert bundle.originalCodeHash.startswith("0x")
    assert bundle.proofBytes.startswith("0x")

    # ABI encoded public values length: 9 fields * 32 bytes = 288 bytes
    raw_pv = bundle.encode_public_values()
    assert len(raw_pv) == 288

    # JSON round-trip
    data = json.loads(bundle.to_json())
    assert data["agentId"] == 101
    assert data["checksBitmap"] == 31
    assert data["passed"] is True
    assert data["vulnClass"] == 1
    assert data["difficulty"] == 2


def test_generate_zk_attestation_bundle_failing():
    bundle = generate_zk_attestation_bundle(
        agent_id=101,
        challenge_id="0x" + "11" * 32,
        original_code="contract Vault { ... }",
        patched_code="contract Vault { ... }",
        vuln_class=0,
        difficulty=0,
        poc_proves_bug=True,
        poc_fails_after_patch=False,  # Failed to neutralize PoC!
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=True,
        timestamp=1700000000,
    )
    assert bundle.passed is False
    assert bundle.checksBitmap == 29  # 31 - 2


def test_generate_zk_attestation_bundle_core_checks_bitmap15():
    bundle = generate_zk_attestation_bundle(
        agent_id=102,
        challenge_id="reentrancy-001",
        original_code="contract Bank { ... }",
        patched_code="contract Bank { ... }",
        vuln_class=0,
        difficulty=1,
        poc_proves_bug=True,
        poc_fails_after_patch=True,
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=True,  # grader reports True when no suite is configured
        invariants_applied=False,  # Unconfigured invariant suite -> 15 (0x0F)
        timestamp=1700000000,
    )
    assert bundle.passed is True
    assert bundle.checksBitmap == 15
    assert len(bundle.encode_public_values()) == 288


def test_invariant_suite_failure_is_not_a_pass():
    """Regression: an invariant suite that ran and FAILED must not mint (bitmap 15 alone is not enough)."""
    bundle = generate_zk_attestation_bundle(
        agent_id=103,
        challenge_id="vault-inv-001",
        original_code="contract V { }",
        patched_code="contract V { uint x; }",
        poc_proves_bug=True,
        poc_fails_after_patch=True,
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=False,
        invariants_applied=True,
        timestamp=1700000000,
    )
    assert bundle.checksBitmap == 15
    assert bundle.passed is False


def test_unapplied_invariants_never_claim_five_checks():
    """Regression: bit 4 must not be set when no invariant suite ran, even if the grader says True."""
    bundle = generate_zk_attestation_bundle(
        agent_id=104,
        challenge_id="static-001",
        original_code="contract S { }",
        patched_code="contract S { uint y; }",
        poc_proves_bug=True,
        poc_fails_after_patch=True,
        hidden_tests_pass=True,
        patch_within_limits=True,
        invariants_hold=True,
        invariants_applied=False,
        timestamp=1700000000,
    )
    assert bundle.checksBitmap == 15
    assert bundle.passed is True
