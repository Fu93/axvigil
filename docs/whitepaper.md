# AxVigil Whitepaper (v3.1)

> **From Compute to Protection** — turning AI's code-reasoning compute into a verifiable defense for smart contracts and on-chain assets.

**Status discipline (read this first).** This document describes one thing that exists and two that do not yet. **Layer 1 — the Crucible (certification)** is built, tested, and live on BSC testnet today. **Layer 2 (defense network)** and **Layer 3 (settlement & orchestration)** are the roadmap. Every forward-looking claim is marked as such. Where this document says "today" it means code in `Fu93/axvigil` at `main`; where it says "roadmap" or "future" it means design intent, not shipped software.

**No token has been issued.** Nothing in this document is an offer to sell a token or a solicitation to invest. Points are an off-chain score with no monetary value. The collectible carries no financial rights. A later utility-token design, and the fee model that is meant to fund the project without one, are in §8. Both are planned, not built.

---

## 0. Positioning

**AxVigil is an anti-memorization proving ground that certifies AI agents to *fix* smart-contract vulnerabilities, and the trust root for a defense network built on top of it.**

The near-term, demonstrable product is the proving ground — **the Crucible**. The long-term vision is to route certified agents at real contract-security work. We lead with the first because it is real; we describe the second because it is where the first is aimed.

*From Compute to Protection — make every AI inference a layer of security, not a zero-sum puzzle.*

---

## 1. Executive summary

AI agents can already draft smart-contract patches. But a plausible patch is not a verified fix, and the industry has no independent, re-runnable way to tell them apart. Meanwhile two things sit side by side:

- **Compute is wasted.** Many Web3 projects point AI at SAT instances, prime hunts and mazes, then mint NFTs to prove "my AI is fast." The output protects no one.
- **Security is under-supplied.** DeFi exploits have cost billions; audits are slow and expensive; most newly deployed protocols ship unaudited.

**AxVigil's thesis: route the first kind of compute at the second kind of pain — but only after proving the compute is actually competent.**

The piece we built, and the piece this space is missing, is **verification**: an agent is dealt a freshly generated vulnerable contract, submits a patch *and* a proof-of-concept exploit, and a deterministic sandboxed grader confirms the exploit worked before the patch and fails after — without the patch breaking the contract. Pass, and the agent earns a **soulbound license** bound to its on-chain identity. That certification is the trust root; a defense network that puts licensed agents on real work is the destination.

| Item | Today (built) | Roadmap |
|---|---|---|
| Core | The Crucible: deal challenge → agent fixes → deterministic verify → on-chain license | Defense network: automated review, continuous monitoring, bounty scanning |
| Credential | `AxVigilSkill` — ERC-5192 soulbound license bound to Agent ID | license gates access to real defense tasks |
| Verification | differential 4-check grader + anti-memorization variant engine | multi-node re-run / decentralized verification |
| Economy | off-chain points with no monetary value; no token issued | stablecoin or fiat fees (§8.2, planned); a utility token only if the §8.3 triggers are met |
| Deployment | BSC testnet (chain 97), full flow exercised on-chain | mainnet, gated on Layer 1 proving itself |
| Challenge source | only patched, publicly disclosed bugs, transformed by `variantgen` | sponsored challenges; private-eval mode with responsible disclosure |

---

## 2. The problem

### 2.1 Compute layer — AI reasoning is being wasted

Through 2025–2026, agent code-reasoning capability grew fast, and a large share of Web3 pointed it at **zero-sum games with no social value**: SAT/boolean-satisfiability puzzles, prime hunts, maze runs, repeated benchmark screenshots — each burning real GPU time to mint a "proof" that protects nobody. **Compute spins; the real-world security gap widens.**

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
3. **Credentials bind to the wrong thing** — capability should belong to the agent, not a wallet.
4. **Authors aren't rewarded** — whitehats' curated bug patterns get reused with no ongoing return.
5. **Everyone rebuilds the harness** — each team builds its own sandbox, sources its own challenges, fights its own cheating.
6. **No path from exam to battlefield** — even a proven agent has no network to actually protect real assets.

**The core problem AxVigil addresses: build a trustworthy mechanism that moves AI compute from "spinning on puzzles" toward "defending real contracts" — starting with the verification that makes any such claim credible.**

