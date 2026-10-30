# AxVigil — Hackathon Pitch

> **Verified fixes, not just findings.** AxVigil trains and certifies AI agents to *fix* smart-contract vulnerabilities — and proves each fix on-chain.

**Meta Global AI Developer Hackathon · BSC testnet (chain 97) · sandbox / whitehat**

---

## The one-liner

AxVigil is an **anti-memorization proving ground for security AI**. An agent is dealt a freshly generated vulnerable contract, writes a patch *and* a proof-of-concept exploit, and a deterministic sandboxed verifier confirms the bug is actually gone before anything is rewarded. A passing solve mints a **soulbound skill license** bound to the agent's identity — a credential that is earned, not claimed.

This proving ground (we call it **the Crucible**) is built, tested, and live on BSC testnet today. It is the trust root for a larger vision — a network that points AI compute at real contract security instead of zero-sum puzzle-solving — but the hackathon deliverable is the Crucible itself, and it works end to end.

---

## The problem

Two facts sit side by side in Web3 right now:

- **AI compute is being burned on nothing.** A wave of "agents solving puzzles" projects spend real GPU time on SAT instances, prime hunts and mazes, then mint an NFT to prove their agent is fast. The output protects no one.
- **Contract security doesn't scale.** DeFi exploits have cost billions; top audits run months and tens to hundreds of thousands of dollars; most newly deployed small protocols ship unaudited. AI can already draft plausible patches — but a plausible patch is not a verified fix, and nobody can currently tell the two apart at scale.

The gap between them is a **trust problem**: there is no independent, re-runnable way to show that an AI actually closed an exploit without breaking the contract. That is the gap AxVigil closes first.

---

## What we built (and why it's the hard part)

**1. An anti-memorization challenge engine (`mothers/` + `variantgen/`).**
Each "mother" is one vulnerability template. A seed renders a structurally unique variant every time — renamed identifiers, injected distractor functions, reordered bodies — and a structural fingerprint discards look-alikes before issue. So a public answer is worthless; the agent has to fix the *class* of bug, not recall a known hack.

- **4 mothers across 3 vulnerability classes and all 3 difficulty tiers**, each shipping **20 self-verified variants — 80 in all**.

| Mother | Class | Difficulty |
|---|---|---|
| `reentrancy` | Reentrancy | Basic |
| `access-control` | Access Control | Basic |
| `price-manipulation` | Price Manipulation | Advanced |
| `signature-replay` | Access Control | Legendary |

**2. A deterministic grader that scores the *difference*, not a test suite (`verifier/`).**
Four checks, every one required:

| Check | What it proves |
|---|---|
| `pocProvesBug` | the PoC exploits the *original* contract (no fake PoC) |
| `pocFailsAfterPatch` | the same PoC fails after the patch (the bug is actually gone) |
| `hiddenTestsPass` | hidden functional tests still pass (the fix didn't break the contract) |
| `patchWithinLimits` | changed-lines / bytes are capped (no "delete the whole contract" cheat) |

Runs in a hardened sandbox — `ffi` off, no network, wall-clock timeout and POSIX resource limits, its own process group — with **zero third-party dependencies**. Grading is reproducible and can't reach the host.

**3. A platform and on-chain credential layer.**
A FastAPI server issues challenges (the agent never sees the mother, the seed, the hidden tests or the reference solution), grades a submission in a session, and signs an EIP-712 authorization only for what passed. Login is a wallet signature **checked against the on-chain Agent ID registry (`ownerOf`)**. A passing solve lets the Agent ID owner mint:

- **`AxVigilSkill`** — an **ERC-5192 soulbound** license bound to the Agent ID (not a wallet), recording per-class counts and max difficulty. `locked()` is always true: it can't be sold or transferred, and it follows the agent.
- **`AxVigilCollectible`** — a free, cosmetic ERC-721 commemorating a real verification event (its metadata carries the `submissionHash`).

**Production reward rule:** the server deals the challenge — the caller can't pick the mother or difficulty, can't reroll, and opening a session spends one of **two lifetime attempts** whether it passes or not. Solves and mints stay strictly 1:1.

---

## Live proof (BSC testnet, chain 97)

- **Deployed and exercised on-chain.** `AxVigilSkill` `0x3377…CD18`, `AxVigilCollectible` `0x0658…4658`, Agent ID registry `0x7Aa4…d45e`.
- **A full flow has run against the live contracts:** a local backend doing a real-RPC Agent ID ownership check signed a MintAuth for a *server-dealt* legendary (pool 2) solve; Agent ID 1 minted token #1 (batch 1 committed, reveal pending). `submissionHash 0x8083…64df`.
- **All 80 variants self-verify:** the generator runs every variant's reference solution through the real grader before it ships. CI (Foundry + Python) is green on `main`.

Nothing here is a mock: the challenge an agent sees, the grade it gets, and the on-chain record are the same pipeline.

---

## Why it can't be gamed

- **Memorization doesn't help** — every challenge is a fresh, fingerprinted variant.
- **A fake fix can't pass** — the differential requires the exploit to work before and fail after, and the functional tests to still pass.
- **Brute-force "fixes" can't pass** — patch size is capped and the public interface must survive.
- **Farming is bounded** — server-dealt challenges, two lifetime attempts per Agent ID, hourly mint caps, API rate limits, an answer-leak circuit breaker, and a real Agent ID registry as a prerequisite.

---

## Where it goes (roadmap, not built yet)

The Crucible is Layer 1. The vision is to turn licensed agents into a **defense network**: automated first-pass review for newly deployed contracts, continuous monitoring, bounty-pool scanning — paid for out of real security budgets, not token speculation. That is deliberately future work, gated on the Crucible proving itself.

**One honest scope note.** Certification today proves an agent can *fix a known class* of bug on a controlled target. A production defense network also needs *finding unknown* issues in real code — a strictly harder problem the Crucible does not yet test. Layer 2 v1 is therefore scoped to **pattern-class detection and triage within an agent's licensed classes**, not open-ended 0-day hunting. We would rather ship a smaller true claim than a bigger one we can't back with code.

---

## Why this wins

We didn't build another benchmark screenshot or another NFT drop. We built the one piece this space is missing: **an independent, re-runnable way to prove an AI actually closed an exploit** — and wired it to a credential that can be trusted because it can't be bought. Everything above is running on testnet right now; clone the repo and the one-command demo reproduces it.
