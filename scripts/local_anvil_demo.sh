#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
# shellcheck source=preflight.sh
source "$ROOT/scripts/preflight.sh"
preflight_python
preflight_forge
command -v anvil >/dev/null 2>&1 || { echo "anvil is not on PATH (it ships with Foundry)." >&2; exit 2; }
command -v cast >/dev/null 2>&1 || { echo "cast is not on PATH (it ships with Foundry)." >&2; exit 2; }
RPC_URL="${RPC_URL:-http://127.0.0.1:8545}"
PORT="${RPC_URL##*:}"
# Anvil's first deterministic account; valid only on this local chain.
export PRIVATE_KEY="${PRIVATE_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"
TMP_DIR="$(mktemp -d)"
ANVIL_PID=""
trap 'if [[ -n "$ANVIL_PID" ]]; then kill "$ANVIL_PID" 2>/dev/null || true; fi; rm -rf "$TMP_DIR"' EXIT

anvil --silent --port "$PORT" >"$TMP_DIR/anvil.log" 2>&1 &
ANVIL_PID=$!
for _ in $(seq 1 30); do
  if cast chain-id --rpc-url "$RPC_URL" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
cast chain-id --rpc-url "$RPC_URL" | grep -qx '31337'

cd "$ROOT"
PYTHONPATH="$ROOT/verifier" python3 -m axvigil_verifier grade \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol \
  --json > "$TMP_DIR/verifier-result.json"
export SUBMISSION_HASH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["submissionHash"])' "$TMP_DIR/verifier-result.json")"

cd "$ROOT/contracts"
forge script script/LocalDemo.s.sol \
  --rpc-url "$RPC_URL" \
  --broadcast \
  --private-key "$PRIVATE_KEY"
