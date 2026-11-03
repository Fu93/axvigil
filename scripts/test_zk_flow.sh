#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
export PYTHONPATH="${ROOT}/agent:${ROOT}/verifier"
cd "$ROOT"

python3 - <<'PY'
from axvigil_verifier.zk_attestation import generate_zk_attestation_bundle

orig = "contract Vault { function withdraw() external {} }"
patch = "contract Vault { function withdraw() external { require(true); } }"

bundle = generate_zk_attestation_bundle(
    agent_id=1,
    challenge_id="reentrancy-vault",
    original_code=orig,
    patched_code=patch,
    poc_proves_bug=True,
    poc_fails_after_patch=True,
    hidden_tests_pass=True,
    patch_within_limits=True,
    invariants_hold=True,
)

print("ZK Proof Bundle generated successfully!")
print(f"  agentId:          {bundle.agentId}")
print(f"  challengeId:      {bundle.challengeId}")
print(f"  checksBitmap:     {hex(bundle.checksBitmap)} (all 5 checks active: 0x1F)")
print(f"  patchCommitment:  {bundle.patchCommitment}")
print(f"  originalCodeHash: {bundle.originalCodeHash}")
print(f"  proofBytes (hex): {bundle.proofBytes[:32]}...")
print(f"  passed:           {bundle.passed}")
PY
