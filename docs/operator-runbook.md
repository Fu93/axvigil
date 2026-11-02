# Operator runbook

These steps need the owner key and, for a new mint, the backend signer key. They are not run from this repository's CI. Placeholders below stay empty until the transactions are mined.

Live contracts (no redeploy required for signer rotation; `setSigner` is already deployed):

| Role | Address |
|---|---|
| Collectible | `0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658` |
| Skill | `0x337743Da5894B58039743f46f689337991cECD18` |
| MockAgentID | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` |
| Current owner and signer | `0x4E38ec3f38D5c947B60E7e1273890Eea51501Ef8` |

Pending:

- `signerRotationTx`: null
- `batch2RevealTx`: null

## 1. Rotate the signer

Generate a new key on the operator machine. Do not commit it. Put the address in `NEW_SIGNER` and the private key only in the backend's `SIGNER_KEY`.

```bash
export RPC_URL=https://bsc-testnet-rpc.publicnode.com
export AXVIGIL_COLLECTIBLE=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658
export NEW_SIGNER=0x<address of the backend SIGNER_KEY>
export OWNER_KEY=0x<current owner key>

# read the current signer, send nothing
DRY_RUN=1 ./scripts/rotate_signer.sh

# broadcast setSigner
./scripts/rotate_signer.sh
```

Then set the backend environment (see `backend/.env.example`):

```bash
SIGNER_KEY=0x<the new key, same address as NEW_SIGNER>
VERIFYING_CONTRACT=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658
CHAIN_ID=97
RPC_URL=https://bsc-testnet-rpc.publicnode.com
AGENT_REGISTRY=0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e
AXVIGIL_REFERENCE_CHECK=1
# EVIDENCE_DIR=backend/evidence
# IPFS_PIN_URL=          # optional
# IPFS_PIN_TOKEN=        # optional
```

Record the transaction hash as `signerRotationTx` in `deployments/bsc-testnet-97.json` after it is mined. Until then the deployer address remains the signer.

## 2. Redeploy

Not required for signer rotation. A redeploy is required only if the collectible bytecode itself changes. This change does not.

## 3. Reveal batch 2

The seed is the preimage of the hash committed in `0xc48b3866605adac8328dad2bfff467ba9918c2a4c91271d9257c5b12fbaef222`. It is not in this repo. Write it to a file that is not committed, one hex line.

```bash
export RPC_URL=https://bsc-testnet-rpc.publicnode.com
export AXVIGIL_COLLECTIBLE=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658
export BATCH_ID=2
export SEED_FILE=/path/to/batch2.seed

# check the seed against the committed hash; do not send
python3 scripts/reveal_and_recompute.py --dry-run

export OWNER_KEY=0x<owner key>
python3 scripts/reveal_and_recompute.py
```

The script calls `revealSeed` then `revealTokens`, then replays tier and artId from chain data and compares `tokenURI`. Dry-run with no `SEED_FILE` only reads the deployment. Record the reveal transaction as `batch2RevealTx`. It is null until this is sent.

## 4. Evidence-bundled Muse Spark mint

With the backend running under the environment in step 1:

```bash
# agent, META_API_KEY set, practice or reward as intended
PYTHONPATH=agent:verifier python3 -m axvigil_agent solve \
  --challenge <dir from POST /v1/start> --max-iters 4
```

`POST /v1/submit` writes `EVIDENCE_DIR/<submissionHash>/manifest.json` and returns `evidenceCid`. `POST /v1/authorize` returns the same CID. The owner (or the Agent ID owner) submits the returned `MintAuth` on chain. The tie to the token is `Minted.submissionHash`, not `tokenURI`.

Recompute locally:

```bash
python3 scripts/verify_evidence.py "$EVIDENCE_DIR/<submissionHash>/manifest.json"
```

A fresh Muse Spark mint after this PR is not in the deployment file yet. The mint already on chain is `museSparkMint` (token #2, signature-replay). The reference-solution smoke test remains `smokeTest` (token #1).
