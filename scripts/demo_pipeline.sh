#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
# shellcheck source=preflight.sh
source "$ROOT/scripts/preflight.sh"
preflight_python
preflight_forge

if [[ -z "${AXVIGIL_SIGNER_PRIVATE_KEY:-}" ]]; then
  # Demo-only key. Never use this key on a public network or with real funds.
  export AXVIGIL_SIGNER_PRIVATE_KEY="0x1111111111111111111111111111111111111111111111111111111111111111"
  echo "Using the deterministic demo-only signer key" >&2
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT"
PYTHONPATH="$ROOT/verifier" python3 -m axvigil_verifier grade \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol \
  --json > "$TMP_DIR/verifier-result.json"

python3 -m backend.mint_auth \
  --result "$TMP_DIR/verifier-result.json" \
  --agent-id 1 \
  --to 0x00000000000000000000000000000000000000AA \
  --chain-id 97 \
  --verifying-contract 0x00000000000000000000000000000000000000BB \
  --nonce 1 \
  --deadline "$(( $(date +%s) + 3600 ))" \
  --difficulty 1 \
  --pool 0 > "$TMP_DIR/mint-auth.json"

python3 - <<'PY' "$TMP_DIR/verifier-result.json" "$TMP_DIR/mint-auth.json"
import json
import sys

result = json.load(open(sys.argv[1]))
auth = json.load(open(sys.argv[2]))
assert result["passed"] is True
assert auth["auth"]["submissionHash"] == result["submissionHash"]
assert auth["signature"].startswith("0x")
print("[1/3] verifier: passed")
print(f"[2/3] MintAuth: signed by {auth['signer']}")
print(f"      submissionHash: {auth['auth']['submissionHash']}")
PY

cd "$ROOT/contracts"
forge test --match-path test/VerifierMintIntegration.t.sol
printf '%s\n' "[3/3] contract integration: passed"
