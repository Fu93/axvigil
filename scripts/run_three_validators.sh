#!/usr/bin/env bash
# Start three local validator processes for a threshold demo.
# Keys stay in the environment. Do not commit them.
#
#   VALIDATOR_KEY_1=0x... VALIDATOR_KEY_2=0x... VALIDATOR_KEY_3=0x... \\
#   VERIFYING_CONTRACT=0x... CHAIN_ID=97 \\
#   ./scripts/run_three_validators.sh
#
# Listens on 127.0.0.1:9101, 9102, 9103. RECHECK defaults to 1 (re-grade).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${VALIDATOR_KEY_1:?}"
: "${VALIDATOR_KEY_2:?}"
: "${VALIDATOR_KEY_3:?}"
: "${VERIFYING_CONTRACT:?}"
export CHAIN_ID="${CHAIN_ID:-97}"
export RECHECK="${RECHECK:-1}"
# CHALLENGE_CONTRACT is the book that verifies ChallengeVerdict. /sign ignores it.
export CHALLENGE_CONTRACT="${CHALLENGE_CONTRACT:-}"
export AXV_ALLOW_TEST_GRADE="${AXV_ALLOW_TEST_GRADE:-}"
export PYTHONPATH="${ROOT}/backend:${ROOT}/verifier:${ROOT}/variantgen"
pids=()
start() {
  local key="$1" port="$2"
  VALIDATOR_KEY="$key" PORT="$port" python3 "$ROOT/scripts/run_validators.py" &
  pids+=("$!")
  echo "validator on 127.0.0.1:${port} pid $!"
}
start "$VALIDATOR_KEY_1" 9101
start "$VALIDATOR_KEY_2" 9102
start "$VALIDATOR_KEY_3" 9103
echo "Ctrl-C stops all three."
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM
wait
