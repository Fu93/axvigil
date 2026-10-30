# AxVigil Whitepaper (v3.1)

> **From Compute to Protection** — turning AI's code-reasoning compute into a verifiable defense for smart contracts and on-chain assets.

**Status discipline (read this first).** This document describes one thing that exists and two that do not yet. **Layer 1 — the Crucible (certification)** is built, tested, and live on BSC testnet today. **Layer 2 (defense network)** and **Layer 3 (settlement & orchestration)** are the roadmap. Every forward-looking claim is marked as such. Where this document says "today" it means code in `Fu93/axvigil` at `main`; where it says "roadmap" or "future" it means design intent, not shipped software.

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
| Economy | points only; no token, no yield promise | revenue from real security budgets (B2B scanning, bounty share) |
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
| | challenge library | `mothers/` + `variantgen/` (4 mothers × 20 variants) | built |
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
6. **No speculative token** — the loop is driven by security budgets, not market heat.

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
| Verifier | zero third-party deps; `ffi` off, no network, wall-clock timeout + POSIX resource limits; auto-resolves the Foundry toolchain |
| Agent | automated solve loop with an offline oracle so judges can reproduce runs |
| Contracts | EIP-712 authorization; two lifetime attempts per Agent ID; hourly cap; pausable; rotatable signer; fixed supply |
| Deployment | BSC testnet (chain 97): Skill `0x3377…CD18`, Collectible `0x0658…4658`, Agent ID registry `0x7Aa4…d45e` |
| Tests | Foundry unit / fuzz / rarity-distribution / invariant / verify→mint integration; Python backend and verifier suites; CI green on `main` |

### 4.4 Live status

A full flow has run against the live contracts: a backend doing a real-RPC Agent ID ownership check signed a MintAuth for a **server-dealt legendary (pool 2)** solve; Agent ID 1 minted token #1 (batch 1 committed, then revealed: tier COMMON); `submissionHash 0x8083…64df`. All 80 variants self-verify against the real grader before shipping.

---

## 5. Challenge library & anti-memorization engine

### 5.1 Why anti-memorization is the prerequisite

If an agent merely memorized answers, it is **dead weight** in the defense layer — it can't recognize new variants in the wild. The Crucible's core value is ensuring every licensed agent has **generalizable** repair capability, not recall of specific problems.

### 5.2 `variantgen` — the anti-memorization engine

Each mother is one vulnerability template. Per seed, `variantgen` renames identifiers, injects distractor functions and reorders bodies to produce structurally distinct variants; a structural fingerprint discards look-alikes before issue. The agent must actually fix that class of bug.

| Mother | Class | Difficulty |
|---|---|---|
| `reentrancy` | Reentrancy | Basic |
| `access-control` | Access Control | Basic |
| `price-manipulation` | Price Manipulation | Advanced |
| `signature-replay` | Access Control | Legendary |

**Today: 4 mothers, each with 20 self-verified unique variants — 80 total**, across 3 vulnerability classes and all 3 difficulty tiers.

### 5.3 The differential four checks

| Check | Verifies | Why required |
|---|---|---|
| `pocProvesBug` | PoC succeeds on the original contract | the bug is real; rejects fake PoCs |
| `pocFailsAfterPatch` | the same PoC fails after the patch | the bug is actually removed |
| `hiddenTestsPass` | hidden functional tests all pass | the fix didn't break existing logic |
| `patchWithinLimits` | changed lines / bytes are capped | blocks "delete the whole contract" brute-force patches |

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
| Visual | on-chain SVG; a new emblem per class passed |
| Revocation | admin can revoke (e.g. malicious false positives in real work) |

Because it can't be bought, a buyer can't fake competence — which is exactly what makes it worth trusting.

### 6.2 The commemorative (cosmetic only): `AxVigilCollectible`

A free, non-speculative ERC-721 marking a **real verification event** (metadata carries the `submissionHash`). It is deliberately free and gives no financial claim; its only meaning is "a real solve happened." Rarity mechanics exist in the contract but are intentionally kept out of the core narrative — see **Appendix A**. The license is the star; the collectible is a souvenir.

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

## 8. Points → economy (phased)

### 8.1 Principle

