# Deploying AxVigil

Two paths: a **local devnet** (anvil) that needs nothing external, and **BSC testnet**
(chainId 97) which needs a funded test key. The contracts refuse any chain other than 97.

> For the authoritative BSC testnet checklist (faucet, preflight, verification) and the
> live deployment record, see [`docs/bsc-testnet-deployment.md`](docs/bsc-testnet-deployment.md)
> and [`deployments/bsc-testnet-97.json`](deployments/bsc-testnet-97.json). This file adds
> the local-devnet path and the `LiveFlow` lifecycle (which also exercises the
> `recordSolve` third-class path).

## Local devnet — full lifecycle in two commands

Proves deploy → two mints → a skill-only 3rd class → commit-reveal → tier draw, all on a
live chain, with no faucet and no network.

```bash
# 1. a local chain at BSC testnet's chainId
anvil --chain-id 97 &

# 2. deploy + run the whole lifecycle (uses anvil's built-in funded keys)
cd contracts
forge script script/LiveFlow.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
```

`LiveFlow.s.sol` prints the deployed addresses and the resulting state (tiers drawn,
`classCounts` reaching `[1,1,1]`, `maxDifficulty` LEGENDARY). To read the on-chain skill art:

```bash
SKILL=<AxVigilSkill address from the script output>
cast call $SKILL "tokenURI(uint256)(string)" 1 --rpc-url http://127.0.0.1:8545
# base64-decode the data:application/json, then the image's data:image/svg+xml
```

## BSC testnet (chainId 97)

```bash
# 1. a throwaway key with testnet BNB
cast wallet new                      # note the address + private key
#   fund it at the BSC testnet faucet (e.g. https://testnet.bnbchain.org/faucet-smart)

# 2. configure
cd contracts
cp .env.example .env
#   PRIVATE_KEY   = the funded testnet key
#   SIGNER        = the backend signer ADDRESS (keep its key off this deployer / off the seed holder)
#   BSC_TESTNET_RPC = https://data-seed-prebsc-1-s1.binance.org:8545   (or another 97 RPC)
#   optional: OWNER, AGENT_REGISTRY, HOURLY_CAP, BASE_URI, UNREVEALED_URI, SEED_HASH
set -a && . ./.env && set +a

# 3. deploy (MockAgentID is deployed automatically if AGENT_REGISTRY is unset)
forge script script/Deploy.s.sol --rpc-url bsc_testnet --broadcast
#   add --verify --etherscan-api-key $BSCSCAN_KEY to verify on BscScan
```

After deploy, set `VERIFYING_CONTRACT` in `backend/.env` to the printed
`AxVigilCollectible` address, start the backend, and the signer it uses must equal the
`SIGNER` address above. The agent (`agent/`) solves challenges and the backend signs the
resulting `MintAuth`/`SkillAuth`; the Agent ID owner submits them.

### Operating commit-reveal (owner)

```bash
SEED=$(cast keccak "some-random-string")          # keep this secret until reveal
cast send $NFT "commitSeed(bytes32)" $(cast keccak $SEED) --private-key $OWNER_KEY --rpc-url $RPC
# ... users mint into the open batch ...
cast send $NFT "revealSeed(uint32,bytes32)" 1 $SEED --private-key $OWNER_KEY --rpc-url $RPC
cast send $NFT "revealTokens(uint256)" 200        --private-key $OWNER_KEY --rpc-url $RPC
```

`revealSeed` closes the batch, so minting pauses with `NoOpenBatch` until the next
`commitSeed`. Reveal tokens in chunks of ~100–300 to stay under the block gas limit.

## Red lines

Fork or testnet only, never real funds. The challenge contracts are intentionally
vulnerable teaching toys — do not deploy them to mainnet. Keep the signer key separate
from the owner/seed key: whoever holds the commit-reveal seed can predict rarity.
