#!/usr/bin/env bash
# One-command local demo for a hackathon judge.
#
#   ./scripts/judge_demo.sh
#
# Offline oracle, then a local anvil chain with the production quotas. The API
# checks Agent ID ownership against the MockAgentID deployed on that chain.
# Reward challenges are server-random; practice=true is how a caller picks a mother.
# The signed pool equals the solved difficulty (0 basic, 1 advanced, 2 legendary).
#
# Uses Anvil's public default keys. Never point this script at a public network.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.foundry/bin:${HOME}/.local/bin:${PATH}"
# shellcheck source=preflight.sh
source "$ROOT/scripts/preflight.sh"

preflight_python
preflight_forge
command -v anvil >/dev/null 2>&1 || { echo "anvil is not on PATH (it ships with Foundry)." >&2; exit 2; }
command -v cast >/dev/null 2>&1 || { echo "cast is not on PATH (it ships with Foundry)." >&2; exit 2; }

# Anvil account 0 owns the Agent ID and sends the mint. Account 1 only signs.
PLAYER_KEY="${PLAYER_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"
SIGNER_KEY="${SIGNER_KEY:-0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d}"
SIGNER="$(cast wallet address --private-key "$SIGNER_KEY")"
RPC_URL="${RPC_URL:-http://127.0.0.1:8545}"
PORT="${RPC_URL##*:}"
API_PORT="${API_PORT:-8000}"

TMP_DIR="$(mktemp -d)"
ANVIL_PID=""
API_PID=""
cleanup() {
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "$ANVIL_PID" ]]; then kill "$ANVIL_PID" 2>/dev/null || true; fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo ""
echo "== 1/4 oracle agent (offline, no API key) =="
PYTHONPATH="$ROOT/agent:$ROOT/verifier" python3 -m axvigil_agent solve \
  --challenge "$ROOT/challenges/reentrancy-vault" --oracle --json \
  >"$TMP_DIR/oracle.json"
python3 - <<'PY' "$TMP_DIR/oracle.json"
import json, sys
doc = json.load(open(sys.argv[1]))
print(f"solved={doc['solved']} iterations={len(doc['iterations'])}")
for it in doc["iterations"]:
    print(f"  iter {it['index']}: passed={it['passed']} {it['checks']}")
if not doc["solved"]:
    raise SystemExit("oracle agent did not solve the fixture")
PY

echo ""
echo "== 2/4 local chain and contracts =="
anvil --silent --port "$PORT" >"$TMP_DIR/anvil.log" 2>&1 &
ANVIL_PID=$!
for _ in $(seq 1 50); do
  if cast chain-id --rpc-url "$RPC_URL" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
CHAIN_ID="$(cast chain-id --rpc-url "$RPC_URL")"
echo "anvil chain id $CHAIN_ID"

(
  cd "$ROOT/contracts"
  PRIVATE_KEY="$PLAYER_KEY" SIGNER="$SIGNER" \
    forge script script/JudgeDemo.s.sol \
    --rpc-url "$RPC_URL" --broadcast --private-key "$PLAYER_KEY"
) >"$TMP_DIR/deploy.log"
REGISTRY="$(awk '/^[[:space:]]*REGISTRY /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
SKILL="$(awk '/^[[:space:]]*SKILL /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
COLLECTIBLE="$(awk '/^[[:space:]]*COLLECTIBLE /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
AGENT_ID="$(awk '/^[[:space:]]*AGENT_ID /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
MAX_SUPPLY="$(awk '/^[[:space:]]*MAX_SUPPLY /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
DRAWABLE="$(awk '/^[[:space:]]*DRAWABLE /{print $2}' "$TMP_DIR/deploy.log" | tail -1)"
if [[ -z "$COLLECTIBLE" || -z "$AGENT_ID" || -z "$REGISTRY" ]]; then
  echo "deploy did not print addresses. Log:" >&2
  cat "$TMP_DIR/deploy.log" >&2
  exit 1
fi
echo "registry    $REGISTRY"
echo "collectible $COLLECTIBLE"
echo "skill       $SKILL"
echo "agent id    $AGENT_ID"
echo "max supply  $MAX_SUPPLY  drawable $DRAWABLE (mint closes at public tiers; pool 2 rolls hidden at 0.25%)"

