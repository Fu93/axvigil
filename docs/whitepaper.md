# AxVigil Whitepaper (v3.1)

> **Every inference, a line of defense.**

**Status discipline (read this first).** This document describes one thing that exists and two that do not yet. **Layer 1 — the Crucible** is built, tested, and live on BSC testnet today. **Layer 2 (defense network)** and **Layer 3 (settlement and orchestration)** are planned. Every forward-looking claim is marked as such. Where this document says "today" it means code in `Fu93/axvigil` at `main`; where it says "planned" or "future" it means design intent, not shipped software.

**No token has been issued.** Nothing in this document is an offer to sell a token or a solicitation to invest. Points are an off-chain score with no monetary value. The collectible carries no financial rights. A later utility-token design, and the fee model that is meant to fund the project without one, are in §8. Both are planned, not built.

---

## 0. Positioning

**Every inference, a line of defense.**

AxVigil wants to spend Web3's AI compute where it actually matters. There is an absurd pattern right now: more and more projects send AI agents to solve math problems and compute hashes, only to mint an NFT or mine a new token. The compute is burned, and the chain is no safer. At the same time, the crypto industry loses billions of dollars to theft every year — more than $3.4 billion in 2025. The largest hauls mostly come from private keys and infrastructure being broken, but smart-contract code bugs are still the most frequent attack type. In 2025 that category alone caused about $350 million to $500 million in real losses, and AI is making attacks cheaper and faster. AxVigil points this compute at that real pain: AI agents patch contracts inside a vulnerability sandbox that is reshuffled every time, three validators re-grade, and at least two signatures must agree. Every successful patch leaves an on-chain capability record anyone can recompute. When a protocol chooses an AI scanning tool, it can check these records instead of listening to an advertisement. We do not issue an empty token, and we do not run a zero-sum game. We only want each AI inference to take one more step toward protecting on-chain assets.

The three validators are currently permissioned and run by the team. An open validator set is planned, not live. Muse Spark (`muse-spark-1.1`) is the first model with public records on AxVigil. That is not a ranking.

### Sources for the 2025 figures

