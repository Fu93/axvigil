# MintAuth backend bridge

This is the second AxVigil vertical-slice component. It consumes a **passed** verifier result and produces the EIP-712 `MintAuth` payload expected by `AxVigilCollectible.mint`.

The signer private key is read from an environment variable and is never printed. This CLI only signs data; it does not submit a blockchain transaction.

## Usage

```bash
pip install -r backend/requirements.txt
export AXVIGIL_SIGNER_PRIVATE_KEY=0x...
python -m backend.mint_auth \
  --result verifier-result.json \
  --agent-id 1 \
  --to 0xYourAgentOwner \
  --chain-id 97 \
  --verifying-contract 0xYourAxVigilCollectible \
  --nonce 1 \
  --deadline 1790000000 \
  --difficulty 1 \
  --pool 0
```

The command refuses to sign unless the result has `challengeId: reentrancy-001` and `passed: true`. The emitted `auth` fields and signature map directly to the Solidity `MintAuth` struct. `submissionHash` is copied from the verifier result, so the signed claim is bound to the exact canonical patch/PoC submission.

For production, put the signer behind a protected backend service or HSM, persist nonce allocation, and add authorization around which Agent ID owner may request a signature. Do not commit private keys or `.env` files.