echo ""
echo "== 3/4 platform API (ownership checked against the local registry) =="
export SIGNER_KEY VERIFYING_CONTRACT="$COLLECTIBLE" CHAIN_ID
export AGENT_REGISTRY="$REGISTRY" RPC_URL
unset AXVIGIL_DEV_SKIP_OWNERSHIP
export DB_PATH="$TMP_DIR/axvigil.db"
export CHALLENGE_CACHE_DIR="$TMP_DIR/cache"
export SESSION_SECRET="judge-demo-not-a-production-secret"
mkdir -p "$CHALLENGE_CACHE_DIR"
PYTHONPATH="$ROOT/backend:$ROOT/verifier:$ROOT/variantgen" \
  python3 -m uvicorn axvigil_backend.app:app --host 127.0.0.1 --port "$API_PORT" --app-dir "$ROOT/backend" \
  >"$TMP_DIR/api.log" 2>&1 &
API_PID=$!
for _ in $(seq 1 50); do
  if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null; then break; fi
  sleep 0.2
done
curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null || {
  echo "API did not start. Log:" >&2
  cat "$TMP_DIR/api.log" >&2
  exit 1
}

AXVIGIL_API="http://127.0.0.1:${API_PORT}" \
  DB_PATH="$DB_PATH" CHALLENGE_CACHE_DIR="$CHALLENGE_CACHE_DIR" \
  MINT_AUTH_OUT="$TMP_DIR/mint.json" PLAYER_KEY="$PLAYER_KEY" AGENT_ID="$AGENT_ID" \
  python3 "$ROOT/scripts/judge_play.py" || {
    echo "API log:" >&2
    cat "$TMP_DIR/api.log" >&2
    exit 1
  }

echo ""
echo "== 4/4 mint, reveal, tokenURI =="
python3 - <<'PY' "$TMP_DIR/mint.json" "$TMP_DIR/mint-args.txt"
import json, sys
auth = json.load(open(sys.argv[1]))
if auth["pool"] != auth["difficulty"]:
    raise SystemExit("pool must equal difficulty")
sig = auth.pop("signature")
fields = ["agentId", "to", "vulnClass", "difficulty", "pool", "submissionHash", "nonce", "deadline"]
tuple_arg = "(" + ",".join(str(auth[name]) for name in fields) + ")"
open(sys.argv[2], "w").write(tuple_arg + "\n" + sig + "\n")
PY
TUPLE="$(sed -n '1p' "$TMP_DIR/mint-args.txt")"
SIG="$(sed -n '2p' "$TMP_DIR/mint-args.txt")"
cast send "$COLLECTIBLE" \
  "mint((uint256,address,uint8,uint8,uint8,bytes32,uint256,uint256),bytes)" \
  "$TUPLE" "$SIG" \
  --private-key "$PLAYER_KEY" --rpc-url "$RPC_URL" >/dev/null
echo "minted token 1 to $(cast wallet address --private-key "$PLAYER_KEY")"

SEED="$(cast keccak "axvigil-judge-demo")"
cast send "$COLLECTIBLE" "revealSeed(uint32,bytes32)" 1 "$SEED" \
  --private-key "$PLAYER_KEY" --rpc-url "$RPC_URL" >/dev/null
cast send "$COLLECTIBLE" "revealTokens(uint256)" 5 \
  --private-key "$PLAYER_KEY" --rpc-url "$RPC_URL" >/dev/null

echo "collectible tokenURI: $(cast call "$COLLECTIBLE" "tokenURI(uint256)(string)" 1 --rpc-url "$RPC_URL")"
echo "tier (0 common .. 3 legendary, 4 hidden only from pool 2): $(cast call "$COLLECTIBLE" "tierOf(uint256)(uint8)" 1 --rpc-url "$RPC_URL")"
cast call "$SKILL" "tokenURI(uint256)(string)" "$AGENT_ID" --rpc-url "$RPC_URL" >"$TMP_DIR/skill-uri.txt"
python3 - <<'PY' "$TMP_DIR/skill-uri.txt"
import base64, json, sys
uri = open(sys.argv[1]).read().strip().strip('"')
prefix = "data:application/json;base64,"
if not uri.startswith(prefix):
    print(uri[:180])
    raise SystemExit(0)
meta = json.loads(base64.b64decode(uri[len(prefix):]))
print(f"skill metadata name: {meta.get('name')}")
print(f"skill metadata description: {meta.get('description', '')[:180]}")
image = meta.get("image", "")
print(f"skill image is on-chain SVG: {image.startswith('data:image/svg+xml')}")
PY
echo ""
echo "Demo complete. Anvil and the API are stopped when this script exits."
