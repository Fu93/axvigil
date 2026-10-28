# AxVigil

> Train and certify AI agents that fix smart-contract vulnerabilities.

AxVigil is a hackathon prototype for turning verified smart-contract fixes into portable, on-chain credentials for AI agents. An agent solves a vulnerability challenge, a deterministic verifier checks the patch and proof of concept, and a signed EIP-712 authorization lets the Agent ID owner mint both a tradeable collectible and a non-transferable skill record.

**Meta Global AI Developer Hackathon · BSC testnet · sandbox/whitehat demo**

## Why AxVigil

AI coding agents can generate patches, but it is difficult to distinguish a plausible answer from a fix that actually removes an exploit without breaking the contract. AxVigil connects four pieces:

```text
challenge → AI-generated patch + PoC → deterministic verifier → signed on-chain credential
```

The credential is bound to a SPACE ID-style Agent ID rather than a wallet. The collectible records the challenge category and difficulty, while the ERC-5192 skill record accumulates the agent's verified vulnerability-solving history.

## Current repository status

The current public prototype implements the smart-contract credential layer:

- `AxVigilCollectible`: ERC-721 collectible with EIP-712 mint authorization, fixed tier pools, staged rarity release, commit-reveal demo randomness, per-Agent ID quota, hourly cap and pause controls.
- `AxVigilSkill`: ERC-5192-style soulbound skill record bound to an Agent ID, with vulnerability-class counts, maximum difficulty, revocation and on-chain SVG metadata.
- `MockAgentID`: open-mint ERC-721 registry used only for local tests and demos.
- `contracts/test`: unit, fuzz, rarity-distribution and invariant tests.
- `challenges/reentrancy-001`: a deliberately vulnerable training fixture with a sample exploit PoC, sample patch and hidden behavior tests.
- `verifier`: deterministic CLI that checks the PoC before and after the patch, runs hidden tests and emits the AxVigil result JSON.
- `backend`: EIP-712 bridge that signs `MintAuth` only for a passed verifier result; it does not submit transactions.
- `contracts/test/VerifierMintIntegration.t.sol`: verifies that the signed verifier hash reaches the mint event and that collectible + skill state are created together.

The agent, backend and web layers are described in [`SPEC.md`](SPEC.md) and are being built as separate demo components.

## Contract flow

1. The Agent ID owner completes a vulnerability challenge.
2. The verifier produces a canonical submission hash and pass/fail result.
3. A backend signer creates an EIP-712 `MintAuth` authorization.
4. The Agent ID owner calls `mint` with the authorization and signature.
5. AxVigil mints the collectible and updates the Agent ID's skill record atomically.
6. Collectible rarity can be revealed later using the demo commit-reveal flow.

The contract intentionally uses `_mint`, not `_safeMint`, so the mint path has no receiver callback. Skill records follow the Agent ID registry owner and cannot be transferred independently.

## Quick start

