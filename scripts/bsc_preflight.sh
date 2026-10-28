#!/usr/bin/env bash
set -euo pipefail

export PATH="${HOME}/.foundry/bin:${PATH}"
RPC_URL="${BSC_TESTNET_RPC:-https://data-seed-prebsc-1-s1.bnbchain.org:8545}"
MIN_TBNB="${MIN_TBNB:-0.01}"

if [[ -z "${PRIVATE_KEY:-}" ]]; then
  echo "PRIVATE_KEY is not set. Use a dedicated BSC testnet-only wallet." >&2
  exit 2
fi
command -v cast >/dev/null || { echo "cast is required; install Foundry first" >&2; exit 2; }

CHAIN_ID="$(cast chain-id --rpc-url "$RPC_URL")"
if [[ "$CHAIN_ID" != "97" ]]; then
  echo "Wrong chain ID: expected 97 (BSC Testnet), got $CHAIN_ID" >&2
  exit 1
fi

DEPLOYER="$(cast wallet address --private-key "$PRIVATE_KEY")"
BALANCE="$(cast balance "$DEPLOYER" --rpc-url "$RPC_URL" --ether)"
SIGNER_ADDRESS="${SIGNER:-$DEPLOYER}"

python3 - "$BALANCE" "$MIN_TBNB" <<'PY'
from decimal import Decimal
import sys
balance = Decimal(sys.argv[1].split()[0])
minimum = Decimal(sys.argv[2])
if balance < minimum:
    raise SystemExit(f"Insufficient tBNB: {balance} available, need at least {minimum}")
PY

printf '%s\n' "BSC testnet preflight passed"
printf '%s\n' "RPC: $RPC_URL"
printf '%s\n' "Chain ID: $CHAIN_ID"
printf '%s\n' "Deployer: $DEPLOYER"
printf '%s\n' "Signer: $SIGNER_ADDRESS"
printf '%s\n' "Balance: $BALANCE tBNB"
printf '%s\n' "Explorer: https://testnet.bscscan.com/address/$DEPLOYER"
