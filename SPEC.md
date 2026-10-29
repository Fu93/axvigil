# AxVigil hackathon demo — build spec (shared by all builders)

Deadline: Meta Global AI Developer Hackathon, 2026-11-04 21:00 ET. Chain: BSC testnet (chainId 97). Whitehat, sandbox only.
This file is the repo-local contract for the demo. The longer product PRD is not shipped in this repository. The v1.4 asset pipeline addendum is `docs/prd-v1.4-asset-pipeline.md`.

## Monorepo layout (/workspace/axvigil)
- contracts/   Foundry project: AxVigilSkill (ERC-5192), AxVigilCollectible (ERC-721), MockAgentID for tests
- challenges/  3 parent challenges + template variant generator
- verifier/    deterministic sandboxed grader (Python CLI)
- agent/       Muse Spark solver loop (later; needs Meta API key)
- backend/     FastAPI: login, start challenge, submit, sign mint authorization (later)
- web/         static demo page (later)

## Shared interfaces
Vuln classes (uint8): 0 REENTRANCY, 1 PRICE_MANIPULATION, 2 ACCESS_CONTROL.
Difficulty: 0 BASIC, 1 ADVANCED, 2 LEGENDARY.
Pool: 0 NORMAL, 1 PREMIUM (hard + fast solve).

Verifier result JSON (stdout of `python -m verifier grade ...`):
{ "challengeId": str, "seed": int, "vulnClass": int, "difficulty": int,
  "pocProvesBug": bool, "pocFailsAfterPatch": bool, "hiddenTestsPass": bool,
  "patchWithinLimits": bool, "passed": bool, "solveSeconds": int|null,
  "submissionHash": "0x..." (keccak256 of canonical patch+poc), "log": str }

EIP-712 MintAuth (domain name "AxVigil", version "1", chainId, verifyingContract = AxVigilCollectible):
MintAuth(uint256 agentId,address to,uint8 vulnClass,uint8 difficulty,uint8 pool,bytes32 submissionHash,uint256 nonce,uint256 deadline)
One signature mints BOTH: a collectible NFT to `to`, and records/updates the skill record for agentId.

Agent ID: SPACE ID .ai Agent ID registry on BSC mainnet 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F (ERC-721-like, ownerOf(tokenId)). On testnet use MockAgentID (simple ERC-721) with same ownerOf interface.

## Fixed rules
- Max 2 collectibles per Agent ID tokenId, lifetime. Quota bound to tokenId, not wallet.
- Mints and skill solves are 1:1. `mint` is the only way a solve is recorded. There is no mint-free `recordSolve` entry point. One `submissionHash` can mint once. A third mint reverts.
- Reward challenges are server-assigned. Opening a reward session consumes one of two lifetime attempts even if it is abandoned. The pool signed in `MintAuth` must equal `difficulty` (0 basic / 1 advanced / 2 legendary).
- Public rarity draw is Common, Rare, Epic, and Legendary (5444/1555/622/152), without replacement. Higher pools raise the weight of rarer public tiers (`[1,1,1,1]`, `[1,2,4,8]`, `[1,3,8,16]`) and never guarantee a tier.
- Hidden (4) is drawable only from pool 2, by a fixed roll of 25/10000 (0.25%), strictly below 0.30%. The chance does not depend on remaining counts. Pools 0 and 1 never draw it. `mint` stops at the 7,773 public pieces; a Hidden hit uses one of those slots, and any Hidden that is not rolled stays unminted.
- Total supply configured as 7,777 = those tiers. Legendary is released in 4 equal stages across the public supply. Hidden is not stage-gated.
- Hourly mint cap; pausable; rotatable signer; supply cannot increase.
- Hackathon randomness: commit-reveal (no VRF).
- Skill record: non-transferable (ERC-5192 locked), bound to Agent ID tokenId, revocable by admin, records counts per vulnClass and max difficulty; tokenURI on-chain SVG that grows with each new vuln class.
- No token, no yield promises.