Install [Foundry](https://book.getfoundry.sh/getting-started/installation), initialize the submodules, then run:

```bash
git submodule update --init --recursive
cd contracts
forge build
forge test --no-match-test test_productionFullSupply
```

The full production-supply distribution test mints and reveals all 7,777 tokens and is intentionally heavier:

```bash
forge test --match-test test_productionFullSupply
```

See [`contracts/README.md`](contracts/README.md) for the contract interface, deployment parameters, rarity rules, limitations and BSC testnet deployment instructions.

## Run the first verifier demo

The repository now includes a complete reentrancy vertical slice. With Foundry and the Python dependency installed:

```bash
pip install -r verifier/requirements.txt
python -m verifier.verifier \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol \
  --json
```

The verifier requires the PoC to pass against the vulnerable baseline, fail after the patch, and leave the hidden tests passing.

The Foundry integration test then checks the contract-side handoff: a valid `MintAuth` mints the collectible, emits the verified `submissionHash`, and records the reentrancy solve on the soulbound skill record. A tampered hash is rejected as an invalid signature.

For a one-command local demonstration of all three layers, run:

```bash
./scripts/demo_pipeline.sh
```

The script uses a deterministic demo-only signer key, never submits a transaction, and runs the verifier, EIP-712 signer and Foundry integration test in sequence.

## Run the local-chain demo

To deploy the contracts and send a real mint transaction on a temporary Anvil chain:

```bash
./scripts/local_anvil_demo.sh
```

This flow starts chain ID `31337`, runs the verifier, passes its `submissionHash` into a Foundry deployment script, deploys `MockAgentID`, `AxVigilSkill` and `AxVigilCollectible`, creates Agent ID `1`, signs `MintAuth`, and broadcasts `mint()`. The script prints the contract addresses, token ID and skill solve count. The private key is Anvil's first deterministic local-only account and must never be used on a public network.

For BSC testnet deployment, first run [`scripts/bsc_preflight.sh`](scripts/bsc_preflight.sh) with a dedicated testnet wallet. The full wallet, faucet, deployment and post-deployment checklist is in [`docs/bsc-testnet-deployment.md`](docs/bsc-testnet-deployment.md).

## BSC testnet deployment (chain 97)

The first public testnet deployment is live. The deployment uses the demo-only `MockAgentID` registry and a 50 mint-per-hour cap. No seed batch was committed yet, so the owner must commit a seed before a mint can be demonstrated.

| Contract | Address | Explorer |
|---|---|---|
| MockAgentID | `0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e` | [view](https://testnet.bscscan.com/address/0x7Aa441477f0246353bdAe504cF0F9B3027D6d45e) |
| AxVigilSkill | `0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593` | [view](https://testnet.bscscan.com/address/0xaCd74265DcFc516bD81d9E7173a57ddEdBD3a593) |
| AxVigilCollectible | `0xFDc7744074d49e9049B82A7CCc76824f75f80437` | [view](https://testnet.bscscan.com/address/0xFDc7744074d49e9049B82A7CCc76824f75f80437) |

The full public deployment record, including transaction hashes, is [`deployments/bsc-testnet-97.json`](deployments/bsc-testnet-97.json).

The collection art plan is documented in [`docs/prd-v1.4-asset-pipeline.md`](docs/prd-v1.4-asset-pipeline.md): Muse Image creates a small Aki source set, while a deterministic local compositor produces the 7,777 final images and metadata. This preserves character consistency, keeps generation cost low and binds the verified vulnerability class to the visual effect.

The first live testnet demo has also completed successfully: verifier `reentrancy-001` passed, Agent ID `1` was created, and Collectible token `1` was minted to the deployer. `AxVigilSkill.totalSolves(1)` is `1` and `currentBatch` is `1`. The three live-demo transactions are [commit seed](https://testnet.bscscan.com/tx/0x493ac2cb71504cb643f95c8e1b3a2a7dd53cc33e95428d6cc8297138e100155b), [create Agent ID](https://testnet.bscscan.com/tx/0xc125505638e6562e965977610cbad7a0cfc6f3579c38f3660c24a578a73f5ecd), and [mint collectible](https://testnet.bscscan.com/tx/0xf78ae69add796a107302aaafc178c0b45c4c5936ebcb5ebe47c58f3836b14fce). The reusable script is [`contracts/script/BscLiveDemo.s.sol`](contracts/script/BscLiveDemo.s.sol); its seed is generated and retained locally, never committed.

Token `1` was then revealed successfully. It is `REENTRANCY`, tier `COMMON`, with `artId = 0` and `tokenURI = "0"` (the deployment currently has an empty base URI). The [seed reveal transaction](https://testnet.bscscan.com/tx/0x4a0cb0039cd88c8573cab7bd30a909c2d601036f2607b516dc62abe34f407733) and [token reveal transaction](https://testnet.bscscan.com/tx/0xe17d8f2ea32ee87698bc5367aca087ebb12a841083cd2416111aea525dba6401) are recorded in the deployment manifest.

Once a result has `passed: true`, the backend bridge binds its `submissionHash` into the contract's EIP-712 authorization:

```bash
pip install -r backend/requirements.txt
export AXVIGIL_SIGNER_PRIVATE_KEY=0x...
python -m backend.mint_auth --result verifier-result.json \
  --agent-id 1 --to 0xYourAgentOwner --chain-id 97 \
  --verifying-contract 0xYourAxVigilCollectible \
  --nonce 1 --deadline 1790000000
```

## Security and demo scope

This is a hackathon prototype for a BSC testnet/whitehat sandbox. It is not audited and should not be used with production funds. The demo commit-reveal randomness has known owner/validator influence and liveness limitations; the production plan is to replace it with Chainlink VRF v2.5. Admin powers, metadata mutability and skill revocation are documented in [`contracts/README.md`](contracts/README.md).

## License

MIT
