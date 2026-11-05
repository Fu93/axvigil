# AxVigil — Hackathon Pitch

> **Verified fixes, not just findings.** AxVigil trains and shows on a record AI agents to *fix* smart-contract vulnerabilities — and proves each fix on-chain.

**Meta Global AI Developer Hackathon · BSC testnet (chain 97) · sandbox / whitehat**

---

## The one-liner

AxVigil is an **anti-memorization proving ground for security AI**. An agent is dealt a freshly generated vulnerable contract, writes a patch *and* a proof-of-concept exploit, and a deterministic sandboxed verifier confirms the bug is actually gone before anything is rewarded. A passing solve mints a **soulbound skill capability record** bound to the agent's identity — a capability record that is earned, not claimed.

This proving ground (we call it **the Crucible**) is built, tested, and live on BSC testnet today. It is the trust root for a larger vision — a network that points AI compute at real contract security instead of zero-sum puzzle-solving — but the hackathon deliverable is the Crucible itself, and it works end to end.

---

## The problem

Two facts sit side by side in Web3 right now:

- **AI compute is being burned on nothing.** A wave of "agents solving puzzles" projects spend real GPU time on SAT instances, prime hunts and puzzles, then mint an NFT to prove their agent is fast. The output protects no one.
- **Contract security doesn't scale.** DeFi exploits have cost billions; top audits run months and tens to hundreds of thousands of dollars; most newly deployed small protocols ship unaudited. AI can already draft plausible patches — but a plausible patch is not a verified fix, and nobody can currently tell the two apart at scale.

The gap between them is a **trust problem**: there is no independent, re-runnable way to show that an AI actually closed an exploit without breaking the contract. That is the gap AxVigil closes first.

---

## What we built (and why it's the hard part)

**1. An anti-memorization challenge engine (`variantgen/` and the family-template directory).**
Each "vulnerability family" is one vulnerability template. A seed renders a structurally unique fresh rewrite every time — renamed identifiers, injected distractor functions, reordered bodies — and a structural fingerprint discards look-alikes before issue. So a public answer is worthless; the agent has to fix the *class* of bug, not recall a known hack.

- **9 vulnerability families across 3 vulnerability classes and all 3 difficulty tiers** (including 5 minimal offline reproductions of DeFi incidents), each tested for 20 distinct fresh rewrites, **180 in all**. The arena benchmarks 6 of the 9. Five rebuild already-patched public incidents, and the grader accepts only the class fix.

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

**2. A deterministic grader that scores the *difference*, not a test suite (`verifier/`).**
Five checks, every one required:

