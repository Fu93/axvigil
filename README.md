# AxVigil

An AI agent that **finds and fixes smart-contract vulnerabilities**, and earns an
on-chain, soulbound record of every bug it fixes. Built for the Meta Global AI
Developer Hackathon. Whitehat, sandbox only — BSC testnet (chainId 97).

The loop end to end:

```
   mother (母題)            agent (Meta Model API)              verifier
   + seed → VARIANT   ──►  read → patch + write a PoC exploit  ──►  grade in a
   (unique each time)      ▲                                   │    sandbox (forge)
                           └───────  feedback on failure  ◄────┘        │
                                                                        ▼  passed
                            backend ── grade-then-sign ──►  EIP-712 MintAuth / SkillAuth
                                                                        │
                                                                        ▼
                   AxVigilCollectible.mint() / recordSolve()  ──►  tradeable NFT
                                                            + soulbound skill record
```

Every challenge is a fresh **variant** rendered from a mother template with a unique
seed, so a model can't win by memorizing a public answer — it has to actually fix the
bug class. A solve is only rewarded after the verifier confirms it, and each verified
solve (`submissionHash`) drives at most one on-chain action.

## Repository

| Path | What it is | Status |
|---|---|---|
| [`contracts/`](contracts/) | Foundry: `AxVigilCollectible` (ERC-721, EIP-712 mint, staged tier pools, commit-reveal) + `AxVigilSkill` (ERC-5192 soulbound record, on-chain SVG) | 67 tests passing |
| [`mothers/`](mothers/) | The three母題: reentrancy, price-manipulation, access-control (vuln classes 0/1/2), as seed templates | 3 mothers |
| [`variantgen/`](variantgen/) | Seed variant generator — the anti-memorization engine (`python -m variantgen`) | 3×20 unique solvable; 13 tests |
| [`challenges/`](challenges/) | Challenge format + `reentrancy-vault`, the hand-authored reference challenge | 1 challenge |
| [`verifier/`](verifier/) | Deterministic sandboxed grader (`python -m verifier`), zero deps | 5 tests passing |
| [`backend/`](backend/) | FastAPI grade-then-sign service | e2e verified |
| [`agent/`](agent/) | Autonomous propose→grade→retry solve loop (Meta Model API) | runs on generated variants |
| [`SPEC.md`](SPEC.md) | The binding interface shared by all modules | — |

## Quick start

```bash
# 0. tooling
curl -L https://foundry.paradigm.xyz | bash && foundryup   # forge
# (this repo was also validated with forge 1.7.1 from npm @foundry-rs/forge and a pinned solc 0.8.28)

# 1. contracts
cd contracts && git submodule update --init --recursive && forge test

# 2. generate variants and confirm all three mothers produce 20 unique, solvable ones
cd ../variantgen
python -m variantgen verify-mother --mother ../mothers/reentrancy --count 20
python -m variantgen render --mother ../mothers/price-manipulation --seed 42 --out /tmp/variant42

# 3. the agent loop on a freshly generated variant, offline (no API key): fail -> feedback -> pass
cd ../agent && python -m axvigil_agent solve --challenge /tmp/variant42 --oracle

# 4. the backend (grade -> sign)
cd ../backend && pip install -r requirements.txt
cp .env.example .env   # set SIGNER_KEY + VERIFYING_CONTRACT after deploy
uvicorn axvigil_backend.app:app --port 8000
```

With a real `META_API_KEY`, step 3 becomes a live solve against Muse Spark; the
`submissionHash` it produces is what the backend signs in step 4 and what
`AxVigilCollectible` checks on chain.

## How cheating is prevented

The verifier scores four independent checks (details in
[`verifier/README.md`](verifier/README.md)); the guarantees come from combining them:

- **Fake fix** (unchanged contract) → the PoC still drains it → `pocFailsAfterPatch=false`.
- **Gutted contract** (delete the function) → `patchWithinLimits=false` + hidden tests fail.
- **No-op PoC** → passes on both versions, so it never *fails after patch* → the differential rejects it.

On chain: the backend signer is kept separate from the owner/seed key (the seed
holder can predict commit-reveal rarity), `submissionHash` is deduped across both
reward paths, and the skill record is non-transferable and admin-revocable.

## What changed recently

- Contracts: skill records were capped at 2 (a side effect of the 2-collectible
  mint limit), so an agent could never light up all three class emblems. Added a
  signed `recordSolve` path that records a solve without minting or consuming the
  quota, plus on-chain `submissionHash` dedup. See [`contracts/README.md`](contracts/README.md).
- Added the verifier, the backend and the agent loop (the `verifier/`, `backend/`,
  `agent/` work the SPEC reserved).
- Added all three母題 and the seed variant generator — the PRD's core anti-memorization
  mechanism. Each mother yields 20/20 unique, solvable variants, and the agent loop
  runs end to end on a generated variant. See [`variantgen/README.md`](variantgen/README.md).

## Not for production

Hackathon-grade randomness (commit-reveal, not VRF) and a testnet-only
`MockAgentID`. See the caveats in [`contracts/README.md`](contracts/README.md).