---

## 3. Solution & positioning

### 3.1 Positioning

AxVigil is **trust and dispatch infrastructure for security AI**. Not another benchmark, not another audit shop, not another NFT drop.

- To AI teams: a licensing exam today, a job board tomorrow.
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
│  Layer 1 — Certification (The Crucible)        ← BUILT, LIVE  │
│  anti-memorization challenges · deterministic sandbox · soulbound license
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Components by layer

| Layer | Function | Component | State |
|---|---|---|---|
| **L1 — Crucible** | identity | Agent ID (SPACE-ID-style ERC-721 registry) | built |
| | challenge library | `mothers/` + `variantgen/` (6 mothers × 20 variants) | built |
| | verification | `axvigil_verifier` (4 checks + sandbox) | built |
| | license | `AxVigilSkill` (ERC-5192 soulbound) | built |
| | commemorative | `AxVigilCollectible` (ERC-721, free) | built |
| **L2 — Defense** | task dispatch | queue + match engine | roadmap |
| | execution | licensed-agent SDK | roadmap |
| | result review | responsible-disclosure pipeline | roadmap |
| **L3 — Settlement** | bounty payout | USDC settlement | roadmap |
| | service fee | subscription / per-scan billing | roadmap |
| | reputation | Skill revocation on bad behavior | roadmap |

### 3.4 Design principles

1. **Compute must produce real protection** — reward removing a bug, not "solving" per se.
2. **Re-runnable and verifiable** — any result can be independently reproduced.
3. **Challenges are issued, not chosen** — agents can't pick or memorize.
4. **Credentials follow the agent** — bound to Agent ID, not a wallet.
5. **Free to participate, revenue from real budgets** — certification is free; defense work earns real income.
6. **No speculative token** — operation is meant to be funded by security budgets (§8.2). A token is only the §8.3 design, and none has been issued.

---

## 4. Layer 1 — The Crucible (current system)

### 4.1 Its role in the network

Today's prototype (`Fu93/axvigil`, `main`) implements **Layer 1**. Its job: **ensure an agent entering the defense network has real capability — not compute that would generate false positives and waste protocols' time.** An agent that hasn't passed the Crucible can't reach Layer 2. This is the network's trust root — and it is the hackathon deliverable, working end to end.

### 4.2 Certification flow (end to end)

```
Backend (FastAPI) ──deal a fresh variant (source only)──▶ AI Agent
      ▲                                                     │
      │                      patch + PoC                    ▼
      │                                               Verifier (deterministic sandbox)
      │                                               ① pocProvesBug
      │                                               ② pocFailsAfterPatch
      │                                               ③ hiddenTestsPass
      │◀──── EIP-712 MintAuth (only if all pass) ──── ④ patchWithinLimits
      ▼
Agent ID owner submits mint
  → AxVigilSkill (ERC-5192): license updated
  → AxVigilCollectible (ERC-721): free commemorative
  → agent is now licensed; eligible for Layer 2 (roadmap)
```

### 4.3 Current components

| Component | Highlights |
|---|---|
| Backend | FastAPI: wallet-signature login with on-chain Agent ID `ownerOf` check; server-dealt challenges; in-session grading; EIP-712 authorization; SQLite; rate limits; answer-leak circuit breaker; difficulty-weighted leaderboard |
| Verifier | zero third-party deps; sandbox is a resource-limited offline subprocess (`ffi` off, no network, wall-clock timeout, POSIX rlimits); forge supplies solc unless `SOLC` pins one |
| Agent | automated solve loop with an offline oracle so judges can reproduce runs |
| Contracts | EIP-712 authorization; `mintedPerAgent` ceiling of 2; hourly cap; pausable; `setSigner` (owner rotates the signer; the signer key only authorizes mints); fixed supply |
| Deployment | BSC testnet (chain 97): Skill `0x3377…CD18`, Collectible `0x0658…4658`, registry `0x7Aa4…d45e` (`MockAgentID`, open mint, not a production Agent ID) |
| Tests | Foundry unit / fuzz / rarity-distribution / invariant / verify→mint integration; Python backend and verifier suites; 179 tests green (contracts 75 · Python 104; one Docker image check skipped until the sandbox image is built) |

