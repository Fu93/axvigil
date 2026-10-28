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

**Tiers** `0 COMMON 5444, 1 RARE 1555, 2 EPIC 622, 3 LEGENDARY 152, 4 HIDDEN 4` (constructor params; `maxSupply` is immutable and is their sum).

**Staged release.** Draw index `i` (0-based, equal to tokenId-1) sits in stage `i*4/maxSupply` (0..3).
LEGENDARY and HIDDEN have `total*(stage+1)/4` released, so Legendary goes 38 → 76 → 114 → 152
and Hidden goes 1 → 2 → 3 → 4. The first stage is open from token #1. This is our reading of
"1 per 25%": with exactly 4 Hidden, waiting until 25% for the first would make the last one
unreachable. The constructor rejects any config where a stage could run out of released tokens.

**Pools.** NORMAL weights each tier by its remaining released count, which is a uniform draw
without replacement. PREMIUM multiplies those weights by `[1,2,4,8,8]` for
COMMON..HIDDEN. That gives better odds, never a guarantee, and it never exceeds a pool or a stage.

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
- `submissionHash` is signed and emitted but not checked for uniqueness on-chain. Uniqueness
  rests on the nonce plus the backend.
- Art `index` within a bucket is sequential in reveal order. Randomness lives in the tier draw,
  not in which image within a bucket.