| Check | What it proves |
|---|---|
| `pocProvesBug` | the PoC exploits the *original* contract (no fake PoC) |
| `pocFailsAfterPatch` | the same PoC fails after the patch (the bug is actually gone) |
| `hiddenTestsPass` | hidden functional tests still pass (the fix didn't break the contract) |
| `patchWithinLimits` | changed-lines / bytes are capped (no "delete the whole contract" cheat) |
| `invariantsHold` | Foundry fuzz & stateful invariants (2000 fuzz + 256 invariant runs at seed `0xA11CE`) prevent test-specific cheating |

Runs in a hardened sandbox — `ffi` off, no network, wall-clock timeout and POSIX resource limits, its own process group — with **zero third-party dependencies**. Grading is reproducible and can't reach the host.

**3. A platform and on-chain capability record layer.**
A FastAPI server issues challenges (the agent never sees the vulnerability family, the seed, the hidden tests or the reference solution), grades a submission in a session, and signs an EIP-712 authorization only for what passed. Login is a wallet signature **checked against the on-chain Agent ID registry (`ownerOf`)**. A passing solve lets the Agent ID owner mint:

- **`AxVigilSkill`** — an **ERC-5192 soulbound** capability record bound to the Agent ID (not a wallet), recording per-class counts and max difficulty. `locked()` is always true: it can't be sold or transferred, and it follows the agent.
- **`AxVigilCollectible`** — a free, cosmetic ERC-721 commemorating a real verification event (its metadata carries the `submissionHash`).
- **`AxVigilZKVerifier`** — the on-chain half of a planned **SP1 zkVM** path. Decodes the 288-byte journal (`agentId`, `challengeId`, `patchCommitment`, `vulnClass`, `difficulty`, `checksBitmap`), calls an `ISP1Verifier`, verifies Agent ID ownership, and records the soulbound skill with a domain-bound nullifier (`keccak256(chainid, address(this), agentId, challengeId)`) and lifetime solve quota (`MAX_SOLVES_PER_AGENT = 2`). **Status:** tested against a mock verifier only. There is no SP1 prover program yet, and the off-chain bundle carries a simulated placeholder proof, so live mints use the 2-of-3 EIP-712 path.

**Production reward rule:** the server deals the challenge — the caller can't pick the vulnerability family or difficulty, can't reroll, and opening a session spends one of **two lifetime attempts** whether it passes or not. Solves and mints stay strictly 1:1.

---

## Live proof (BSC testnet, chain 97)

> [!NOTE]
> **Deployment & Verification Note:**
> - **Public Testnet (BSC Chain ID 97)**: The deployed addresses below represent our **PR #8 snapshot** deployment.
> - **Latest Features**: The newly integrated `AxVigilChallenge` (Optimistic Challenge Window), `AxVigilZKVerifier` (verifier contract for a planned SP1 path; tested with a mock verifier, no real prover yet), and Foundry Invariant fuzzing test suites (`invariantsHold`) are fully integrated and verified locally.
> - **Judge Reproduction**: To review and verify the complete, bleeding-edge architecture with zero network dependencies, judges can run a single command locally:
>   `./scripts/judge_demo.sh`
>   *(Runs local Anvil, offline oracle agent, verifier checks, EIP-712 signing, and dynamic SVG metadata output).*
> - **Live Meta Model API End-to-End Demo**: To watch the complete official pipeline driven live by the Meta Model API (`muse-spark-1.1`, `1.2`, `1.3`; each model is dealt its own server-chosen challenge, so scores are not a like-for-like comparison), judges can run:
>   `python scripts/meta_official_flow_demo.py`
>   *(Performs web entry check, Anvil deployment with ZK verifier, EIP-191 auth, live Meta AI inference, differential grading (4 core checks, plus `invariantsHold` when the challenge has a suite), attestation journal with a simulated proof, EIP-712 co-signing, on-chain minting, commit-reveal art draw, and leaderboard ranking update).*

- **Deployed and exercised on-chain.** Original skill `0x3377…CD18`, collectible `0x0658…4658` (signer rotated to `0x91Ae…e081`; token #2 revealed LEGENDARY, artId 320000). Threshold 2-of-3 collectible `0x0e87…C8eB`, skill `0xE165…5F59`, validators `0xc32d…95F9` / `0xD5f5…4645` / `0x133F…ec7f`. Registry `0x7Aa4…d45e` is still MockAgentID.
- **Muse Spark (`muse-spark-1.1`) on the threshold contract:** three server-dealt sessions, each solved on the first request, each evidence bundle re-checked (`verify_evidence.py` OK), each mint using 2 of 3 validator signatures. Grading used the subprocess sandbox, not Docker. The earlier signature-replay mint on `0x0658…4658` is token #2. The reference smoke test is token #1, tier COMMON. `submissionHash` of that smoke test is `0x8083…64df`.
- **Live Meta Model API Nomad Bridge Solve:** `muse-spark-1.1` diagnosed the Nomad Bridge zero-root authorization bypass in 13.7s, completed 5/5 differential checks (`0x1F` bitmap) with dynamic storage layout preservation in 17.16s, built the attestation journal (simulated proof), and minted Token #1 on local Anvil via the EIP-712 path.
- **Offline bank: 180 fresh rewrites (9 vulnerability families × 20), each fingerprint-checked as distinct; live deals reference-check the seed before it is shown.** Live deals also reference-check the seed and skip a repeated structural fingerprint before the source is shown. CI (Foundry + Python) is green: 315 tests passed, 1 skipped (contracts 122 · Python 193).

The challenge an agent sees, the grade it gets, and the on-chain record are the same pipeline. Two parts are still stand-ins and are labelled as such: the Agent ID registry (`MockAgentID`) and the ZK proof (simulated placeholder).

---

## Why it can't be gamed

### Threat Model & Current Trust Assumptions (Pragmatic Disclosure)
In the spirit of cryptographic transparency, we explicitly document the security boundaries of this hackathon release:
- **What Attackers CANNOT Do**:
  - Forge a passed grading result without valid validator ECDSA/EIP-712 signatures.
  - Bypass `invariantsHold` with test-specific hardcoding (enforced by 2000 Foundry fuzz runs at fixed seed `0xA11CE`).
  - Transfer or steal skill credentials (ERC-5192 Soulbound to SPACE ID-compatible Agent ID).
- **Current Centralization Boundaries (Roadmap for v2)**:
  - *Validator Quorum*: Currently operates as a 2-of-3 permissioned quorum run by the deployment team. Transitioning to decentralized AVS / TEE coprocessors is slated for v2.
  - *Randomness*: Mint rarity uses demo commit-reveal randomness with documented liveness/validator influence trade-offs; Chainlink VRF v2.5 integration is planned for mainnet.
  - *Admin Capabilities*: Contract owner currently retains pause controls, per-agent quotas, and skill revocation rights.

### Anti-Gaming Guardrails

- **Memorization doesn't help** — every challenge is a fresh, fingerprinted fresh rewrite.
- **A fake fix can't pass** — the differential requires the exploit to work before and fail after, and the functional tests to still pass.
- **Storage corruption & slot shifts detected** — dynamic EVM storage layout preservation check (`forge inspect storage-layout --json`) fails patches that delete, shift, or re-order variables.
- **Anti-cheat decoy PoC & patch cheatcode guard** — static inspection rejects PoCs probing `.code.length`, `extcodesize`, `extcodehash`, `.codehash`, `type(...).runtimeCode`, `type(...).creationCode`, `gasleft()`, or `selfbalance()` to simulate vulnerabilities without true state manipulation, and rejects patches that import `forge-std/Vm.sol` or call `0x7109709ECfa91a80626fF3989D68f67F5b1DD12D`.
- **Anti-collusion reference PoC check** — when a challenge ships a canonical `solution/poc/Poc.t.sol`, the patched contract must also repel the ground-truth exploit, not only the agent's self-authored PoC.
- **Brute-force "fixes" can't pass** — patch size is capped and the public interface must survive.
- **Farming is bounded** — server-dealt challenges, two lifetime attempts per Agent ID, hourly mint caps, API rate limits, an answer-leak circuit breaker, and a real Agent ID registry as a prerequisite.

---

## Where it goes (roadmap, not built yet)

The Crucible is Layer 1. The vision is to turn recorded agents into a **defense network**: automated first-pass review for newly deployed contracts, continuous monitoring, bounty-pool scanning — paid for out of real security budgets, not token speculation. That is deliberately future work, gated on the Crucible proving itself.

**One honest scope note.** Passing record today proves an agent can *fix a known class* of bug on a controlled target. A production defense network also needs *finding unknown* issues in real code — a strictly harder problem the Crucible does not yet test. Layer 2 v1 is therefore scoped to **pattern-class detection and triage within an agent's recorded classes**, not open-ended 0-day hunting. We would rather ship a smaller true claim than a bigger one we can't back with code.

---

## Why this wins

We didn't build another benchmark screenshot or another NFT drop. We built the one piece this space is missing: **an independent, re-runnable way to prove an AI actually closed an exploit** — and wired it to a capability record that can be trusted because it can't be bought. Everything above is running on testnet right now; clone the repo and the one-command demo reproduces it.
