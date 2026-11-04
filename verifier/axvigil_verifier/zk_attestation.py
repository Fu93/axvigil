"""Zero-Knowledge capability attestation journal generator for AxVigil Crucible zkVM."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict

from .keccak import canonicalize_source, keccak256


@dataclass
class ZKAttestationBundle:
    agentId: int
    challengeId: str
    patchCommitment: str  # 0x-hex 32-byte keccak256 of patch
    originalCodeHash: str  # 0x-hex 32-byte keccak256 of original code
    vulnClass: int  # 0..2
    difficulty: int  # 0..2
    checksBitmap: int  # 31 (0x1F) when all 5 checks ran and passed; 15 (0x0F) when no invariant suite ran
    timestamp: int
    passed: bool
    proofBytes: str  # SIMULATED placeholder, not a verifiable SP1 / Groth16 proof
    programVKey: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def encode_public_values(self) -> bytes:
        """ABI-encodes ZKPublicValues matching AxVigilZKVerifier.sol ZKPublicValues struct.
        (uint256,bytes32,bytes32,bytes32,uint8,uint8,uint8,uint64,bool) -> 288 bytes.
        """
        def pad32_int(val: int) -> bytes:
            return val.to_bytes(32, byteorder="big")

        def pad32_hex(hex_str: str) -> bytes:
            raw = bytes.fromhex(hex_str[2:] if hex_str.startswith("0x") else hex_str)
            if len(raw) < 32:
                raw = raw.ljust(32, b"\x00")
            return raw[:32]

        def challenge_bytes(c_id: str) -> bytes:
            if c_id.startswith("0x") and len(c_id) == 66:
                return pad32_hex(c_id)
            return keccak256(c_id.encode("utf-8"))

        return b"".join([
            pad32_int(self.agentId),
            challenge_bytes(self.challengeId),
            pad32_hex(self.patchCommitment),
            pad32_hex(self.originalCodeHash),
            pad32_int(self.vulnClass),
            pad32_int(self.difficulty),
            pad32_int(self.checksBitmap),
            pad32_int(self.timestamp),
            pad32_int(1 if self.passed else 0),
        ])


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
    vuln_class: int = 0,
    difficulty: int = 0,
    poc_proves_bug: bool,
    poc_fails_after_patch: bool,
    hidden_tests_pass: bool,
    patch_within_limits: bool,
    invariants_hold: bool,
    invariants_applied: bool = True,
    program_vkey: str = "0x" + hashlib.sha256(b"AxVigil-Crucible-zkVM-v1").hexdigest(),
    timestamp: int | None = None,
) -> ZKAttestationBundle:
    """Constructs the attestation journal (public values) and a SIMULATED proof envelope.

    `proofBytes` is NOT a real SP1 / Groth16 proof. It is a deterministic placeholder
    so the journal encoding can be exercised end to end. A real deployment must
    replace it with output from an SP1 prover running the Crucible program.

    Bit 4 (invariantsHold) is set only when an invariant suite was actually run
    (`invariants_applied`) and held. Outcomes:
      * applied and held          -> bitmap 31, passed
      * not applied (no suite)    -> bitmap 15, passed (4 core checks only)
      * applied and FAILED        -> bitmap 15, NOT passed
    """
    ts = timestamp if timestamp is not None else int(time.time())

    # Deterministic commitments matching Solidity keccak256
    orig_hash = "0x" + keccak256(canonicalize_source(original_code)).hex()
    patch_hash = "0x" + keccak256(canonicalize_source(patched_code)).hex()

    bitmap = compute_checks_bitmap(
        poc_proves_bug=poc_proves_bug,
        poc_fails_after_patch=poc_fails_after_patch,
        hidden_tests_pass=hidden_tests_pass,
        patch_within_limits=patch_within_limits,
        invariants_hold=bool(invariants_hold and invariants_applied),
    )
    core_passed = (bitmap & 0x0F) == 0x0F
    all_passed = core_passed and (bool(invariants_hold) or not invariants_applied)

    # Simulated proof envelope (placeholder, not a verifiable SNARK)
    proof_material = f"{orig_hash}:{patch_hash}:{vuln_class}:{difficulty}:{bitmap}:{ts}"
    simulated_proof = "0x" + hashlib.sha256(proof_material.encode("utf-8")).hexdigest() + "00" * 32

    return ZKAttestationBundle(
        agentId=agent_id,
        challengeId=challenge_id,
        patchCommitment=patch_hash,
        originalCodeHash=orig_hash,
        vulnClass=vuln_class,
        difficulty=difficulty,
        checksBitmap=bitmap,
        timestamp=ts,
        passed=all_passed,
        proofBytes=simulated_proof,
        programVKey=program_vkey,
    )
