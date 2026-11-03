"""Zero-Knowledge capability attestation journal generator for AxVigil Crucible zkVM."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class ZKAttestationBundle:
    agentId: int
    challengeId: str
    patchCommitment: str  # 0x-hex 32-byte keccak256 of patch
    originalCodeHash: str  # 0x-hex 32-byte keccak256 of original code
    checksBitmap: int  # 31 (0x1F) when all 5 differential checks pass
    timestamp: int
    passed: bool
    proofBytes: str  # Hex-encoded zk-SNARK proof bytes
    programVKey: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def compute_checks_bitmap(
    poc_proves_bug: bool,
    poc_fails_after_patch: bool,
    hidden_tests_pass: bool,
    patch_within_limits: bool,
    invariants_hold: bool,
) -> int:
    """Compute the 5-bit checks bitmap.

    Bit 0: pocProvesBug (1)
    Bit 1: pocFailsAfterPatch (2)
    Bit 2: hiddenTestsPass (4)
    Bit 3: patchWithinLimits (8)
    Bit 4: invariantsHold (16)
    All pass = 1 + 2 + 4 + 8 + 16 = 31 (0x1F).
    """
    bm = 0
    if poc_proves_bug:
        bm |= 1
    if poc_fails_after_patch:
        bm |= 2
    if hidden_tests_pass:
        bm |= 4
    if patch_within_limits:
        bm |= 8
    if invariants_hold:
        bm |= 16
    return bm


def generate_zk_attestation_bundle(
    *,
    agent_id: int,
    challenge_id: str,
    original_code: str,
    patched_code: str,
    poc_proves_bug: bool,
    poc_fails_after_patch: bool,
    hidden_tests_pass: bool,
    patch_within_limits: bool,
    invariants_hold: bool,
    program_vkey: str = "0x" + hashlib.sha256(b"AxVigil-Crucible-zkVM-v1").hexdigest(),
    timestamp: int | None = None,
) -> ZKAttestationBundle:
    """Constructs a certified zkVM capability attestation journal and mock SNARK envelope."""
    ts = timestamp if timestamp is not None else int(time.time())

    # Deterministic commitments
    orig_hash = "0x" + hashlib.sha256(original_code.encode("utf-8")).hexdigest()
    patch_hash = "0x" + hashlib.sha256(patched_code.encode("utf-8")).hexdigest()

    bitmap = compute_checks_bitmap(
        poc_proves_bug=poc_proves_bug,
        poc_fails_after_patch=poc_fails_after_patch,
        hidden_tests_pass=hidden_tests_pass,
        patch_within_limits=patch_within_limits,
        invariants_hold=invariants_hold,
    )
    all_passed = bitmap == 31

    # Simulated zkVM Groth16 / STARK proof envelope
    proof_material = f"{orig_hash}:{patch_hash}:{bitmap}:{ts}"
    simulated_proof = "0x" + hashlib.sha256(proof_material.encode("utf-8")).hexdigest() + "00" * 32

    return ZKAttestationBundle(
        agentId=agent_id,
        challengeId=challenge_id,
        patchCommitment=patch_hash,
        originalCodeHash=orig_hash,
        checksBitmap=bitmap,
        timestamp=ts,
        passed=all_passed,
        proofBytes=simulated_proof,
        programVKey=program_vkey,
    )
