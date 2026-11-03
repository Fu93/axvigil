# Operator runbook

These steps need the owner key and, for a new mint, the backend signer key. They are not run from this repository's CI. The BSC testnet (chain 97) broadcast listed under "Done" is already in `deployments/bsc-testnet-97.json`. The commands below are how to repeat a rotation, a reveal, or another mint.

Live contracts (no redeploy required for signer rotation; `setSigner` is already deployed):

| Role | Address |
|---|---|
| Collectible | `0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658` |
| Skill | `0x337743Da5894B58039743f46f689337991cECD18` |
| MockAgentID | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` |
| Current owner and signer | `0x4E38ec3f38D5c947B60E7e1273890Eea51501Ef8` |

Done on BSC testnet (chain 97):

- Original collectible signer rotation: `0xaea5242f066736eae950daf093a8cfe44e863e2341e97ab4e08e406f1cea2d3b` (now `0x91AeE1253D3EF16864FEfC8EFF3431959c86e081`)
- Batch 2 reveal: `0xf83f082999ea63a7bef5f4eacc105e1aa2d648c2be38af1a5ff7fabdb978d597` and revealTokens `0x343f3a8ca91b5c31b5441381900eddf7478e9ed01deeb4e9900338c6273f6ef2`. Recompute mismatches: 0. Token #2 is LEGENDARY, artId 320000.
- Threshold collectible `0x0e8755245231b66FdcE3a625b764dc1Bb597C8eB`, skill `0xE165C8B4826b6eF7aE84dfe3B1b27017aF1b5F59`, threshold 2 of 3. Validators `0xc32d95193F489EF0ACBE767D387509a8a3C495F9`, `0xD5f579698CdbFD0FA1C7d1F36127b8276F5c4645`, `0x133Fa4314da9a90aEB8a7AB9F281149F4d0Dec7f`. Owner `0x94aC129e81ababD2153093b33ec4B2920d11f6E9` is not a validator. Deploy `0xd3717767483596a9aeba2ceea15a7613d227344e93d077b17db7c57540aaac4b`.
- Three Muse Spark threshold mints, each first-request pass, `verify_evidence.py` OK. Grading used `AXVIGIL_SANDBOX=subprocess`. Docker was not used.

Another mint uses `scripts/run_threshold.sh` (below). Keys come from env files you do not commit.

## Coordinator (`scripts/run_threshold.sh`)

Posts one evidence bundle to the three validators, keeps two signatures, and sends `mint(auth, bytes[])`. Default gas price is 1 gwei (`GAS_PRICE=1000000000`).

```bash
export META_API_KEY=...
export AXVIGIL_DEPLOY_ENV=/path/to/deploy.env          # SIGNER_KEY here is the player
export AXVIGIL_BACKEND_SIGNER_ENV=/path/to/backend.env # dedicated SIGNER_KEY
export AXVIGIL_VALIDATORS_ENV=/path/to/validators.env  # VALIDATOR_KEY_1/2/3
./scripts/run_threshold.sh /tmp/axv-threshold-run
```

Do not commit those env files. The live three mints already used this flow with the subprocess sandbox.

## 0. Deploy the threshold collectible (already broadcast; repeat only for a new chain)

The original collectible does not have `mint(auth, bytes[])`. The threshold pair is a separate deploy, not an upgrade of token #1 and token #2. Those tokens stay on `0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658`. `thresholdRedeploy` in `deployments/bsc-testnet-97.json` is filled (`status` `live`). Repeat the script only for a new chain, then record the new addresses the same way.

```bash
export PRIVATE_KEY=0x<deployer, also the initial owner>
export SIGNER=0x<validator 1 address>
export VALIDATOR_2=0x<validator 2 address>
export VALIDATOR_3=0x<validator 3 address>
export THRESHOLD=2
export OWNER=0x<admin, not one of the validators>
export AGENT_REGISTRY=0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e
export BSC_TESTNET_RPC=https://bsc-testnet-rpc.publicnode.com