### 4.4 Live proof (Muse Spark mint)

The primary on-chain proof is a **Muse Spark** solve, not the earlier reference-solution smoke test.

| Field | Value |
|---|---|
| Model | `muse-spark-1.1` via `https://api.meta.ai/v1` |
| Challenge | server-dealt `signature-replay` (legendary). Class 2 because `NUM_CLASSES = 3`; signature replay is grouped under access control |
| Model calls | 1 request, 4,947 completion tokens, first try |
| Grade | server hidden-test grade passed |
| Signer | `0x4E38ec3f38D5c947B60E7e1273890Eea51501Ef8` (still also deployer, owner, and admin — rotation not sent) |
| Mint | tx `0x8f135d51462a5a5ad98dc3af3df0838f5f3eabc1207210fc22041f876281c177`, block 140439816, 331,623 gas |
| Collectible | token #2, `tokenURI` `ipfs://unrevealed.json`, batch 2 |
| Skill | token #7, `locked() == true` |
| submissionHash | `0x93eb0753c8c9022acfa604e06a7fa89c4f19b04730c049acba261fce092b7094` (in the `Minted` event: vulnClass 2, difficulty 2, pool 2, batch 2) |
| Batch 2 commit | `0xc48b3866605adac8328dad2bfff467ba9918c2a4c91271d9257c5b12fbaef222` |
| Batch 2 reveal | **pending.** The seed is not in the repo. `revealTx` is null until the operator runs `scripts/reveal_and_recompute.py` |

Secondary, kept in `deployments/bsc-testnet-97.json` under `smokeTest`: a reference solution for a server-dealt legendary session minted token #1 (Agent ID 1). Batch 1 was later revealed as tier COMMON, artId 20000, `submissionHash 0x8083…64df`.

### 4.5 Meta model integration and results

The agent loop is propose → grade → feed the grader log back → retry (`agent/axvigil_agent`). The HTTP client talks to an OpenAI-compatible chat-completions endpoint. Default model `muse-spark-1.1`, default base URL `https://api.meta.ai/v1`. HTTP timeout default is 300s. `META_MAX_TOKENS`, when set, is sent as `max_tokens`; unset means the request does not cap the completion.

| Run | Outcome |
|---|---|
| `bridge-phantom-deposit` seed 7 (contract `Tunnel`), after the PR #11 hint | attempt 0: narrow `address(0)` fix, hidden tests 7/8. attempt 1: `token.code.length > 0`, pass. 16,250 tokens, 45 s, 2 attempts |
| `access-control` seed 1 (role rendered as `custodian`), after the hidden-test fix | pass on the first try. 3,487 tokens, 16 s |
| Server-dealt `signature-replay` on BSC testnet | pass on the first try (1 request, 4,947 tokens), then the mint in §4.4 |
| Same bridge seed 7 before the hint change | 5 attempts, all stuck at hidden 7/8, because the retry text said to keep the fix minimal |

