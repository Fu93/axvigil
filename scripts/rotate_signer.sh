#!/usr/bin/env bash
# Point AxVigilCollectible.signer at a dedicated backend key.
# The owner calls setSigner. The signer key itself never needs to be on this machine:
# pass only the new signer's address. No redeploy: setSigner is already on the
# live contract and emits SignerUpdated.
#
# Required:
#   RPC_URL          chain RPC
#   AXVIGIL_COLLECTIBLE   collectible address
#   NEW_SIGNER       address the backend SIGNER_KEY controls
# Broadcast also needs:
#   OWNER_KEY        contract owner private key (hex). Omit it with DRY_RUN=1.
#
# DRY_RUN=1 reads the current signer and does not send a transaction.
set -euo pipefail

: "${RPC_URL:?Set RPC_URL}"
: "${AXVIGIL_COLLECTIBLE:?Set AXVIGIL_COLLECTIBLE}"
: "${NEW_SIGNER:?Set NEW_SIGNER}"

if ! command -v cast >/dev/null 2>&1; then
  echo "cast is not on PATH. Install Foundry (foundryup)." >&2
  exit 2
fi

current="$(cast call "$AXVIGIL_COLLECTIBLE" "signer()(address)" --rpc-url "$RPC_URL")"
echo "current signer: $current"
echo "new signer:     $NEW_SIGNER"

if [[ "${DRY_RUN:-}" == "1" ]]; then
  echo "DRY_RUN=1: not broadcasting setSigner."
  exit 0
fi

: "${OWNER_KEY:?Set OWNER_KEY to broadcast, or DRY_RUN=1 to read only}"

# BSC testnet still expects legacy transactions. GAS_PRICE is wei; default 1 gwei.
GAS_PRICE="${GAS_PRICE:-1000000000}"
cast send "$AXVIGIL_COLLECTIBLE" "setSigner(address)" "$NEW_SIGNER" \
  --private-key "$OWNER_KEY" \
  --rpc-url "$RPC_URL" \
  --legacy \
  --gas-price "$GAS_PRICE"

after="$(cast call "$AXVIGIL_COLLECTIBLE" "signer()(address)" --rpc-url "$RPC_URL")"
echo "signer after:   $after"
echo "setSigner broadcast complete."
