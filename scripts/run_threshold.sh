#!/usr/bin/env bash
# Muse Spark solve -> server grade + evidence bundle -> 3 validators re-grade and sign
# -> mint(auth, bytes[2]) on the threshold collectible (BSC testnet, chain 97).
#
# Keys are never printed. Load them from env files you do not commit, or export them:
#   AXVIGIL_DEPLOY_ENV          deploy wallet; its SIGNER_KEY is the Agent ID owner (PLAYER_KEY)
#   AXVIGIL_BACKEND_SIGNER_ENV  dedicated backend SIGNER_KEY and NEW_SIGNER
#   AXVIGIL_VALIDATORS_ENV      VALIDATOR_KEY_1 VALIDATOR_KEY_2 VALIDATOR_KEY_3
# If those files are unset, PLAYER_KEY, SIGNER_KEY, NEW_SIGNER, and VALIDATOR_KEY_* must
# already be in the environment.
#
#   META_API_KEY=... ./scripts/run_threshold.sh /tmp/axv-threshold-run
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:?out dir}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
export PATH="${HOME}/.foundry/bin:${PATH}"

if [[ -n "${AXVIGIL_DEPLOY_ENV:-}" ]]; then
  set -a; # shellcheck disable=SC1090
  . "$AXVIGIL_DEPLOY_ENV"; set +a
  PLAYER_KEY="${PLAYER_KEY:-$SIGNER_KEY}"
fi
if [[ -n "${AXVIGIL_BACKEND_SIGNER_ENV:-}" ]]; then
  set -a; # shellcheck disable=SC1090
  . "$AXVIGIL_BACKEND_SIGNER_ENV"; set +a
fi
if [[ -n "${AXVIGIL_VALIDATORS_ENV:-}" ]]; then
  set -a; # shellcheck disable=SC1090
  . "$AXVIGIL_VALIDATORS_ENV"; set +a
fi
: "${PLAYER_KEY:?Set PLAYER_KEY or AXVIGIL_DEPLOY_ENV}"
: "${VALIDATOR_KEY_1:?}"
: "${VALIDATOR_KEY_2:?}"
: "${VALIDATOR_KEY_3:?}"
: "${META_API_KEY:?}"

export RPC_URL="${RPC_URL:-https://bsc-testnet-rpc.publicnode.com}"
export AXVIGIL_COLLECTIBLE="${AXVIGIL_COLLECTIBLE:-0x0e8755245231b66FdcE3a625b764dc1Bb597C8eB}"
export AXVIGIL_SKILL="${AXVIGIL_SKILL:-0xE165C8B4826b6eF7aE84dfe3B1b27017aF1b5F59}"
export AGENT_REGISTRY="${AGENT_REGISTRY:-0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e}"
export CHAIN_ID="${CHAIN_ID:-97}"
export RECHECK="${RECHECK:-1}"
export AXVIGIL_SANDBOX="${AXVIGIL_SANDBOX:-subprocess}"
export GAS_PRICE="${GAS_PRICE:-1000000000}"
R="$RPC_URL"
NC="$AXVIGIL_COLLECTIBLE"
NS="$AXVIGIL_SKILL"
G="$AGENT_REGISTRY"