- Chainalysis, [2025 Crypto Theft Reaches $3.4 Billion](https://www.chainalysis.com/blog/crypto-hacking-stolen-funds-2026/): more than $3.4 billion stolen from January through early December 2025. The largest service losses are concentrated in a few attacks on private-key infrastructure and signing.
- TRM Labs, [2026 Crypto Crime Report](https://www.trmlabs.com/reports-and-whitepapers/2026-crypto-crime-report): code exploits were the most frequent hack category in 2025 (52 incidents) and accounted for $350 million. Infrastructure attacks (keys, wallets, privileged access) were $2.2 billion across 45 incidents.
- Hacken, [2025 Yearly Security Report](https://assets.hacken.io/assets/Hacken-2025-Yearly-Security-Report.pdf): smart-contract vulnerabilities accounted for $512 million. The "$350 million to $500 million" range in the paragraph above is the span of the TRM code-exploit total and the Hacken smart-contract total, rounded.

The near-term product is the Crucible. Sections below keep the technical body and the sustainability model in §8. On-chain facts match `main`.

---

## 1. What a passing record is

A plausible patch is not a fix. An agent is dealt a reshuffled vulnerable contract, submits a patch and a proof of concept, and a deterministic sandboxed grader confirms the exploit worked before the patch and fails after, without breaking the contract. Pass, and the chain writes a verifiable capability record bound to the agent's identity.

| Item | Today (built) | Planned |
|---|---|---|
| Core | The Crucible: deal a fresh rewrite, the agent patches, a deterministic grader checks, an on-chain capability record is written | Defense network: automated review, continuous monitoring, bounty scanning |
| Record | `AxVigilSkill` — ERC-5192 record bound to an Agent ID | the record is what a protocol can check before it trusts a scan |
| Verification | five-check grader plus anti-memorization fresh rewrites | multi-node re-run |
| Economy | off-chain points with no monetary value; no token issued | stablecoin or fiat fees (§8.2); a utility token only if the §8.3 triggers are met |
| Deployment | BSC testnet (chain 97) | mainnet, only after the earlier phases |
| Challenge source | only patched, publicly disclosed bugs, reshuffled by `variantgen` | sponsored challenges; private eval with responsible disclosure |

---

## 2. The problem

### 2.1 Compute layer — AI reasoning is being wasted

Through 2025–2026, agent code-reasoning capability grew fast, and a large share of Web3 pointed it at **zero-sum games with no social value**: SAT/boolean-satisfiability puzzles, prime hunts, puzzle runs, repeated benchmark screenshots — each burning real GPU time to mint a "proof" that protects nobody. **Compute spins; the real-world security gap widens.**

### 2.2 Security layer — contract defense is badly under-supplied

| Pain | Reality |
|---|---|
| Loss scale | DeFi exploits have cost billions over recent years |
| Audit supply | top firms book months out at five- to six-figure cost |
| Coverage gap | most newly deployed small/mid protocols have no audit budget and ship exposed |
| Response speed | audits are static/point-in-time; continuous post-deploy monitoring is near zero |
| AI unused | AI can produce plausible patches, but there is no trusted verification or dispatch layer |

### 2.3 Infrastructure layer — no bridge from compute to security

Even for those who want to use AI for security:

1. **Capability can't be verified** — "security skill" rests on benchmark screenshots or self-report, with no independently re-runnable evidence.
2. **Challenges get memorized** — public problem sets enter training data fast; fixed challenges measure recall, not repair.
3. **Capability records bind to the wrong thing** — capability should belong to the agent, not a wallet.
4. **Authors aren't rewarded** — whitehats' curated bug patterns get reused with no ongoing return.
5. **Everyone rebuilds the harness** — each team builds its own sandbox, sources its own challenges, fights its own cheating.
6. **No path from exam to battlefield** — even a proven agent has no network to actually protect real assets.

**The core problem AxVigil addresses: build a trustworthy mechanism that moves AI compute from "spinning on puzzles" toward "defending real contracts" — starting with the verification that makes any such claim credible.**

---

## 3. Solution & positioning

### 3.1 Positioning

AxVigil is **trust and dispatch infrastructure for security AI**. Not another benchmark, not another audit shop, not another NFT drop.

- To AI teams: a proving ground today, a job board tomorrow.
- To protocols: an automated line of defense (roadmap).
- To whitehat authors: knowledge that keeps paying out.
- To the ecosystem: a converter from idle compute into a security public good.

### 3.2 Three-layer architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — Settlement & Orchestration (The Engine)  [roadmap] │
│  task dispatch · bounty settlement · reputation · protocol onboarding
├─────────────────────────────────────────────────────────────┤
│  Layer 2 — Defense Network (The Shield)             [roadmap] │
│  automated first-pass review · continuous monitoring · bounty scanning
├─────────────────────────────────────────────────────────────┤
│  Layer 1 — Passing record (The Crucible)        ← BUILT, LIVE  │
│  anti-memorization challenges · deterministic sandbox · soulbound capability record
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Components by layer

| Layer | Function | Component | State |
|---|---|---|---|
| **L1 — Crucible** | identity | Agent ID (SPACE-ID-style ERC-721 registry) | built |
| | challenge library | `variantgen/` and the family-template directory (9 vulnerability families × 20 fresh rewrites) | built |
| | verification | `axvigil_verifier` (5 checks + sandbox) | built |
| | capability record | `AxVigilSkill` (ERC-5192 soulbound) | built |
| | commemorative | `AxVigilCollectible` (ERC-721, free) | built |
| **L2 — Defense** | task dispatch | queue + match engine | roadmap |
| | execution | recorded-agent SDK | roadmap |
| | result review | responsible-disclosure pipeline | roadmap |
| **L3 — Settlement** | bounty payout | USDC settlement | roadmap |
| | service fee | subscription / per-scan billing | roadmap |
| | reputation | Skill revocation on bad behavior | roadmap |

### 3.4 Design principles

1. **Compute must produce real protection** — reward removing a bug, not "solving" per se.
2. **Re-runnable and verifiable** — any result can be independently reproduced.
3. **Challenges are issued, not chosen** — agents can't pick or memorize.
4. **Capability records follow the agent** — bound to Agent ID, not a wallet.
5. **Free to participate, revenue from real budgets** — passing record is free; defense work earns real income.
6. **No speculative token** — operation is meant to be funded by security budgets (§8.2). A token is only the §8.3 design, and none has been issued.

---

## 4. Layer 1 — The Crucible (current system)

### 4.1 Its role in the network

Today's prototype (`Fu93/axvigil`, `main`) implements **Layer 1**. Its job: **ensure an agent entering the defense network has real capability — not compute that would generate false positives and waste protocols' time.** An agent that hasn't passed the Crucible can't reach Layer 2. This is the network's trust root — and it is the hackathon deliverable, working end to end.

### 4.2 Passing record flow (end to end)

```
Backend (FastAPI) ──deal a fresh rewrite (source only)──▶ AI Agent
      ▲                                                     │
      │                      patch + PoC                    ▼
      │                                               Verifier (deterministic sandbox)
      │                                               ① pocProvesBug
      │                                               ② pocFailsAfterPatch
      │                                               ③ hiddenTestsPass
      │                                               ④ patchWithinLimits
      │◀──── EIP-712 MintAuth (only if all pass) ──── ⑤ invariantsHold
      ▼
Agent ID owner submits mint
  → AxVigilSkill (ERC-5192): capability record updated
  → AxVigilCollectible (ERC-721): free commemorative
  → agent is now recorded; eligible for Layer 2 (roadmap)
```

### 4.3 Current components

| Component | Highlights |
|---|---|
| Backend | FastAPI: wallet-signature login with on-chain Agent ID `ownerOf` check; server-dealt challenges; in-session grading; EIP-712 authorization; SQLite; rate limits; answer-leak circuit breaker; difficulty-weighted leaderboard |
| Verifier | zero third-party deps; sandbox is a resource-limited offline subprocess (`ffi` off, no network, wall-clock timeout, POSIX rlimits); forge supplies solc unless `SOLC` pins one |
| Agent | automated solve loop with an offline oracle so judges can reproduce runs |
| Contracts | EIP-712 authorization; `mintedPerAgent` ceiling of 2; hourly cap; pausable; `setSigner` (owner rotates the signer; the signer key only authorizes mints); fixed supply |
| Deployment | BSC testnet (chain 97): Skill `0x3377…CD18`, Collectible `0x0658…4658`, registry `0x7Aa4…d45e` (`MockAgentID`, open mint, not a production Agent ID) |
| Tests | Foundry unit / fuzz / rarity-distribution / invariant / verify→mint integration; Python backend and verifier suites; 315 tests passed, 1 skipped (contracts 122 · Python 193; the Docker image is built and graded in sandbox CI) |

### 4.4 Live proof (Muse Spark mint)

The primary on-chain proof is a **Muse Spark** solve, not the earlier reference-solution smoke test.

| Field | Value |
|---|---|
| Model | `muse-spark-1.1` via `https://api.meta.ai/v1` |
| Challenge | server-dealt `signature-replay` (legendary). Class 2 because `NUM_CLASSES = 3`; signature replay is grouped under access control |
| Model calls | 1 request, 4,947 completion tokens, first try |
| Grade | server hidden-test grade passed |
| Signer at mint time | `0x4E38ec3f38D5c947B60E7e1273890Eea51501Ef8` (deployer). Rotated afterwards to `0x91AeE1253D3EF16864FEfC8EFF3431959c86e081` by [`setSigner`](https://testnet.bscscan.com/tx/0xaea5242f066736eae950daf093a8cfe44e863e2341e97ab4e08e406f1cea2d3b) (30,781 gas). That key is not the owner and not a threshold validator |
| Mint | tx [`0x8f135d51…`](https://testnet.bscscan.com/tx/0x8f135d51462a5a5ad98dc3af3df0838f5f3eabc1207210fc22041f876281c177), block 140439816, 331,623 gas |
| Collectible | token #2 on `0x0658…4658`. After reveal, tier LEGENDARY, artId 320000, `tokenURI` `320000` |
| Skill | token #7, `locked() == true` |
| submissionHash | `0x93eb0753c8c9022acfa604e06a7fa89c4f19b04730c049acba261fce092b7094` (in the `Minted` event: vulnClass 2, difficulty 2, pool 2, batch 2) |
| Batch 2 commit | [`0xc48b3866…`](https://testnet.bscscan.com/tx/0xc48b3866605adac8328dad2bfff467ba9918c2a4c91271d9257c5b12fbaef222) |
| Batch 2 reveal | [`revealSeed`](https://testnet.bscscan.com/tx/0xf83f082999ea63a7bef5f4eacc105e1aa2d648c2be38af1a5ff7fabdb978d597) (77,699 gas) and [`revealTokens`](https://testnet.bscscan.com/tx/0x343f3a8ca91b5c31b5441381900eddf7478e9ed01deeb4e9900338c6273f6ef2) (102,912 gas). Replay matches token #1 (tier 0, artId 20000) and token #2 (tier 3, artId 320000). 0 mismatches |

Secondary, kept in `deployments/bsc-testnet-97.json` under `smokeTest`: a reference solution for a server-dealt legendary session minted token #1 (Agent ID 1). Batch 1 was later revealed as tier COMMON, artId 20000, `submissionHash 0x8083…64df`.

### 4.5 Meta model integration and results

The agent loop is propose → grade → feed the grader log back → retry (`agent/axvigil_agent`). The HTTP client talks to an OpenAI-compatible chat-completions endpoint. Default model `muse-spark-1.1`, default base URL `https://api.meta.ai/v1`. HTTP timeout default is 300s. `META_MAX_TOKENS`, when set, is sent as `max_tokens`; unset means the request does not cap the completion.

| Run | Outcome |
|---|---|
| `bridge-phantom-deposit` seed 7 (contract `Tunnel`), after the PR #11 hint | attempt 0: narrow `address(0)` fix, hidden tests 7/8. attempt 1: `token.code.length > 0`, pass. 16,250 tokens, 45 s, 2 attempts |
| `access-control` seed 1 (role rendered as `custodian`), after the hidden-test fix | pass on the first try. 3,487 tokens, 16 s |
| Server-dealt `signature-replay` on the original collectible | pass on the first try (1 request, 4,947 tokens), then the mint in §4.4, later revealed LEGENDARY artId 320000 |
| Three server-dealt threshold mints on `0x0e87…C8eB` (2-of-3) | each `muse-spark-1.1` pass on the first request. price-manipulation token #1 (5,067 completion / 5,938 total tokens, [mint](https://testnet.bscscan.com/tx/0x720f135e0af68e9dd1b908fc428153cffb0351e173b3b8f9b741b83045d7e3ab), CID `bafkreick5qyty6dxfa6w6p2immr5jg2bj2buvvjvdeohnj7j2eui3fguly`); access-control token #2 (3,336 / 3,992, [mint](https://testnet.bscscan.com/tx/0xf30d90b0f6edddcd61d5674ff2a3bd66592c69a21c11b1158d087d1992505cd1), CID `bafkreib5fwr5qggt3wrxev7u7uhi4tvclkcgjhe4nf4hva7tsmfhhbmbcm`); price-manipulation token #3 (4,560 / 5,491, [mint](https://testnet.bscscan.com/tx/0xfb058e4daeec61cf5a711335a3d61b6bf95faf5e0e1d5b887c33952aad3b11dd), CID `bafkreidtrw73rx3b6rdvdl32qxlusrggsbijrfhdmnhofhch6zodaqzpoe`). All three validators signed each session; 2 signatures were submitted. `verify_evidence.py` OK on all three. Grading used the subprocess sandbox, not Docker |
| Same bridge seed 7 before the hint change | 5 attempts, all stuck at hidden 7/8, because the retry text said to keep the fix minimal |

**Failure analysis (two benchmark bugs, both fixed in PR #11).**

1. Hidden-test failure text said the patch had changed intended behaviour and to keep the fix minimal. A correct class diagnosis (phantom deposit) was then patched only for `token == address(0)`. `test_codelessNonZeroTokenCannotPhantomDeposit` rejects that. The hint now says the failure is either changed behaviour or an incomplete class fix, and it does not name the hidden test or the `code.length` repair.
2. the access-control hidden-test template required the revert string `"not owner"`. Rendering renames the role (`custodian`, `manager`, …) and that string is not in the vulnerable source, so a correct `"not custodian"` revert was a false fail. The hidden test now accepts any revert from an unauthorized caller.

### 4.6 Trust model and threat model

What a pass means: one sandboxed grader, on one machine, accepted one patch against one rendered fresh rewrite. The `Minted` event's `submissionHash` commits to `(challengeId, seed, patch, PoC)` under the canonical encoding in `verifier/axvigil_verifier/keccak.py`. It does not, by itself, prove that a second implementation of the grader would agree, or that the signer key was not the same key as the owner.

| Actor | Can | Cannot |
|---|---|---|
| Agent | read the rendered source; submit a patch and a PoC | read the seed, the hidden tests, or the reference fix from the API (the tests are public in the git repo) |
| Backend signer | sign `MintAuth` for a session this process marked passed | mint by itself; change tiers; rotate itself |
| Contract owner | `setSigner`, `commitSeed`, `revealSeed`, pause, set URI | forge a `MintAuth` once the signer has been rotated to a different key |
| Anyone | recompute `submissionHash` from an evidence bundle and re-run `scripts/verify_evidence.py` | recover a batch seed before `revealSeed` |

The sandbox that graded the live BSC runs, including the three threshold mints, was the resource-limited offline subprocess: `ffi` off, `FOUNDRY_OFFLINE`, a wall-clock timeout, and POSIX `rlimit` on CPU, address space, file size, and process count. Docker was not installed on that historical machine and was not used. `AXVIGIL_SANDBOX=docker` is implemented (`verifier/docker/Dockerfile`, image `axvigil-sandbox:1.8.7`: `--network none`, read-only root, uid 1000, CPU/memory/pid limits, tmpfs workdir) and is now built and exercised by `.github/workflows/sandbox.yml`. Unset or `subprocess` remains the compatibility runner; Docker is the recommended mode for new untrusted grades. Neither mode is a TEE or a zkVM.

Known false-pass gap: **none known** on the two real-incident vulnerability families after the negative controls (an `address(0)`-only bridge patch, and `require(shares > 0)` on the vault, both fail). That is not a proof that no other false-pass exists.

### 4.7 Decentralisation roadmap

**On BSC testnet now:**

- Key separation on the original collectible `0x0658…4658`: signer is `0x91Ae…e081`, set by [`0xaea5242f…`](https://testnet.bscscan.com/tx/0xaea5242f066736eae950daf093a8cfe44e863e2341e97ab4e08e406f1cea2d3b). Owner remains `0x4E38…1Ef8`.
- Threshold collectible [`0x0e8755245231b66FdcE3a625b764dc1Bb597C8eB`](https://testnet.bscscan.com/address/0x0e8755245231b66FdcE3a625b764dc1Bb597C8eB), skill [`0xE165C8B4826b6eF7aE84dfe3B1b27017aF1b5F59`](https://testnet.bscscan.com/address/0xE165C8B4826b6eF7aE84dfe3B1b27017aF1b5F59). Threshold 2 of 3. Validators `0xc32d…95F9`, `0xD5f5…4645`, `0x133F…ec7f`. Owner `0x94aC…f6E9` is not a validator. Deploy [`0xd3717767…`](https://testnet.bscscan.com/tx/0xd3717767483596a9aeba2ceea15a7613d227344e93d077b17db7c57540aaac4b). Three Muse Spark mints are in §4.5. Grading was subprocess, not Docker.
- Evidence bundles: each of those three submits has a CID, and `scripts/verify_evidence.py` returned OK (CID, submissionHash, seed commitment, forge re-grade).
- Batch 2 on the original collectible is revealed. Replay mismatches: 0. Seed is public on-chain (`0xb1f8de1b…7f6b`).

**After the deadline (not built):**

- Staking and slashing on top of the threshold prototype (the k-of-n check itself is in this repo; stake is not).
- TEE or zkVM attested grading.
- On-chain attempt quotas (today the attempt cap is backend state; the contract caps mints at 2) and an ERC-8004-style identity instead of `MockAgentID`.
- An on-chain bounty market.

### 4.8 Limitations and known issues

- On the original collectible the signer is now a dedicated key. The owner is still the deployer address. On the threshold collectible the owner is a different address and is not a validator.
- Batch 2 on the original collectible is revealed (token #2 is LEGENDARY, artId 320000). The three threshold-collectible tokens are still `ipfs://unrevealed.json` because that contract's batch seed has not been revealed.
- The Docker sandbox is in the repo and was not used for the live grades.
- `MockAgentID` is an open mint. It is not the SPACE ID Agent ID registry.
- The backend refuses a third reward session. The contract reverts a third mint. They are not the same counter: an abandoned session spends a backend attempt and does not mint.
- Skill art can show a new emblem per class passed, but a single Agent ID can record at most two solves, because each solve is written by a mint and mints are capped at two.
- Hidden tests are withheld from the session payload and are public in the hidden-test templates in the family-template directory.
- Author revenue share, commercial eval stake or fee, and B2B scan billing are roadmap. They are not implemented.
- The offline verify command checks 20 unique fresh rewrites per vulnerability family (180 total). Live dealing now also reference-checks the dealt seed and skips a repeated structural fingerprint. It does not pre-publish an exhaustive list of every future seed.

---

## 5. Challenge library & anti-memorization engine

### 5.1 Why anti-memorization is the prerequisite

If an agent merely memorized answers, it is **dead weight** in the defense layer — it can't recognize new fresh rewrites in the wild. The Crucible's core value is ensuring every recorded agent has **generalizable** repair capability, not recall of specific problems.

### 5.2 `variantgen` — the anti-memorization engine

Each vulnerability family is one vulnerability template. Per seed, `variantgen` renames identifiers, injects distractor functions and reorders bodies. A structural fingerprint treats rename-only copies as the same fresh rewrite. The offline verify command discards those look-alikes while it builds the 20-variant bank. The live server does the same check before it returns source: it skips a fingerprint it has already issued, and when `AXVIGIL_REFERENCE_CHECK` is on (the default for `Settings.from_env`) it grades the reference solution before dealing. The agent must fix the class of bug.

| Vulnerability family | Class | Difficulty |
|---|---|---|
| `reentrancy` | Reentrancy | Basic |
| `access-control` | Access Control | Basic |
| `price-manipulation` | Price Manipulation | Advanced |
| `signature-replay` | Access Control | Legendary |
| `bridge-phantom-deposit` | Access Control (Qubit QBridge, Jan 2022) | Advanced |
| `empty-market-inflation` | Price Manipulation (Hundred Finance / Sonne) | Advanced |
| `platypus-emergency-withdraw` | Access Control (Platypus Finance solvency check) | Advanced |
| `nomad-unproven-message` | Access Control (Nomad Bridge zero-root) | Legendary |
| `beanstalk-flash-governance` | Access Control (Beanstalk flash governance) | Advanced |

**Today: 4 canonical vulnerability families plus 5 rebuilt real incidents — 9 vulnerability families, 20 self-verified unique fresh rewrites each, 180 offline (with 6 families benchmarked in the multi-model arena).** Classes are three because `NUM_CLASSES = 3`. `signature-replay` is legendary access-control, not a fourth class. The five incidents are `bridge-phantom-deposit` (Qubit QBridge), `empty-market-inflation` (Hundred Finance / Sonne), `platypus-emergency-withdraw`, `nomad-unproven-message`, and `beanstalk-flash-governance`. Only the class fix passes: an `address(0)`-only bridge patch, and a vault patch that merely does `require(shares > 0)`, are rejected.

### 5.3 The differential five checks

| Check | Verifies | Why required |
|---|---|---|
| `pocProvesBug` | PoC succeeds on the original contract | the bug is real; rejects fake PoCs |
| `pocFailsAfterPatch` | the same PoC fails after the patch | the bug is actually removed |
| `hiddenTestsPass` | hidden functional tests all pass | the fix didn't break existing logic |
| `patchWithinLimits` | changed lines and bytes are capped, the contract name plus every required public function are still present, EVM storage layout is preserved, and forge-std cheatcodes are absent from the patch | blocks a deleted contract, a deleted interface, a shifted storage slot, or cheatcode smuggling |
| `invariantsHold` | Foundry fuzzing and stateful invariants pass at seed 0xA11CE (and PoCs are checked against decoy `.code.length` / `extcodesize` probes) | prevents cheating by test-specific hardcoding, decoy PoCs, or state corruption |

### 5.4 Challenge-sourcing policy

- ✅ Only **patched, publicly disclosed** bugs (post-mortems from DeFiHackLabs, Code4rena, Sherlock, Immunefi).
- ✅ Always transformed by `variantgen` first.
- ❌ Never anything live and unpatched.
- 📋 Private-eval mode (planned): bring-your-own challenges graded only in a private environment; new findings go through responsible disclosure.

---

## 6. Capability records & commemorative

### 6.1 The capability record (the capability record that matters): `AxVigilSkill`

`AxVigilSkill` is not a trophy — it is a **capability record**. It means: *"this agent has passed the Crucible, has real capability in [class], and is cleared for AxVigil defense work (roadmap)."*

| Attribute | Detail |
|---|---|
| Standard | ERC-5192 (soulbound) |
| Binding | `tokenId` = Agent ID; `ownerOf` follows the Agent ID registry |
| Transferability | `locked()` always true — cannot be sold or transferred |
| Record | per-class passing record counts, max difficulty, total |
| Visual | on-chain SVG; a new emblem per class passed. A single Agent ID can pass at most two mints, so at most two solves are recorded |
| Revocation | admin can revoke (e.g. malicious false positives in real work) |

Because it can't be bought, a buyer can't fake competence — which is exactly what makes it worth trusting.

### 6.2 The commemorative (cosmetic only): `AxVigilCollectible`

A free, non-speculative ERC-721 marking a **real verification event**. The `submissionHash` is in the `Minted` event, not in `tokenURI`. Before reveal, `tokenURI` is the unrevealed URI (`ipfs://unrevealed.json` on the current testnet deployment). It is deliberately free and gives no financial claim. Rarity mechanics exist in the contract but are kept out of the core narrative — see **Appendix A**. The capability record is the capability record; the collectible is a souvenir.

> Note on consistency: AxVigil critiques "mint-an-NFT-to-prove-compute" projects, so its own token design is deliberately the opposite — the thing that carries meaning (the capability record) can't be traded, and the thing that can be seen (the collectible) is free and cosmetic.

---

## 7. Participants & flywheel

### 7.1 Four sides

| Party | Provides | Gets |
|---|---|---|
| Whitehat authors | vulnerability families, fix rules, hidden tests | usage-based revenue share (not a one-time buyout); author ranking |
| AI teams / agents | compute + code reasoning | a capability record → access to real defense work → real security income *(roadmap)* |
| Protocols | security budget (scan fees / bounty pools) | automated defense, trustworthy reports, continuous monitoring *(roadmap)* |
| Sponsors / grants | funding for specific challenge pools | brand exposure, ecosystem influence, priority access |

### 7.2 The defense flywheel *(the paid steps are roadmap)*

```
better library (whitehats)
  → stricter passing record (weeds out ineffective AI)
    → higher-quality recorded agents
      → better real-world defense (more bugs intercepted)      [roadmap]
        → protocols pay (security budget flows in)             [roadmap]
          → authors + AI teams earn more
            → more contributions → loop accelerates
```

**The key difference:** this flywheel is driven by **real security budgets**, not speculative expectation. Protocols pay because "my contract is protected," not because "a token might go up."

### 7.3 Cold-start strategy (0 → first paying customer)

| Phase | Play | Goal |
|---|---|---|
| hackathon → 1 mo | seed via AI-security community + hackathon network; free eval tooling to 3–5 AI teams | initial user base |
| 1–3 mo | approach 10–20 newly deployed DeFi protocols with "free first scan + paid monitoring" | 1–2 paid pilots |
| 3–6 mo | explore API integration with Immunefi / Code4rena; open a bounty-hunter mode | first "AI found a real bug" record |

**Principle: every side has a standalone reason to join before the flywheel spins** — whitehats get double points + public ranking early; AI teams get genuinely useful free eval tooling; protocols get a free first scan.

---

## 8. Sustainability and long-term operation

### 8.1 Status

No token has been issued. Nothing in this document is an offer to sell a token or a solicitation to invest. Points are an off-chain score with no monetary value. The collectible carries no financial rights: it cannot be redeemed, it pays nothing, and it is not a claim on revenue.

The project is meant to keep running on fees paid in stablecoins or fiat (§8.2). A token (§8.3) is a later design. It is not launched, and it is not required for §8.2.

### 8.2 Revenue without a token (planned, not built)

All of the following is planned. None of it is implemented, priced, or under contract.

| Who pays | For what | How | Status |
|---|---|---|---|
| Protocols | An agent fix, or a posted fix-bounty | Platform take rate, or a per-eval verification fee | planned, not built |
| AI labs and agent developers | Passing record evals on a private hidden-test set (benchmark-as-a-service) | Per eval or subscription | planned, not built |
| Audit firms | Agent pre-screening, priced by volume | Per-volume fee | planned, not built |
| — | Challenge authors, when an eval uses their vulnerability family | Revenue share of that eval | planned, not built |

Early funding, also planned and not committed: hackathon prizes, ecosystem grants, and early design-partner protocols. Payment, when it exists, is stablecoin or fiat. It does not require a project token.

Phase A, today, is the off-chain point score and no revenue. Phase B is the table above. The old Phase C token text is §8.3.

### 8.3 Token design (Phase C, planned, not launched)

This is the former Phase C, restated. No token exists. Issuance happens only when both triggers are true:

1. Decentralised multi-validator grading is live.
2. Real paying demand exists under §8.2.

Utilities are there to close an operating loop, not to promise profit:

- Validator staking, with slashing for bad grades.
- A fee sink: part of protocol and bounty fees is converted to a buy-and-burn, or is distributed to validators.
- Rewards for challenge authors and agents, by usage.
- Governance over which vulnerability families enter the library, and over slashing parameters.

**Illustrative supply, allocation, vesting, emission, and burn. Illustrative, subject to change.** These figures are a proposal for discussion. They are not a cap, not a vote, and not an offer. Example supply: 1,000,000,000 units.

| Bucket | Share | Unlock (illustrative, subject to change) |
|---|---|---|
| Agent and author usage rewards | 40% | Emitted only against measured usage, over 4 years after launch. What is not emitted is not minted. |
| Validator incentives | 20% | Emitted over 4 years, and only to validators who are staked. |
| Ecosystem and grants | 15% | 12-month cliff, then monthly linear unlock over 36 months. |
| Contributors | 15% | 12-month cliff, then monthly linear unlock over 36 months. |
| Treasury | 10% | Locked at launch. Later releases only by the governance in this section. |

Emission is not a fixed high inflation schedule. Illustrative ceilings, subject to change: 8% of the example supply in year 1, 6% in year 2, 4% in year 3, and 2% in year 4, drawn only from the usage and validator buckets. An unused yearly ceiling is not carried forward.

Burn, illustrative and subject to change: of fees that are already denominated in the token, half are burned and half are paid to staked validators. Fees that arrive in stablecoins stay in stablecoins unless a later governance decision routes a stated share into a market buy-and-burn. That route is not built and is not promised.

Closed loop: protocols pay → validators, authors, and agents earn → stake in order to validate → slashing secures grades → more trust → more paying protocols.

Legal review is required before any issuance. The design aims at utility (the right to validate, and the stake that can be slashed), not at an expectation of profit.

### 8.4 Points (built score, not money)

| Flow | Trigger | Note |
|---|---|---|
| author share *(roadmap, not built)* | an eval uses their vulnerability family | the §8.2 revenue share, not a buyout and not a token |
| agent points | passing passing record / completing defense work | off-chain; no monetary value. Weights: Basic 1, Advanced 3, Legendary 8 |
| sponsor pool | sponsor funds a challenge pool | planned; not built |
| defense bounty *(Phase B+)* | agent finds a real bug in the field | planned; paid from the bounty in stablecoin or fiat |
| scan fee *(Phase B+)* | protocol asks for a fix or a pre-screen | the §8.2 fee; planned, not built |

### 8.5 Anti-abuse (built today)

The backend opens at most two reward sessions per Agent ID (the attempt is spent when the session opens, including if it is abandoned). The contract separately reverts a third `mint` (`mintedPerAgent`). Server-dealt challenges, hourly mint cap, API rate limits, and an answer-leak circuit breaker are built. The registry on testnet is `MockAgentID` (open mint). A commercial eval stake or fee is not built.

---

## 9. Business model (the anchor)

**AxVigil's revenue comes from security budgets, not speculative capital.** Global DeFi spends hundreds of millions a year on security (audits, insurance, bug bounties). The goal is to become an efficient, automated allocation channel into that pool. *This section — not the "decentralized compute network" phrasing — is what justifies the ambition.*

### 9.1 Revenue sources (by priority)

| Priority | Source | Note | Window |
|---|---|---|---|
| 🥇 | **B2B automated scanning** | recorded AI does first-pass review of new contracts; per-scan or subscription | pilot in 3–6 mo |
| 🥈 | **bounty share** | agents find bugs on Immunefi / Code4rena; AxVigil takes a platform fee (5–15%) | 6–12 mo |
| 🥉 | **private eval service** | passing record evals on a private hidden-test set (§8.2) | planned, not built |
| 4 | **sponsorship / grants** | ecosystem security grants, sponsored challenge pools | ongoing |
| 5 | **recorded-agent marketplace** | match recorded agents with protocols that need security | 18 mo+ |

### 9.2 Why passing record stays free

Passing record (Layer 1) is the **gate, not the product** — the product is defense service. Free passing record maximizes the pool of recorded agents (and thus defense-side compute supply), and charging would choke cold-start.

### 9.3 Versus the market

| Dimension | Audit firm | Bug bounty | AxVigil |
|---|---|---|---|
| Executor | human auditors | human whitehats | **recorded AI agents** |
| Speed | weeks–months | days–weeks | **minutes–hours** |
| Cost | priced per engagement | per severity | **per-scan / subscription (roadmap pricing, not a quoted tariff)** |
| Coverage | static (pre-deploy) | passive (wait for submissions) | **continuous (24/7)** |
| Scalability | human-bound | whitehat-bound | **compute scales horizontally** |

---

## 10. The find-vs-fix gap (stated honestly)

The single most important caveat in this document, and the thing a sharp reviewer will ask about:

**Passing record today proves an agent can *fix a known class* of bug on a controlled target. A production defense network also needs *finding unknown* issues in real code — a strictly harder problem the Crucible does not yet test.** Passing the Crucible does not, by itself, imply an agent will find novel 0-days.

We treat this as a scoping decision, not a hand-wave:

- **Layer 2 v1 is scoped to pattern-class detection and triage within an agent's recorded classes** — surfacing instances of the bug classes already on its record — not open-ended 0-day hunting.
- The near-term value proposition is therefore "fast, cheap, continuous first-pass triage for known classes," explicitly positioned as **assistive, not a replacement for human audit**.
- Closing the gap toward genuine discovery is future research, and the roadmap is gated on it rather than assuming it.

We would rather ship a smaller claim we can back with code than a larger one we can't.

---

## 11. Roadmap

No dates. A phase is live only when the row says Live.

| Phase | Status | What it is |
|---|---|---|
| **Phase 0** | Live on BSC testnet | Vulnerability sandbox. Hidden-test grading. 2-of-3 validator mint. Evidence CIDs. Three Muse Spark threshold mints, with `verify_evidence.py` OK. The three validators are permissioned and run by the team. Live grades used the subprocess sandbox. |
| **Phase 1** | Planned | Replace MockAgentID with a real agent registry. External grader review. Reveal the threshold batch. Run the Docker sandbox on live grades. Publish multi-model arena results. |
| **Phase 2** | Planned | Scanning pilots on real protocols, and bounty integrations. More vulnerability families. An open validator set. |
| **Phase 3** | Planned | A decentralised validator network. A utility token only as described in §8. Not an offer. Mainnet. |

---

## 12. Risk matrix

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Verifier bypassed (forged pass) | 🔴 fatal | medium | differential 5-check + public red-team challenge + multi-node re-run *(future)* |
| Contract / backend vulnerability | 🔴 high | low | audit, bug bounty, pause switch |
| Single signer compromised | 🔴 high | medium | KMS, multisig, role split, rotation |
| Challenges leak / get memorized | 🟠 medium | medium | `variantgen`, circuit breaker, vulnerability family rotation |
| Sybil Agent IDs farm rewards | 🟠 medium | high (today) | real registry, attempt caps, future staking |
| **Find-vs-fix gap** (passing record ≠ discovery) | 🔴 high | — | scope L2 v1 to pattern-class triage; position as assistive; see §10 |
| **AI false positives erode protocol trust** | 🔴 high | medium | human review before any public result; false positives trigger Skill revocation |
| **Protocols won't let external AI scan their contracts** | 🟠 medium | medium | private-deploy option; NDAs; scan only public contract code |
| Regulatory change | 🟠 medium | medium | points first, free mint, legal opinion |
| No demand | 🟠 medium | med-low | B2B pilots validate with paying customers first |
| Solo-project bandwidth | 🟠 medium | high | scope control, phase gates, prioritize B2B over large community |

---

## 13. Open questions

1. Which chain for mainnet? Can the SPACE ID `.ai` Agent ID registry be used directly?
2. Author revenue-share ratio and accounting of points?
3. Who custodies sponsor funds, and how, to avoid becoming a regulated financial activity?
4. Are the §8.3 triggers (multi-validator grading live, and paying demand under §8.2) the right gate, and who attests that both are met?
5. B2B product: SaaS or private deployment?
6. Layer 2 dispatch: how to match a protocol's scan need to a recorded agent's classes?
7. Legal boundary of real scanning: does scanning public contract code need protocol authorization? If an agent finds a 0-day, what disclosure flow?
8. Bounty-share ratio and settlement: how to avoid being classed as a financial intermediary?
9. Commercial-use capability record scope of AI-generated art?
10. Operating entity, jurisdiction, and tax.

---

## 14. Legal & compliance

| Issue | Response |
|---|---|
| Random draw + tradeable (loot-box concern) | free mint, passing record-gated, no mint fee |
| Token might be deemed a security | no token has been issued; this paper is not an offer; any issuance needs legal review and is specified as utility, not a profit expectation (§8.3) |
| Insurance / claims pool | excluded; distant idea only, would require a regulatory permit |
| Vulnerability material | only patched, publicly disclosed bugs; real work via responsible disclosure |
| Legal boundary of AI scanning third-party contracts | prioritize open-source contracts; private scans need explicit authorization + NDA |
| Whether bounty settlement is financial intermediation | initially protocols forward bounties directly; long-term needs legal opinion |
| Liability of AI-produced security reports | explicit disclaimer: AxVigil is assistive scanning, not a replacement for human audit; no liability for losses from scan results |
| Rights in art / model output | confirm commercial terms of the image model used |
| Personal data | backend stores only wallet address and Agent ID |

---

## Appendix A — Collectible rarity mechanics

Kept out of the core narrative on purpose (see §6.2); documented here for completeness, reflecting the current contract.

| Item | Rule |
|---|---|
| Supply | 7,777 = 7,773 public + 4 Hidden |
| Price | free mint, gas only |
| Eligibility | two lifetime reward attempts per Agent ID; a passing `submissionHash` mints once |
| Pools | three-pool ladder; `pool` equals the solved difficulty; Hidden drawable only from pool 2 at a fixed 0.25% (cap 30), leaving 7,773 public pieces always mintable |
| Randomness | commit-reveal today (hackathon-grade); Chainlink VRF v2.5 on mainnet *(roadmap)* |
| Art | original character "Aki" is the art plan (`docs/prd-v1.4-asset-pipeline.md`). `tokenURI` does not carry `submissionHash`; the `Minted` event does |

---

## Appendix B — Reproducibility

From a checkout of `main`, with Foundry installed and `cd contracts && forge build` done once:

```bash
scripts/test_all.sh
# offline bank, one vulnerability family (see variantgen/README.md):
PYTHONPATH=variantgen:verifier python3 -m variantgen verify-mother --mother mothers/reentrancy --count 20
```

A graded session writes `backend/evidence/<submissionHash>/manifest.json` (override with `EVIDENCE_DIR`). Recompute:

```bash
python3 scripts/verify_evidence.py backend/evidence/<submissionHash>/manifest.json
```

That checks the CID, `submissionHash = H(challengeId, seed, patch, poc)`, the seed commitment, and a fresh grader run. Hidden tests are read from the family-template directory in this repo.

Chain, no key:

```bash
RPC_URL=https://bsc-testnet-rpc.publicnode.com \
AXVIGIL_COLLECTIBLE=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658 \
python3 scripts/reveal_and_recompute.py --dry-run
```

Signer rotation and batch-2 reveal on the original collectible are mined (`signerRotationTx` `0xaea5242f…`, `batch2RevealTx` `0xf83f0829…`). The threshold deploy and the three Muse Spark mints are in `deployments/bsc-testnet-97.json`. Commands for a further mint are in `docs/operator-runbook.md`. Live grading used the subprocess sandbox, not Docker.

Model loop, when `META_API_KEY` is set:

```bash
PYTHONPATH=agent:verifier python3 -m axvigil_agent solve \
  --challenge <rendered-challenge-dir> --max-iters 4
```

The offline stand-in is `--oracle`. It does not call `https://api.meta.ai/v1`.

---

## Closing

AI compute should not be wasted on zero-sum puzzles. Every GPU-hour and every inference should produce real protection — a protocol's TVL, a user's deposit, a chain's safety.

AxVigil's end vision is not "launch a token" or "sell NFTs." It is this: **when a new contract is deployed, an agent with a Crucible record should be able to offer a first pass that a human audit can start from.** That pass is not a replacement for the audit, and this paper does not quote a market price for one.

We're not there yet. What we have today is the part that makes the rest trustworthy: a proving ground where an AI's fix is verified, not just claimed. That is where compute should go.
