# AxVigil contracts (Foundry)

Hackathon demo contracts for AxVigil on BSC testnet (chainId 97). The binding interface is
`../SPEC.md`. Product context is in the PRD (v1.3).

| File | What it is |
|---|---|
| `src/AxVigilCollectible.sol` | Tradeable ERC-721. EIP-712 `MintAuth` mint, fixed tier pools, staged release, commit-reveal rarity, per-agent quota, hourly cap, pause |
| `src/AxVigilSkill.sol` | ERC-5192 soulbound skill record, one per Agent ID, ownership proxied to the Agent ID registry, on-chain SVG |
| `src/MockAgentID.sol` | Open-mint ERC-721 standing in for the SPACE ID Agent ID registry (testnet/tests only) |
| `src/interfaces/*` | `IAgentRegistry` (ownerOf), `IERC5192`, `IAxVigilSkill` |
| `script/Deploy.s.sol` | BSC testnet deploy (not run) |
| `test/*` | Unit, fuzz and invariant tests |

## Setup and tests

```bash
curl -L https://foundry.paradigm.xyz | bash && ~/.foundry/bin/foundryup
git submodule update --init --recursive      # forge-std + OpenZeppelin v5.4.0
cd contracts
forge build
forge test                                    # all tests, ~35 s (one test mints the full 7,777)
forge test --no-match-test test_productionFullSupply   # quick run, ~1 s
forge test --gas-report
```

`foundry.toml` raises the test `gas_limit` because `test_productionFullSupply` mints and reveals
all 7,777 tokens in one test.

Rough gas (from `--gas-report`): `mint` ~225k–360k (the first mint for an agent also creates
its skill record), `revealTokens` ~50–75k per token, `commitSeed` ~70k, skill `tokenURI` view ~270k.

## Interface summary

**EIP-712.** Domain `{name: "AxVigil", version: "1", chainId, verifyingContract: AxVigilCollectible}`.

```
MintAuth(uint256 agentId,address to,uint8 vulnClass,uint8 difficulty,uint8 pool,bytes32 submissionHash,uint256 nonce,uint256 deadline)
```

`hashMintAuth(auth)` returns the digest, so the backend can check its own encoding against the contract.

**`mint(MintAuth auth, bytes signature)`** checks, in order:
1. not paused
2. `block.timestamp <= deadline`
3. nonce never used (nonces are global, not per agent)
4. fields in range
5. `to != 0`
6. signature recovers to `signer`
7. `agentRegistry.ownerOf(agentId) == msg.sender`
8. fewer than 2 mints for this agentId, ever
9. supply left
10. hourly cap not reached
11. a seed batch is open

The one call then:
- mints token `totalMinted + 1` to `to` (`_mint`, so there is no receiver callback),
- calls `skill.recordSolve(agentId, vulnClass, difficulty)`, which creates or updates the record.

If the skill record has been revoked, the whole mint reverts.

**Per-token storage:** `tokenData(id)` returns `vulnClass, difficulty, pool, tier, revealed, batchId, artId, entropy`. Also available: `agentOfToken(id)`, `vulnClassOf(id)`, `tierOf(id)` (reverts until revealed).

**tokenURI** is `unrevealedURI` before reveal, then `baseURI + artId` (no extension).
`artId = tier*100000 + vulnClass*10000 + index`, where `index` counts up from 0 within each
(tier, vulnClass) bucket in reveal order. Examples: `0` is the first Common in Reentrancy, and
`420003` is the 4th Hidden in Access Control. The art pipeline should produce, for each
(tier, vulnClass) bucket, up to `tierTotal(tier)` images and metadata files named by artId.
`setProvenanceHash(h)` commits to the hash of the whole generated set and can be called once.

**Tiers** `0 COMMON 5444, 1 RARE 1555, 2 EPIC 622, 3 LEGENDARY 152, 4 HIDDEN 4` (constructor params; `maxSupply` is immutable and is their sum, 7,777). `drawableSupply` is the public tiers only (7,773). `mint` closes when `totalMinted - hiddenDrawn` reaches that public quota, or when `totalMinted` reaches `maxSupply`. A revealed Hidden piece does not consume a public slot.

**Staged release.** Draw index `i` sits in stage `i*4/drawableSupply` (0..3). LEGENDARY has `total*(stage+1)/4` released, so it goes 38 → 76 → 114 → 152 across the public supply. Hidden is not stage-gated and is not in the weighted ladder. The constructor rejects a config where a legendary stage could empty the public pool.

**Pools.** The pool is the difficulty, and `mint` reverts with `PoolDifficultyMismatch` if they differ.

| Difficulty | Pool | Multipliers (Common, Rare, Epic, Legendary) | Hidden |
|---|---|---|---|
| 0 BASIC | 0 | 1, 1, 1, 1 | never |
| 1 ADVANCED | 1 | 1, 2, 4, 8 | never |
| 2 LEGENDARY | 2 | 1, 3, 8, 16 | fixed 25/10000 (0.25%), and only while a piece remains |