**Failure analysis (two benchmark bugs, both fixed in PR #11).**

1. Hidden-test failure text said the patch had changed intended behaviour and to keep the fix minimal. A correct class diagnosis (phantom deposit) was then patched only for `token == address(0)`. `test_codelessNonZeroTokenCannotPhantomDeposit` rejects that. The hint now says the failure is either changed behaviour or an incomplete class fix, and it does not name the hidden test or the `code.length` repair.
2. `mothers/access-control/hidden.t.sol.tmpl` required the revert string `"not owner"`. Rendering renames the role (`custodian`, `manager`, …) and that string is not in the vulnerable source, so a correct `"not custodian"` revert was a false fail. The hidden test now accepts any revert from an unauthorized caller.

### 4.6 Trust model and threat model

What a pass means: one sandboxed grader, on one machine, accepted one patch against one rendered variant. The `Minted` event's `submissionHash` commits to `(challengeId, seed, patch, PoC)` under the canonical encoding in `verifier/axvigil_verifier/keccak.py`. It does not, by itself, prove that a second implementation of the grader would agree, or that the signer key was not the same key as the owner.

| Actor | Can | Cannot |
|---|---|---|
| Agent | read the rendered source; submit a patch and a PoC | read the seed, the hidden tests, or the reference fix from the API (the tests are public in the git repo) |
| Backend signer | sign `MintAuth` for a session this process marked passed | mint by itself; change tiers; rotate itself |
| Contract owner | `setSigner`, `commitSeed`, `revealSeed`, pause, set URI | forge a `MintAuth` once the signer has been rotated to a different key |
| Anyone | recompute `submissionHash` from an evidence bundle and re-run `scripts/verify_evidence.py` | recover a batch seed before `revealSeed` |

The default sandbox is a resource-limited offline subprocess: `ffi` off, `FOUNDRY_OFFLINE`, a wall-clock timeout, and POSIX `rlimit` on CPU, address space, file size, and process count. `AXVIGIL_SANDBOX=docker` runs the same forge test in `axvigil-sandbox:1.8.7` with `--network none`, a read-only root, uid 1000, CPU/memory/pid limits, and a tmpfs workdir (`verifier/docker/Dockerfile`). The subprocess runner remains the fallback when the env is unset or `subprocess`. Neither mode is a TEE or a zkVM.

Known false-pass gap: **none known** on the two real-incident mothers after the negative controls (an `address(0)`-only bridge patch, and `require(shares > 0)` on the vault, both fail). That is not a proof that no other false-pass exists.

### 4.7 Decentralisation roadmap

**In this repository, before the hackathon deadline (operator transactions still pending):**

- Key separation: `setSigner` is on the deployed collectible. `scripts/rotate_signer.sh` sends it. Placeholder: `signerRotationTx: null`.
- Threshold prototype (2-of-3): `mint(auth, bytes[])` checks k distinct validator signatures. The owner adds and removes validators and sets the threshold. This needs a new deploy (`script/DeployThreshold.s.sol`). Placeholder addresses are `thresholdRedeploy` in the deployment file; they are null until the operator broadcasts.
- Evidence bundles: every graded `/v1/submit` writes canonical JSON, a local CIDv1, and optional `IPFS_PIN_URL` pinning. The CID is returned on submit and authorize. The on-chain tie is the existing `Minted.submissionHash`, not a new field.
- Seed reveal: `scripts/reveal_and_recompute.py` can dry-run against the testnet with no key. Batch 2 reveal is pending. Placeholder: `batch2RevealTx: null`.

**After the deadline (not built):**

- Staking and slashing on top of the threshold prototype (the k-of-n check itself is in this repo; stake is not).
- TEE or zkVM attested grading.
- On-chain attempt quotas (today the attempt cap is backend state; the contract caps mints at 2) and an ERC-8004-style identity instead of `MockAgentID`.
- An on-chain bounty market.

### 4.8 Limitations and known issues

- The live signer, owner, and deployer are one address until the operator rotation.
- Batch 2 is committed and not revealed. Token #2 `tokenURI` is still `ipfs://unrevealed.json`.
- `MockAgentID` is an open mint. It is not the SPACE ID Agent ID registry.
- The backend refuses a third reward session. The contract reverts a third mint. They are not the same counter: an abandoned session spends a backend attempt and does not mint.
- Skill art can show a new emblem per class passed, but a single Agent ID can record at most two solves, because each solve is written by a mint and mints are capped at two.
- Hidden tests are withheld from the session payload and are public in `mothers/*/hidden.t.sol.tmpl`.
- Author revenue share, commercial eval stake or fee, and B2B scan billing are roadmap. They are not implemented.
- Offline `verify-mother` checks 20 unique variants per mother (120). Live dealing now also reference-checks the dealt seed and skips a repeated structural fingerprint. It does not pre-publish an exhaustive list of every future seed.

---

## 5. Challenge library & anti-memorization engine

### 5.1 Why anti-memorization is the prerequisite

If an agent merely memorized answers, it is **dead weight** in the defense layer — it can't recognize new variants in the wild. The Crucible's core value is ensuring every licensed agent has **generalizable** repair capability, not recall of specific problems.

### 5.2 `variantgen` — the anti-memorization engine

Each mother is one vulnerability template. Per seed, `variantgen` renames identifiers, injects distractor functions and reorders bodies. A structural fingerprint treats rename-only copies as the same variant. Offline `verify-mother` discards those look-alikes while it builds the 20-variant bank. The live server does the same check before it returns source: it skips a fingerprint it has already issued, and when `AXVIGIL_REFERENCE_CHECK` is on (the default for `Settings.from_env`) it grades the reference solution before dealing. The agent must fix the class of bug.

| Mother | Class | Difficulty |
|---|---|---|
| `reentrancy` | Reentrancy | Basic |
| `access-control` | Access Control | Basic |
| `price-manipulation` | Price Manipulation | Advanced |
| `signature-replay` | Access Control | Legendary |
| `bridge-phantom-deposit` | Access Control (Qubit QBridge, Jan 2022) | Advanced |
| `empty-market-inflation` | Price Manipulation (Hundred Finance / Sonne) | Advanced |

**Today: 4 canonical mothers plus 2 rebuilt incidents — 6 mothers, 20 self-verified unique variants each, 120 offline.** Classes are three because `NUM_CLASSES = 3`. `signature-replay` is legendary access-control, not a fourth class. The two incidents are `bridge-phantom-deposit` (Qubit QBridge, January 2022, loss figure as reported by the post-mortems linked from `mother.json`) and `empty-market-inflation` (Hundred Finance, April 2023, and Sonne, May 2024, same). Only the class fix passes those two: an `address(0)`-only bridge patch, and a vault patch that merely does `require(shares > 0)`, are rejected. There is no known false-pass gap on either. That is not a claim that every possible patch has been enumerated.

### 5.3 The differential four checks

| Check | Verifies | Why required |
|---|---|---|
| `pocProvesBug` | PoC succeeds on the original contract | the bug is real; rejects fake PoCs |
| `pocFailsAfterPatch` | the same PoC fails after the patch | the bug is actually removed |
| `hiddenTestsPass` | hidden functional tests all pass | the fix didn't break existing logic |
| `patchWithinLimits` | changed lines and bytes are capped, and the contract name plus every required public function are still present | blocks a deleted contract or a deleted interface, not only a huge diff |

### 5.4 Challenge-sourcing policy

- ✅ Only **patched, publicly disclosed** bugs (post-mortems from DeFiHackLabs, Code4rena, Sherlock, Immunefi).
- ✅ Always transformed by `variantgen` first.
- ❌ Never anything live and unpatched.
- 📋 Private-eval mode (planned): bring-your-own challenges graded only in a private environment; new findings go through responsible disclosure.

---

## 6. Credentials & commemorative

### 6.1 The license (the credential that matters): `AxVigilSkill`

`AxVigilSkill` is not a trophy — it is a **license**. It means: *"this agent has passed the Crucible, has real capability in [class], and is cleared for AxVigil defense work (roadmap)."*

| Attribute | Detail |
|---|---|
| Standard | ERC-5192 (soulbound) |
| Binding | `tokenId` = Agent ID; `ownerOf` follows the Agent ID registry |
| Transferability | `locked()` always true — cannot be sold or transferred |
| Record | per-class certification counts, max difficulty, total |
| Visual | on-chain SVG; a new emblem per class passed. A single Agent ID can pass at most two mints, so at most two solves are recorded |
| Revocation | admin can revoke (e.g. malicious false positives in real work) |

Because it can't be bought, a buyer can't fake competence — which is exactly what makes it worth trusting.

### 6.2 The commemorative (cosmetic only): `AxVigilCollectible`

A free, non-speculative ERC-721 marking a **real verification event**. The `submissionHash` is in the `Minted` event, not in `tokenURI`. Before reveal, `tokenURI` is the unrevealed URI (`ipfs://unrevealed.json` on the current testnet deployment). It is deliberately free and gives no financial claim. Rarity mechanics exist in the contract but are kept out of the core narrative — see **Appendix A**. The license is the credential; the collectible is a souvenir.

> Note on consistency: AxVigil critiques "mint-an-NFT-to-prove-compute" projects, so its own token design is deliberately the opposite — the thing that carries meaning (the license) can't be traded, and the thing that can be seen (the collectible) is free and cosmetic.

---

## 7. Participants & flywheel

### 7.1 Four sides

| Party | Provides | Gets |
|---|---|---|
| Whitehat authors | mothers, fix rules, hidden tests | usage-based revenue share (not a one-time buyout); author ranking |
| AI teams / agents | compute + code reasoning | a license → access to real defense work → real security income *(roadmap)* |
| Protocols | security budget (scan fees / bounty pools) | automated defense, trustworthy reports, continuous monitoring *(roadmap)* |
| Sponsors / grants | funding for specific challenge pools | brand exposure, ecosystem influence, priority access |

### 7.2 The defense flywheel *(the paid steps are roadmap)*

```
better library (whitehats)
  → stricter certification (weeds out ineffective AI)
    → higher-quality licensed agents
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
| AI labs and agent developers | Certification evals on a private hidden-test set (benchmark-as-a-service) | Per eval or subscription | planned, not built |
| Audit firms | Agent pre-screening, priced by volume | Per-volume fee | planned, not built |
| — | Challenge authors, when an eval uses their mother | Revenue share of that eval | planned, not built |

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
- Governance over which mothers enter the library, and over slashing parameters.

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
| author share *(roadmap, not built)* | an eval uses their mother | the §8.2 revenue share, not a buyout and not a token |
| agent points | passing certification / completing defense work | off-chain; no monetary value. Weights: Basic 1, Advanced 3, Legendary 8 |
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
| 🥇 | **B2B automated scanning** | licensed AI does first-pass review of new contracts; per-scan or subscription | pilot in 3–6 mo |
| 🥈 | **bounty share** | agents find bugs on Immunefi / Code4rena; AxVigil takes a platform fee (5–15%) | 6–12 mo |
| 🥉 | **private eval service** | certification evals on a private hidden-test set (§8.2) | planned, not built |
| 4 | **sponsorship / grants** | ecosystem security grants, sponsored challenge pools | ongoing |
| 5 | **certified-agent marketplace** | match licensed agents with protocols that need security | 18 mo+ |

### 9.2 Why certification stays free

Certification (Layer 1) is the **gate, not the product** — the product is defense service. Free certification maximizes the pool of licensed agents (and thus defense-side compute supply), and charging would choke cold-start.

### 9.3 Versus the market

| Dimension | Audit firm | Bug bounty | AxVigil |
|---|---|---|---|
| Executor | human auditors | human whitehats | **licensed AI agents** |
| Speed | weeks–months | days–weeks | **minutes–hours** |
| Cost | priced per engagement | per severity | **per-scan / subscription (roadmap pricing, not a quoted tariff)** |
| Coverage | static (pre-deploy) | passive (wait for submissions) | **continuous (24/7)** |
| Scalability | human-bound | whitehat-bound | **compute scales horizontally** |

---

## 10. The find-vs-fix gap (stated honestly)

The single most important caveat in this document, and the thing a sharp reviewer will ask about:

**Certification today proves an agent can *fix a known class* of bug on a controlled target. A production defense network also needs *finding unknown* issues in real code — a strictly harder problem the Crucible does not yet test.** Passing the Crucible does not, by itself, imply an agent will find novel 0-days.

We treat this as a scoping decision, not a hand-wave:

- **Layer 2 v1 is scoped to pattern-class detection and triage within an agent's licensed classes** — surfacing instances of the bug classes it is certified for — not open-ended 0-day hunting.
- The near-term value proposition is therefore "fast, cheap, continuous first-pass triage for known classes," explicitly positioned as **assistive, not a replacement for human audit**.
- Closing the gap toward genuine discovery is future research, and the roadmap is gated on it rather than assuming it.

We would rather ship a smaller claim we can back with code than a larger one we can't.

---

## 11. Roadmap (value-gated)

| Phase | Window | Focus | Acceptance |
|---|---|---|---|
| **Phase 0 — Crucible** | to 2026-11-05 | hackathon finish: collection art and a demo video are still open. Hidden is live. Evidence bundles and the reveal/rotate scripts are in the repo. The rotation tx and the batch-2 reveal tx are pending the operator | demo reproducible; offline bank 20/20 per mother; live deal reference-checks when the flag is on |
| **Phase 1 — hardening** | after the hackathon, no calendar promise | operator sends signer rotation; batch-2 reveal; move off `MockAgentID`; external review of the grader. VRF and a legal opinion are not scheduled as if they were already underway | rotation tx mined; batch 2 revealed; a written review of the grader, not a claim that one exists today |
| **Phase 2 — Defense Alpha** | 2027 Q1 (conditional) | mainnet; first real-scan pilots (3–5 protocols) | ≥100 licensed agents; ≥1 paying scan customer |
| **Phase 3 — flywheel** | 3–6 mo post-mainnet | library to 15–20 mothers; bounty-platform integration; B2B pricing | monthly scan revenue covers opex; first bounty settled |
| **Later** | conditional | decentralized verification, conditional token, agent marketplace, cross-chain | — |

**Principle: each phase starts because the previous one produced real value — not because time passed.**

---

## 12. Risk matrix

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Verifier bypassed (forged pass) | 🔴 fatal | medium | differential 4-check + public red-team challenge + multi-node re-run *(future)* |
| Contract / backend vulnerability | 🔴 high | low | audit, bug bounty, pause switch |
| Single signer compromised | 🔴 high | medium | KMS, multisig, role split, rotation |
| Challenges leak / get memorized | 🟠 medium | medium | `variantgen`, circuit breaker, mother rotation |
| Sybil Agent IDs farm rewards | 🟠 medium | high (today) | real registry, attempt caps, future staking |
| **Find-vs-fix gap** (certification ≠ discovery) | 🔴 high | — | scope L2 v1 to pattern-class triage; position as assistive; see §10 |
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
6. Layer 2 dispatch: how to match a protocol's scan need to a licensed agent's certified classes?
7. Legal boundary of real scanning: does scanning public contract code need protocol authorization? If an agent finds a 0-day, what disclosure flow?
8. Bounty-share ratio and settlement: how to avoid being classed as a financial intermediary?
9. Commercial-use license scope of AI-generated art?
10. Operating entity, jurisdiction, and tax.

---

## 14. Legal & compliance

| Issue | Response |
|---|---|
| Random draw + tradeable (loot-box concern) | free mint, certification-gated, no mint fee |
| Token might be deemed a security | no token has been issued; this paper is not an offer; any issuance needs legal review and is specified as utility, not a profit expectation (§8.3) |
| Insurance / claims pool | excluded; distant idea only, would require licensing |
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
# offline bank, one mother:
cd variantgen && python3 -m variantgen verify-mother --mother ../mothers/reentrancy --count 20
```

A graded session writes `backend/evidence/<submissionHash>/manifest.json` (override with `EVIDENCE_DIR`). Recompute:

```bash
python3 scripts/verify_evidence.py backend/evidence/<submissionHash>/manifest.json
```

That checks the CID, `submissionHash = H(challengeId, seed, patch, poc)`, the seed commitment, and a fresh grader run. Hidden tests are read from `mothers/` in this repo.

Chain, no key:

```bash
RPC_URL=https://bsc-testnet-rpc.publicnode.com \
AXVIGIL_COLLECTIBLE=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658 \
python3 scripts/reveal_and_recompute.py --dry-run
```

Signer rotation and batch-2 reveal need the owner key and the batch-2 seed file. They are written up in `docs/operator-runbook.md`. Those transactions are not in the deployment record yet (`signerRotationTx` and `batch2RevealTx` are pending).

Model loop, when `META_API_KEY` is set:

```bash
PYTHONPATH=agent:verifier python3 -m axvigil_agent solve \
  --challenge <rendered-challenge-dir> --max-iters 4
```

The offline stand-in is `--oracle`. It does not call `https://api.meta.ai/v1`.

---

## Closing

AI compute should not be wasted on zero-sum puzzles. Every GPU-hour and every inference should produce real protection — a protocol's TVL, a user's deposit, a chain's safety.

AxVigil's end vision is not "launch a token" or "sell NFTs." It is this: **when a new contract is deployed, a Crucible-certified agent should be able to offer a first pass that a human audit can start from.** That pass is not a replacement for the audit, and this paper does not quote a market price for one.

We're not there yet. What we have today is the part that makes the rest trustworthy: a proving ground where an AI's fix is verified, not just claimed. That is where compute should go.
