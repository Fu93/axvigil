#!/usr/bin/env bash
# Create a NEAR testnet account, deploy axvigil-record, and run one demo:
#   honest verifier seal -> anchor with a function-call key -> finalize
#   unfixed verifier seal -> false pass claim -> challenge -> revoke
# The function-call key can call only anchor_evidence on this contract.
#
# This broadcasts testnet transactions. It refuses every other network.
# Keys stay in the near-cli keychain and in near/.keys/ (gitignored).
# The script never prints a private key. Do not run it with `bash -x`.

set -euo pipefail
umask 077

if [[ "${I_UNDERSTAND_THIS_SENDS_TESTNET_TX:-}" != "1" ]]; then
  echo "refusing to broadcast. Set I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1" >&2
  exit 1
fi
if [[ "${1:-}" == *"mainnet"* || "${NEAR_ENV:-}" == "mainnet" || "${NEAR_NETWORK:-}" == "mainnet" ]]; then
  echo "refusing mainnet" >&2
  exit 1
fi

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.foundry/bin:/usr/local/cargo/bin:$PATH"
export PYTHONPATH="$ROOT/near/python${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"

command -v near >/dev/null || { echo "near-cli-rs is required (tested with 0.31.1)" >&2; exit 1; }
command -v forge >/dev/null || { echo "forge is required to run the AxVigil verifier" >&2; exit 1; }
command -v cargo >/dev/null || { echo "cargo is required to build the contract" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl is required to generate the scoped key" >&2; exit 1; }

WORKDIR="$ROOT/near/.keys/demo"
mkdir -p "$WORKDIR" "$ROOT/docs/near/seals"
TRANSCRIPT="$ROOT/docs/near/demo-transcript.txt"
: > "$TRANSCRIPT"

note() {
  printf '%s\n' "$*" | tee -a "$TRANSCRIPT"
}

record() {
  local label="$1"
  local status="$2"
  local log="$WORKDIR/${label}.log"
  {
    echo
    echo "===== $label (exit $status) ====="
    python3 -m axvigil_near redact "$log"
  } >> "$TRANSCRIPT"
}

run_tx() {
  local label="$1"
  shift
  local log="$WORKDIR/${label}.log"
  set +e
  timeout 240 "$@" </dev/null >"$log" 2>&1
  local status=$?
  set -e
  record "$label" "$status"
  if [[ "$status" -ne 0 ]]; then
    echo "command failed: $label" >&2
    python3 -m axvigil_near redact "$log" >&2
    exit "$status"
  fi
  local tx
  tx=$(python3 -m axvigil_near redact "$log" --tx)
  printf '%s\n' "$tx" > "$WORKDIR/${label}.tx"
  note "$label tx $tx"
}

expect_denied() {
  local label="$1"
  shift
  local log="$WORKDIR/${label}.log"
  set +e
  timeout 180 "$@" </dev/null >"$log" 2>&1
  local status=$?
  set -e
  record "$label" "$status"
  local redacted
  redacted=$(python3 -m axvigil_near redact "$log")
  if grep -Eq 'already registered|challenge window open|not pending|Execution succeeded' <<<"$redacted"; then
    # "Execution succeeded" can appear in near-cli's success banner. A denial
    # must not show that the contract method itself ran.
    if grep -Eq 'already registered|challenge window open|not pending' <<<"$redacted"; then
      echo "scoped key reached the contract for $label" >&2
      exit 1
    fi
  fi
  if [[ "$status" -eq 0 ]] && ! grep -Eiq 'error|not allowed|permission|lack the permission|MethodNotAllowed|does not have enough allowance|Access Key' <<<"$redacted"; then
    echo "expected $label to be denied by the access key" >&2
    printf '%s\n' "$redacted" >&2
    exit 1
  fi
  note "$label denied (exit $status)"
}

WINDOW=90
GAS='100 Tgas'
KEYFILE="$WORKDIR/agent-scoped.json"
if [[ "${AXVIGIL_NEAR_RESUME:-}" == "1" ]]; then
  # shellcheck disable=SC1090
  source "$WORKDIR/resume.env"
else
  SUFFIX=$(python3 -c 'import secrets; print(secrets.token_hex(4))')
  CONTRACT="axvigil-rec-${SUFFIX}.testnet"
  AGENT="agent.${CONTRACT}"
  CHALLENGER="challenger.${CONTRACT}"
fi
note "network testnet"
note "contract $CONTRACT"
note "agent $AGENT"
note "challenger $CHALLENGER"
note "resolver $CONTRACT"
note "window_seconds $WINDOW"
note "response_seconds 3600"
note "bonds 0 yoctoNEAR"

note "step submodule"
git submodule update --init --recursive >> "$TRANSCRIPT" 2>&1 || {
  echo "git submodule update failed" >&2
  exit 1
}

note "step forge-build"
( cd "$ROOT/contracts" && forge build ) >> "$TRANSCRIPT" 2>&1

note "step wasm"
cargo build --manifest-path "$ROOT/near/contract/Cargo.toml" --release --target wasm32-unknown-unknown --locked >> "$TRANSCRIPT" 2>&1
WASM="$ROOT/near/contract/target/wasm32-unknown-unknown/release/axvigil_record.wasm"
[[ -f "$WASM" ]] || { echo "missing wasm at $WASM" >&2; exit 1; }

python3 - << PY
import json
from pathlib import Path
Path("$WORKDIR/init.json").write_text(json.dumps({
    "response_seconds": 3600,
    "operator_bond_yocto": "0",
    "challenge_bond_yocto": "0",
}) + "\n")
PY

if [[ "${AXVIGIL_NEAR_RESUME:-}" == "1" ]]; then
  note "resuming existing testnet accounts"
  note "scoped_key_public $PUBLIC"
  note "scoped_key_methods anchor_evidence"
  note "scoped_key_allowance 0.25 NEAR"
  note "scoped_key_receiver $CONTRACT"
  for prior in create_contract deploy create_agent create_challenger register_agent add_scoped_key; do
    if [[ -f "$WORKDIR/${prior}.tx" ]]; then
      note "$prior tx $(tr -d '\n' < "$WORKDIR/${prior}.tx")"
    fi
  done
  python3 -c 'from axvigil_near.keys import expand_key_file; from pathlib import Path; expand_key_file(Path("'"$KEYFILE"'"))'
else
note "step create-contract"
run_tx create_contract \
  near account create-account sponsor-by-faucet-service "$CONTRACT" \
  autogenerate-new-keypair save-to-keychain \
  network-config testnet create

note "step deploy"
run_tx deploy \
  near contract deploy "$CONTRACT" use-file "$WASM" \
  with-init-call new file-args "$WORKDIR/init.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  network-config testnet sign-with-keychain send

note "step create-agent"
run_tx create_agent \
  near account create-account fund-myself "$AGENT" '2 NEAR' \
  autogenerate-new-keypair save-to-keychain \
  sign-as "$CONTRACT" network-config testnet sign-with-keychain send

note "step create-challenger"
run_tx create_challenger \
  near account create-account fund-myself "$CHALLENGER" '1 NEAR' \
  autogenerate-new-keypair save-to-keychain \
  sign-as "$CONTRACT" network-config testnet sign-with-keychain send

note "step register-agent"
run_tx register_agent \
  near contract call-function as-transaction "$CONTRACT" register_agent json-args '{}' \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$AGENT" network-config testnet sign-with-keychain send

KEYFILE="$WORKDIR/agent-scoped.json"
PUBLIC=$(python3 -m axvigil_near write-key --account "$AGENT" --out "$KEYFILE")
note "scoped_key_public $PUBLIC"
note "scoped_key_methods anchor_evidence"
note "scoped_key_allowance 0.25 NEAR"
note "scoped_key_receiver $CONTRACT"

note "step add-scoped-key"
run_tx add_scoped_key \
  near account add-key "$AGENT" grant-function-call-access \
  --allowance '0.25 NEAR' \
  --contract-account-id "$CONTRACT" \
  --function-names anchor_evidence \
  use-manually-provided-public-key "$PUBLIC" \
  network-config testnet sign-with-keychain send

cat > "$WORKDIR/resume.env" << EOF
CONTRACT=$CONTRACT
AGENT=$AGENT
CHALLENGER=$CHALLENGER
PUBLIC=$PUBLIC
EOF
fi

note "step grade-honest"
python3 -m axvigil_near seal \
  --challenge "$ROOT/challenges/reentrancy-001" \
  --patch "$ROOT/challenges/reentrancy-001/submissions/sample.patch" \
  --poc "$ROOT/challenges/reentrancy-001/submissions/sample_poc.t.sol" \
  --out "$WORKDIR/honest-seal.json"
python3 - << PY
import json
from pathlib import Path
seal = json.loads(Path("$WORKDIR/honest-seal.json").read_text())
if seal["passed"] is not True:
    raise SystemExit("honest sample did not pass")
Path("$ROOT/docs/near/seals/honest-seal.json").write_text(json.dumps(seal, indent=2) + "\n")
Path("$ROOT/docs/near/seals/honest.canonical.json").write_text(seal["canonical"])
print(seal["evidence_hash"])
PY
HONEST_HASH=$(python3 -c 'import json; print(json.load(open("'"$WORKDIR/honest-seal.json"'"))["evidence_hash"])')
note "honest_evidence_hash $HONEST_HASH"

note "step grade-unfixed"
python3 -m axvigil_near seal-unfixed \
  --challenge "$ROOT/challenges/reentrancy-001" \
  --poc "$ROOT/challenges/reentrancy-001/submissions/sample_poc.t.sol" \
  --out "$WORKDIR/bad-seal.json"
BAD_HASH=$(python3 -c 'import json; print(json.load(open("'"$WORKDIR/bad-seal.json"'"))["evidence_hash"])')
if [[ "$HONEST_HASH" == "$BAD_HASH" ]]; then
  echo "honest and unfixed submission hashes collided" >&2
  exit 1
fi
python3 - << PY
import json
from pathlib import Path
seal = json.loads(Path("$WORKDIR/bad-seal.json").read_text())
Path("$ROOT/docs/near/seals/bad-seal.json").write_text(json.dumps(seal, indent=2) + "\n")
Path("$ROOT/docs/near/seals/bad.canonical.json").write_text(seal["canonical"])
PY
note "bad_evidence_hash $BAD_HASH"
note "bad seal passed=false; the anchor below claims passed=true"

python3 -m axvigil_near anchor-args --seal "$WORKDIR/honest-seal.json" --window-seconds "$WINDOW" \
  --out "$WORKDIR/honest-args.json"
python3 -m axvigil_near anchor-args --seal "$WORKDIR/bad-seal.json" --window-seconds "$WINDOW" \
  --claim-pass --out "$WORKDIR/bad-args.json"
cp "$WORKDIR/honest-args.json" "$ROOT/docs/near/seals/honest-anchor-args.json"
cp "$WORKDIR/bad-args.json" "$ROOT/docs/near/seals/bad-anchor-args.json"

note "step anchor-honest"
run_tx anchor_honest \
  near contract call-function as-transaction "$CONTRACT" anchor_evidence \
  file-args "$WORKDIR/honest-args.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$AGENT" network-config testnet \
  sign-with-access-key-file "$KEYFILE" send

note "step anchor-bad"
run_tx anchor_bad \
  near contract call-function as-transaction "$CONTRACT" anchor_evidence \
  file-args "$WORKDIR/bad-args.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$AGENT" network-config testnet \
  sign-with-access-key-file "$KEYFILE" send

note "step scoped-key-cannot-finalize"
expect_denied scoped_finalize \
  near contract call-function as-transaction "$CONTRACT" finalize \
  json-args "{\"evidence_hash\":\"$HONEST_HASH\"}" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$AGENT" network-config testnet \
  sign-with-access-key-file "$KEYFILE" send

note "step scoped-key-cannot-transfer"
expect_denied scoped_transfer \
  near tokens "$AGENT" send-near "$CHALLENGER" '0.01 NEAR' \
  network-config testnet sign-with-access-key-file "$KEYFILE" send

python3 - << PY
import json
from pathlib import Path
Path("$WORKDIR/challenge-args.json").write_text(json.dumps({
    "evidence_hash": "$BAD_HASH",
    "challenge_hash": json.load(open("$WORKDIR/bad-seal.json"))["bundle_sha256"],
}) + "\n")
PY

note "step challenge-bad"
run_tx challenge_bad \
  near contract call-function as-transaction "$CONTRACT" challenge \
  file-args "$WORKDIR/challenge-args.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$CHALLENGER" network-config testnet sign-with-keychain send

python3 - << PY
import json
from pathlib import Path
Path("$WORKDIR/resolve-args.json").write_text(json.dumps({
    "evidence_hash": "$BAD_HASH",
    "upheld": True,
}) + "\n")
PY

note "step resolve-bad"
run_tx resolve_bad \
  near contract call-function as-transaction "$CONTRACT" resolve_challenge \
  file-args "$WORKDIR/resolve-args.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$CONTRACT" network-config testnet sign-with-keychain send

python3 - << PY
import json
from pathlib import Path
Path("$WORKDIR/finalize-args.json").write_text(json.dumps({
    "evidence_hash": "$HONEST_HASH",
}) + "\n")
PY

note "step wait-for-window"
python3 - << PY
import json, time, urllib.request, base64
from pathlib import Path
contract = "$CONTRACT"
evidence = "$HONEST_HASH"
payload = {
    "jsonrpc": "2.0",
    "id": "axvigil",
    "method": "query",
    "params": {
        "request_type": "call_function",
        "finality": "final",
        "account_id": contract,
        "method_name": "get_record",
        "args_base64": base64.b64encode(json.dumps({"evidence_hash": evidence}).encode()).decode(),
    },
}
req = urllib.request.Request(
    "https://rpc.testnet.near.org",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30) as response:
    body = json.loads(response.read().decode())
record = json.loads(bytes(body["result"]["result"]).decode())
ready = int(record["ready_at_ns"]) / 1_000_000_000
delay = ready - time.time() + 3
Path("$WORKDIR/ready_at.txt").write_text(record["ready_at_ns"] + "\n")
print(f"ready_at_ns {record['ready_at_ns']} sleep {max(delay, 0):.1f}")
if delay > 0:
    time.sleep(delay)
PY

note "step finalize-honest"
run_tx finalize_honest \
  near contract call-function as-transaction "$CONTRACT" finalize \
  file-args "$WORKDIR/finalize-args.json" \
  prepaid-gas "$GAS" attached-deposit '0 NEAR' \
  sign-as "$CHALLENGER" network-config testnet sign-with-keychain send

python3 - << PY
import json
from pathlib import Path
root = Path("$ROOT")
def tx(name):
    return Path("$WORKDIR") .joinpath(f"{name}.tx").read_text().strip()
honest = json.loads(Path("$WORKDIR/honest-seal.json").read_text())
bad = json.loads(Path("$WORKDIR/bad-seal.json").read_text())
contract = "$CONTRACT"
deployment = {
    "network": "testnet",
    "spec": "axvigil-record/1",
    "contract": contract,
    "agent": "$AGENT",
    "challenger": "$CHALLENGER",
    "resolver": contract,
    "owner": contract,
    "rpc": "https://rpc.testnet.near.org",
    "window_seconds": $WINDOW,
    "response_seconds": 3600,
    "operator_bond_yocto": "0",
    "challenge_bond_yocto": "0",
    "scoped_key": {
        "public_key": "$PUBLIC",
        "allowance": "0.25 NEAR",
        "receiver": contract,
        "method_names": ["anchor_evidence"],
    },
    "honest_evidence_hash": honest["evidence_hash"],
    "honest_bundle_sha256": honest["bundle_sha256"],
    "bad_evidence_hash": bad["evidence_hash"],
    "bad_bundle_sha256": bad["bundle_sha256"],
    "transactions": {
        "create_contract": tx("create_contract"),
        "deploy": tx("deploy"),
        "create_agent": tx("create_agent"),
        "create_challenger": tx("create_challenger"),
        "register_agent": tx("register_agent"),
        "add_scoped_key": tx("add_scoped_key"),
        "anchor_honest": tx("anchor_honest"),
        "anchor_bad": tx("anchor_bad"),
        "challenge_bad": tx("challenge_bad"),
        "resolve_bad": tx("resolve_bad"),
        "finalize_honest": tx("finalize_honest"),
    },
}
deployment["explorers"] = {
    "contract": f"https://testnet.nearblocks.io/address/{contract}",
    "agent": f"https://testnet.nearblocks.io/address/{deployment['agent']}",
}
deployment["explorers"].update({
    name: f"https://testnet.nearblocks.io/txns/{value}"
    for name, value in deployment["transactions"].items()
})
text = json.dumps(deployment, indent=2) + "\n"
if "private_key" in text or "ed25519:[redacted]" in text:
    raise SystemExit("deployment record looks wrong")
(root / "docs" / "near" / "deployment.json").write_text(text)
print(text)
PY

note "step view"
python3 - << PY
import json, time
from pathlib import Path
from axvigil_near.rpc import call_view
contract = "$CONTRACT"
agent = "$AGENT"
honest = "$HONEST_HASH"
bad = "$BAD_HASH"
rpc = "https://rpc.testnet.near.org"
last = None
for _ in range(12):
    try:
        report = {
            "spec": call_view(rpc, contract, "spec", {}),
            "reputation": call_view(rpc, contract, "get_reputation", {"account": agent}),
            "honest": call_view(rpc, contract, "get_record", {"evidence_hash": honest}),
            "bad": call_view(rpc, contract, "get_record", {"evidence_hash": bad}),
        }
    except Exception as exc:  # retry while the final block catches up
        last = str(exc)
        time.sleep(3)
        continue
    if (
        report["honest"]["status"] == "Final"
        and report["bad"]["status"] == "Revoked"
        and report["reputation"]["finalized"] == 1
        and report["reputation"]["revoked"] == 1
        and report["reputation"]["is_valid"] is True
    ):
        Path("$ROOT/docs/near/view.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        raise SystemExit(0)
    last = report
    time.sleep(3)
raise SystemExit(f"on-chain view did not match the demo: {last}")
PY

python3 - << PY
import json
from pathlib import Path
text = Path("$TRANSCRIPT").read_text()
docs = Path("$ROOT/docs/near")
blob = "\n".join(path.read_text() for path in docs.rglob("*") if path.is_file())
secrets = []
for root in (Path.home() / ".near-credentials", Path.home() / ".config" / "near-cli", Path("$WORKDIR")):
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            raw = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "private_key" not in raw and "secret_key" not in raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        secret = parsed.get("private_key") or parsed.get("secret_key")
        if isinstance(secret, str) and secret.startswith("ed25519:") and secret in blob:
            secrets.append(str(path))
if secrets:
    raise SystemExit("a committed doc contains a private key from " + ", ".join(secrets))
for line in text.splitlines():
    if "private_key" in line.lower() and "[redacted]" not in line:
        raise SystemExit(line)
print("transcript secret scan ok")
PY

note "demo complete"
echo "wrote $ROOT/docs/near/deployment.json"