L="$OUT/onchain.log"
: > "$L"
say(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$L"; }
tx(){ local label="$1"; shift; local out
  out=$(cast send "$@" --legacy --gas-price "$GAS_PRICE" --timeout 300 --private-key "$PLAYER_KEY" --rpc-url "$R" --json)
  echo "$out" > "$OUT/receipt_${label}.json"
  python3 - "$OUT/receipt_${label}.json" "$label" <<'PY' | tee -a "$L" >&2
import json,sys
r=json.load(open(sys.argv[1])); g=int(r['gasUsed'],16); p=int(r['effectiveGasPrice'],16)
print(f"  tx {sys.argv[2]}: {r['transactionHash']} status={int(r['status'],16)} block={int(r['blockNumber'],16)} gasUsed={g} cost={g*p/1e18:.10f} tBNB https://testnet.bscscan.com/tx/{r['transactionHash']}")
PY
}
[ "$(cast chain-id --rpc-url "$R")" = 97 ] || { say "not chain 97"; exit 1; }
ME=$(cast wallet address --private-key "$PLAYER_KEY")
say "threshold collectible $NC (threshold $(cast call "$NC" 'threshold()(uint256)' --rpc-url "$R") of $(cast call "$NC" 'validatorCount()(uint256)' --rpc-url "$R")); player $ME; sandbox=$AXVIGIL_SANDBOX"
say "== 1. register a fresh MockAgentID =="
tx agentId "$G" 'mint(address)' "$ME"
AGENT_ID=$(python3 -c "import json;r=json.load(open('$OUT/receipt_agentId.json'));print([int(l['topics'][3],16) for l in r['logs'] if len(l['topics'])==4][0])")
say "Agent ID $AGENT_ID"
say "== 2. three validators (RECHECK=$RECHECK) =="
( cd "$ROOT" && VERIFYING_CONTRACT="$NC" CHAIN_ID="$CHAIN_ID" RECHECK="$RECHECK" \
    VALIDATOR_KEY_1="$VALIDATOR_KEY_1" VALIDATOR_KEY_2="$VALIDATOR_KEY_2" VALIDATOR_KEY_3="$VALIDATOR_KEY_3" \
    exec ./scripts/run_three_validators.sh ) > "$OUT/validators.log" 2>&1 &
VPID=$!
SRV=$(mktemp -d "${TMPDIR:-/tmp}/axv-threshold-XXXX")
export EVIDENCE_DIR="${EVIDENCE_DIR:-$OUT/evidence}"
PORT="${PORT:-8012}"
( cd "$ROOT" && VERIFYING_CONTRACT="$NC" CHAIN_ID="$CHAIN_ID" AGENT_REGISTRY="$G" RPC_URL="$R" \
  AXVIGIL_REFERENCE_CHECK=1 AXVIGIL_SANDBOX="$AXVIGIL_SANDBOX" EVIDENCE_DIR="$EVIDENCE_DIR" \
  SIGNER_KEY="${SIGNER_KEY:?Set SIGNER_KEY (backend signer)}" \
  DB_PATH="$SRV/axvigil.db" CHALLENGE_CACHE_DIR="$SRV/cache" \
  SESSION_SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')" \
  PYTHONPATH="$ROOT/backend:$ROOT/verifier:$ROOT/variantgen" \
  exec python3 -m uvicorn axvigil_backend.app:app --host 127.0.0.1 --port "$PORT" --app-dir "$ROOT/backend" ) > "$OUT/backend.log" 2>&1 &
APID=$!
cleanup(){ set +e; kill "$APID" 2>/dev/null; pkill -P "$VPID" 2>/dev/null; kill "$VPID" 2>/dev/null; pkill -f "scripts/run_validators.py" 2>/dev/null; true; }
trap cleanup EXIT
for _i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 0.5; done
say "backend health: $(curl -sf "http://127.0.0.1:$PORT/health" || true)"
say "== 3. Muse Spark solve, then validator co-signing =="
OUT="$OUT" AXVIGIL_API="http://127.0.0.1:$PORT" AGENT_ID="$AGENT_ID" PLAYER_KEY="$PLAYER_KEY" \
  AXV_REPO="$ROOT" EVIDENCE_DIR="$EVIDENCE_DIR" AXV_MAX_REQUESTS="${AXV_MAX_REQUESTS:-4}" \
  python3 -u "$ROOT/scripts/threshold_play.py" 2> >(tee -a "$L" >&2) || { say "no threshold MintAuth (exit $?)"; exit 1; }
say "== 4. mint(auth, bytes[2]) =="
TUPLE=$(python3 -c "
import json;a=json.load(open('$OUT/mint_auth.json'))
print('('+','.join(str(a[k]) for k in ['agentId','to','vulnClass','difficulty','pool','submissionHash','nonce','deadline'])+')')")
SIGS=$(cat "$OUT/mint_signatures.txt")
tx mint "$NC" 'mint((uint256,address,uint8,uint8,uint8,bytes32,uint256,uint256),bytes[])' "$TUPLE" "$SIGS"
TOKEN=$(python3 -c "
import json;r=json.load(open('$OUT/receipt_mint.json'))
T='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
print([int(l['topics'][3],16) for l in r['logs'] if l['address'].lower()=='$NC'.lower() and l['topics'][0]==T][0])")
say "== 5. readback =="
{
echo "collectible.ownerOf($TOKEN) = $(cast call "$NC" 'ownerOf(uint256)(address)' "$TOKEN" --rpc-url "$R")"
echo "collectible.tokenURI($TOKEN) = $(cast call "$NC" 'tokenURI(uint256)(string)' "$TOKEN" --rpc-url "$R")"
echo "skill.locked($AGENT_ID) = $(cast call "$NS" 'locked(uint256)(bool)' "$AGENT_ID" --rpc-url "$R")"
} | tee "$OUT/readback.txt" | tee -a "$L"
say "DONE agent $AGENT_ID token $TOKEN"
echo "$AGENT_ID $TOKEN" > "$OUT/result.txt"