**AxVigil's economy is driven by real security budgets, not token speculation.** Whether a token ever ships depends on whether the network produces real protective value — not on market heat. Today, contracts and SPEC are explicit: no token, no yield promise.

### 8.2 Three phases

```
Phase A — points (now)
  driver: hackathon + community · revenue: none
  gate: monthly certifications > 1,000 and authors > 20
      ↓
Phase B — security-service revenue (6–18 mo target)       [roadmap]
  driver: B2B scan fees + bounty share + sponsor pools · revenue: USDC
  gate: monthly scan revenue covers operating cost
      ↓
Phase C — token (conditional, distant)                     [roadmap]
  prerequisites: legal opinion + >500 monthly active agents + no regulatory blocker
  function: governance + anti-abuse staking only; no yield promise
```

### 8.3 Points flow (A–B)

| Flow | Trigger | Note |
|---|---|---|
| author share | their mother is dealt and graded | usage-based, not a buyout |
| agent points | passing certification / completing defense work | difficulty-weighted: Basic 1, Advanced 3, Legendary 8 |
| sponsor pool | sponsor funds a challenge pool | bounties / extra rewards |
| defense bounty *(Phase B+)* | agent finds a real bug in the field | shared from the bounty pool |
| scan fee *(Phase B+)* | protocol submits a scan request | per-scan / subscription |

### 8.4 Anti-abuse (built today)

Two lifetime attempts per Agent ID · server-dealt challenges · hourly mint cap · API rate limits · answer-leak circuit breaker · real Agent ID registry required · commercial eval may require stake or fee.

---

## 9. Business model (the anchor)

**AxVigil's revenue comes from security budgets, not speculative capital.** Global DeFi spends hundreds of millions a year on security (audits, insurance, bug bounties). The goal is to become an efficient, automated allocation channel into that pool. *This section — not the "decentralized compute network" phrasing — is what justifies the ambition.*

### 9.1 Revenue sources (by priority)

| Priority | Source | Note | Window |
|---|---|---|---|
| 🥇 | **B2B automated scanning** | licensed AI does first-pass review of new contracts; per-scan or subscription | pilot in 3–6 mo |
| 🥈 | **bounty share** | agents find bugs on Immunefi / Code4rena; AxVigil takes a platform fee (5–15%) | 6–12 mo |
| 🥉 | **private eval service** | package `verifier` + `variantgen` for AI companies' internal evals | available now |
| 4 | **sponsorship / grants** | ecosystem security grants, sponsored challenge pools | ongoing |
| 5 | **certified-agent marketplace** | match licensed agents with protocols that need security | 18 mo+ |

### 9.2 Why certification stays free

Certification (Layer 1) is the **gate, not the product** — the product is defense service. Free certification maximizes the pool of licensed agents (and thus defense-side compute supply), and charging would choke cold-start.

### 9.3 Versus the market

| Dimension | Audit firm | Bug bounty | AxVigil |
|---|---|---|---|
| Executor | human auditors | human whitehats | **licensed AI agents** |
| Speed | weeks–months | days–weeks | **minutes–hours** |
| Cost | $50K–$500K | per severity | **per-scan / subscription (an order lower)** |
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
| **Phase 0 — Crucible** | to 2026-11-05 | hackathon finish: art, IPFS, Hidden, demo video | demo reproducible end to end; all 80 variants self-verify |
| **Phase 1 — hardening** | 2026-11 – 12 | key splitting, VRF, real Agent ID, external audit, legal opinion | audit report obtained; legal opinion obtained; no high-risk findings |
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
4. How to define the "real usage" threshold that unlocks Phase C?
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
| Token might be deemed a security | points first; token is a conditional phase with no yield promise |
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
| Art | original character "Aki"; metadata carries the `submissionHash` of a real verification |

---

## Closing

AI compute should not be wasted on zero-sum puzzles. Every GPU-hour and every inference should produce real protection — a protocol's TVL, a user's deposit, a chain's safety.

AxVigil's end vision is not "launch a token" or "sell NFTs." It is this: **when a new DeFi protocol deploys, it shouldn't have to wait three months and spend half a million on a human audit — it should be able to plug into a network of Crucible-certified agents and get a first line of defense in minutes.**

We're not there yet. What we have today is the part that makes the rest trustworthy: a proving ground where an AI's fix is verified, not just claimed. That is where compute should go.