cd contracts
forge script script/DeployThreshold.s.sol --rpc-url "$BSC_TESTNET_RPC" --broadcast
```

If `OWNER` is not the deployer, the owner must call `acceptOwnership()` on the new collectible. The deployer registers the three validators and `setThreshold(2)` before that hand-off. Validator private keys are not in this command: only addresses. Put each key in `VALIDATOR_KEY_1` / `_2` / `_3` on the machine that runs the validators.

```bash
export VERIFYING_CONTRACT=0x<new collectible from the script log>
export CHAIN_ID=97
export VALIDATOR_KEY_1=0x<key for SIGNER>
export VALIDATOR_KEY_2=0x<key for VALIDATOR_2>
export VALIDATOR_KEY_3=0x<key for VALIDATOR_3>
export RECHECK=1
./scripts/run_three_validators.sh
```

A coordinator (or a small client) POSTs the evidence `manifest` and one shared `auth` to `http://127.0.0.1:9101/sign`, `:9102`, and `:9103`, keeps the first 2 signatures, and the Agent ID owner calls `mint(auth, signatures)` on the new collectible. `submissionHash` is still single-use. The mint cap is still 2 per Agent ID. Pool must still equal difficulty.

Live deals already reference-check the seed before `start()` returns source when `AXVIGIL_REFERENCE_CHECK` is on (the server default), and they skip a structural fingerprint this process has already issued.

## 1. Rotate the signer on the current single-signer collectible

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

The live rotation is already mined: `signerRotationTx` `0xaea5242f066736eae950daf093a8cfe44e863e2341e97ab4e08e406f1cea2d3b`. The signer is `0x91AeE1253D3EF16864FEfC8EFF3431959c86e081`. Record any later rotation the same way.

## 2. Redeploy

Not required for signer rotation. A redeploy is required only if the collectible bytecode itself changes. This change does not.

## 3. Reveal batch 2

Batch 2 is already revealed. The seed is public on chain and recorded in `deployments/bsc-testnet-97.json` (`0xb1f8de1b66cb064e9f72e5afaaa3ad3ee4e62cf9db43930268d8ba134cf67f6b`). `revealSeed` is `0xf83f082999ea63a7bef5f4eacc105e1aa2d648c2be38af1a5ff7fabdb978d597`. `revealTokens` is `0x343f3a8ca91b5c31b5441381900eddf7478e9ed01deeb4e9900338c6273f6ef2`. Recompute mismatches: 0. A later batch still needs its seed in a file you do not commit, one hex line. The commitment for batch 2 was `0xc48b3866605adac8328dad2bfff467ba9918c2a4c91271d9257c5b12fbaef222`.

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

The script calls `revealSeed` then `revealTokens`, then replays tier and artId from chain data and compares `tokenURI`. Dry-run with no `SEED_FILE` only reads the deployment. `batch2RevealTx` is the mined `revealSeed` transaction above. Record a later reveal the same way.

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

The three threshold Muse Spark mints are `museSparkThresholdMint` (tokens #1–#3 on `0x0e87…C8eB`). Their `tokenURI` is still `ipfs://unrevealed.json`. The earlier signature-replay mint is `museSparkMint` (token #2 on `0x0658…4658`, revealed LEGENDARY). The reference-solution smoke test remains `smokeTest` (token #1).

## New deployment safety requirements

For a new deployment, provide the complete art-set commitment and immutable metadata roots:

```bash
export BASE_URI=ipfs://<art-root>/
export UNREVEALED_URI=ipfs://<unrevealed-metadata>
export PROVENANCE_HASH=0x<keccak256-of-the-complete-art-set>
export FREEZE_METADATA=1
forge script script/Deploy.s.sol --rpc-url bsc_testnet --broadcast
```

`FREEZE_METADATA=1` calls the irreversible `freezeMetadata()` guard after setting the provenance
hash. The existing BSC testnet contracts predate this guard and are intentionally documented as
mutable demo deployments; do not use them as a production-candidate deployment.

For untrusted agent-written Solidity, set `AXVIGIL_SANDBOX=docker` and build the pinned image from
`verifier/docker` before grading. Docker mode is built and exercised in CI; subprocess mode remains
available for the historical testnet demo only.