The Hidden roll is `rand % 10000 < 25` on pool 2, before the weighted ladder. It does not use remaining counts, so the chance stays 0.25% as other tiers deplete, strictly below 0.30% (`MAX_HIDDEN_CHANCE_BPS`). On a hit, one of the 4 Hidden pieces is taken without replacement and the public ladder is skipped for that token. On a miss, the public ladder runs as before. If the public ladder is empty, reveal stops instead of forcing Hidden or reverting. Hidden does not reduce the 7,773 public pieces: after a Hidden reveal, another public mint is still available, up to 7,777 total. Hidden that is never rolled stays unminted. Quotas are exact ceilings and are never exceeded. At the first production draw the legendary-tier share of the public ladder is about 0.50% / 2.68% / 3.87% across the three pools (`contracts/test/Rarity.t.sol`).

**Skill record.** `mint` calls `skill.recordSolve` once. There is no second entry point, so `totalSolves` equals the number of successful mints for that Agent ID and cannot pass 2.

**Skill record (`AxVigilSkill`):**
- `tokenId == agentId`, and `ownerOf` returns `agentRegistry.ownerOf(agentId)`.
- `locked()` is always true. Transfers and approvals revert (`Soulbound`), and `balanceOf` reverts (it cannot be computed when ownership lives in the registry).
- Views: `solvesOf(agentId, class)`, `classCounts`, `maxDifficulty`, `totalSolves`, `getRecord`, `exists`, `isRevoked`, `revokeReason`.
- Admin: `revoke(agentId, reason)` wipes the record and permanently blocks that agentId here.
- Only `MINTER_ROLE`, which is the Collectible contract, can call `recordSolve`.
- `tokenURI` is base64 JSON with an SVG. It has a frame coloured by max difficulty and one emblem per solved class: a loop for Reentrancy, a price spike for Price Manipulation and a key for Access Control. Unsolved classes show as dashed placeholders.

## Operating the commit-reveal (owner)

```text
seed      = random 32 bytes kept offline
seedHash  = keccak256(abi.encodePacked(seed))   # cast keccak <seed>
commitSeed(seedHash)        -> opens batch N; mints now join batch N (closes batch N-1)
... users mint ...
commitSeed(nextHash)        -> optional: rotate to a new batch
revealSeed(N, seed)         -> verifies the hash; if N is still open it is closed first
revealTokens(200)           -> anyone; draws tiers in tokenId order, call repeatedly
```

Do not reveal a seed while its batch is open. `revealSeed` closes it for you, so minting pauses
with `NoOpenBatch` until you commit the next one. Reveal in chunks of roughly 100–300 tokens per
transaction to stay under the block gas limit.

### Randomness: the commit-reveal caveat (please read)

This is hackathon-grade randomness, not VRF. Each token's tier comes from
`keccak256(seed_of_its_batch, keccak256(blockhash(n-1), prevrandao, tokenId, to))`. Its
properties:

- **Users can't predict or re-roll.** The seed is secret while they mint. After the seed is
  revealed, nobody can mint into that batch. Draws use fixed pools and run in tokenId order.
- **The owner/seed holder can predict outcomes.** Whoever knows the seed can simulate mints
  block by block. If the owner also controls the signer, they could mint themselves only in
  favourable blocks. Validators can also nudge `prevrandao`/blockhash a little. Mitigation for
  the demo: keep the seed separate from the signer key, and publish all seed hashes up front.
- **Liveness depends on the owner.** If the owner never reveals a batch (or loses its seed),
  those tokens and every later one stay unrevealed, because reveal is strictly in order. There
  is no timeout fallback.
- **Draw order is mint order, but tiers depend on the seed.** Staged release is enforced by
  draw index, which equals mint index.
- **Mainnet plan (PRD):** Chainlink VRF v2.5. One request per batch or one shuffle of the
  remaining pool, which replaces `commitSeed`/`revealSeed`.

## Deploy (BSC testnet, not executed here)

```bash
cp .env.example .env    # fill PRIVATE_KEY (testnet), SIGNER, optional OWNER / AGENT_REGISTRY / URIs / SEED_HASH
source .env
forge script script/Deploy.s.sol --rpc-url bsc_testnet --broadcast
# optional verification: add --verify --etherscan-api-key $BSCSCAN_KEY
```

What the script does:
- It refuses any chain other than 97.
- If `AGENT_REGISTRY` is unset, it deploys `MockAgentID`.
- It deploys Skill, then Collectible with the production tier counts, and grants the Collectible `MINTER_ROLE`.
- It optionally sets URIs and commits the first seed.
- If `OWNER` differs from the deployer, it hands over admin and ownership. Ownership uses Ownable2Step, so `OWNER` must call `acceptOwnership()`.

A local dry run without any RPC works:

```bash
PRIVATE_KEY=<any test key> SIGNER=0x...dEaD forge script script/Deploy.s.sol --chain-id 97
```

## Known limitations

- Randomness: see the caveat above.
- The owner can change `baseURI` and the hourly cap. Neither can change supply or tiers.
  There is no `freezeMetadata`, so `provenanceHash` is the integrity anchor.
- Skill ERC-721 compatibility is partial. `balanceOf` reverts, and `Transfer` events only
  reflect the owner when a record was created or revoked, because later Agent ID transfers
  happen in the registry. Indexers should read `ownerOf`.
- Revoking a skill record does not burn collectibles already minted, which are tradeable assets.
  It does block further mints for that Agent ID.
- `submissionHash` is signed, emitted, and rejected on a second use (`SubmissionUsed`).
  A solved challenge can drive one mint.
- Art `index` within a bucket is sequential in reveal order. Randomness lives in the tier draw,
  not in which image within a bucket.
