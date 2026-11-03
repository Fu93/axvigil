#!/usr/bin/env bash
# Optimistic challenge-window demo. Default target is a local anvil.
# DEMO_TARGET=bsc broadcasts to BSC testnet (chain 97) and will not run unless
# I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1. Keys come from the environment or from
# AXVIGIL_CHALLENGE_ENV (a file you do not commit). This script never prints them.
#
#   ./scripts/run_challenge_demo.sh
#   DEMO_TARGET=bsc I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1 \
#     AXVIGIL_CHALLENGE_ENV=/path/to/challenge.env \
#     ./scripts/run_challenge_demo.sh
#
# Gas price defaults to 1 gwei legacy. Anvil uses anvil_increaseTime so the
# 120s window does not have to be slept. On BSC the script sleeps the window.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${PATH}"
cd "$ROOT"

if [[ -n "${AXVIGIL_CHALLENGE_ENV:-}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$AXVIGIL_CHALLENGE_ENV"
  set +a
fi

DEMO_TARGET="${DEMO_TARGET:-anvil}"
GAS_PRICE="${GAS_PRICE:-1000000000}"
export GAS_PRICE
CHALLENGE_WINDOW="${CHALLENGE_WINDOW:-120}"
RESPONSE_WINDOW="${RESPONSE_WINDOW:-3600}"
CHALLENGE_BOND="${CHALLENGE_BOND:-1000000000000000}"
OPERATOR_BOND="${OPERATOR_BOND:-2000000000000000}"
PROTOCOL_REWARD="${PROTOCOL_REWARD:-0}"
export CHALLENGE_WINDOW RESPONSE_WINDOW CHALLENGE_BOND OPERATOR_BOND PROTOCOL_REWARD
export AXV_ALLOW_TEST_GRADE="${AXV_ALLOW_TEST_GRADE:-1}"
export RECHECK="${RECHECK:-0}"

ANVIL_PID=""
VAL_PIDS=()
cleanup() {
  if [[ ${#VAL_PIDS[@]} -gt 0 ]]; then
    kill "${VAL_PIDS[@]}" 2>/dev/null || true
  fi
  if [[ -n "$ANVIL_PID" ]]; then
    kill "$ANVIL_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "$DEMO_TARGET" == "anvil" ]]; then
  export CHAIN_ID="${CHAIN_ID:-31337}"
  export RPC_URL="${RPC_URL:-http://127.0.0.1:8545}"
  # Public Anvil development keys. They have no value off this local chain.
  export PRIVATE_KEY="${PRIVATE_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"
  export VALIDATOR_KEY_1="${VALIDATOR_KEY_1:-0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d}"
  export VALIDATOR_KEY_2="${VALIDATOR_KEY_2:-0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a}"
  export VALIDATOR_KEY_3="${VALIDATOR_KEY_3:-0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6}"
  export CHALLENGER_KEY="${CHALLENGER_KEY:-0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a}"
  command -v anvil >/dev/null || { echo "anvil is not on PATH" >&2; exit 2; }
  anvil --silent --port "${RPC_URL##*:}" >/tmp/axv-challenge-anvil.log 2>&1 &
  ANVIL_PID=$!
  for _ in $(seq 1 50); do
    if cast chain-id --rpc-url "$RPC_URL" >/dev/null 2>&1; then break; fi
    sleep 0.1
  done
elif [[ "$DEMO_TARGET" == "bsc" ]]; then
  if [[ "${I_UNDERSTAND_THIS_SENDS_TESTNET_TX:-}" != "1" ]]; then
    echo "DEMO_TARGET=bsc sends testnet transactions. Set I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1." >&2
    exit 2
  fi
  export CHAIN_ID="${CHAIN_ID:-97}"
  export RPC_URL="${RPC_URL:-${BSC_TESTNET_RPC:-https://bsc-testnet-rpc.publicnode.com}}"
  : "${PRIVATE_KEY:?}"
  : "${CHALLENGER_KEY:?}"
  : "${VALIDATOR_KEY_1:?}"
  : "${VALIDATOR_KEY_2:?}"
  : "${VALIDATOR_KEY_3:?}"
else
  echo "DEMO_TARGET must be anvil or bsc" >&2
  exit 2
fi

command -v forge >/dev/null || { echo "forge is not on PATH" >&2; exit 2; }
command -v cast >/dev/null || { echo "cast is not on PATH" >&2; exit 2; }

export SIGNER="${SIGNER:-$(cast wallet address --private-key "$VALIDATOR_KEY_1")}"
export VALIDATOR_2="${VALIDATOR_2:-$(cast wallet address --private-key "$VALIDATOR_KEY_2")}"
export VALIDATOR_3="${VALIDATOR_3:-$(cast wallet address --private-key "$VALIDATOR_KEY_3")}"
export THRESHOLD="${THRESHOLD:-2}"
export HOURLY_CAP="${HOURLY_CAP:-50}"
if [[ -z "${SEED_HASH:-}" ]]; then
  SEED="0x$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  export SEED_HASH="$(cast keccak "$SEED")"
fi

if [[ -z "${AXVIGIL_COLLECTIBLE:-}" || -z "${AXVIGIL_CHALLENGE:-}" ]]; then
  LOG="$(mktemp)"
  (
    cd "$ROOT/contracts"
    forge script script/DeployChallenge.s.sol \
      --rpc-url "$RPC_URL" \
      --broadcast \
      --private-key "$PRIVATE_KEY" \
      --legacy \
      --with-gas-price "$GAS_PRICE" \
      -vv
  ) >"$LOG" 2>&1 || { cat "$LOG" >&2; exit 1; }
  pick() { grep -E "$1" "$LOG" | grep -oE '0x[a-fA-F0-9]{40}' | tail -1; }
  export AGENT_REGISTRY="${AGENT_REGISTRY:-$(pick AgentRegistry)}"
  export AXVIGIL_SKILL="${AXVIGIL_SKILL:-$(pick AxVigilSkill)}"
  export AXVIGIL_COLLECTIBLE="${AXVIGIL_COLLECTIBLE:-$(pick AxVigilCollectible)}"
  export AXVIGIL_CHALLENGE="${AXVIGIL_CHALLENGE:-$(pick AxVigilChallenge)}"
  rm -f "$LOG"
fi

: "${AGENT_REGISTRY:?deploy did not print AgentRegistry}"
: "${AXVIGIL_SKILL:?deploy did not print AxVigilSkill}"
: "${AXVIGIL_COLLECTIBLE:?deploy did not print AxVigilCollectible}"
: "${AXVIGIL_CHALLENGE:?deploy did not print AxVigilChallenge}"

export VERIFYING_CONTRACT="$AXVIGIL_COLLECTIBLE"
export CHALLENGE_CONTRACT="$AXVIGIL_CHALLENGE"
export PYTHONPATH="${ROOT}/backend:${ROOT}/verifier:${ROOT}/variantgen${PYTHONPATH:+:$PYTHONPATH}"

start_validator() {
  local key="$1" port="$2"
  VALIDATOR_KEY="$key" PORT="$port" python3 "$ROOT/scripts/run_validators.py" >/tmp/axv-validator-"$port".log 2>&1 &
  VAL_PIDS+=("$!")
}
start_validator "$VALIDATOR_KEY_1" 9101
start_validator "$VALIDATOR_KEY_2" 9102
start_validator "$VALIDATOR_KEY_3" 9103
export VALIDATOR_URLS="${VALIDATOR_URLS:-http://127.0.0.1:9101,http://127.0.0.1:9102,http://127.0.0.1:9103}"
for _ in $(seq 1 50); do
  if python3 -c 'import socket; socket.create_connection(("127.0.0.1", 9101), 1).close()' >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

python3 "$ROOT/scripts/challenge_play.py"
