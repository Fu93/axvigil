# AxVigil

An AI agent that **finds and fixes smart-contract vulnerabilities**, and earns an
on-chain, soulbound record of every bug it fixes. Built for the Meta Global AI
Developer Hackathon. Whitehat, sandbox only — BSC testnet (chainId 97).

The loop end to end:

```
      challenge                 agent (Meta Model API)              verifier
   vulnerable contract  ──►  read → patch + write a PoC exploit  ──►  grade in a
   + hidden tests            ▲                                   │    sandbox (forge)
                             └───────  feedback on failure  ◄────┘        │
                                                                          ▼  passed
                              backend ── grade-then-sign ──►  EIP-712 MintAuth / SkillAuth
                                                                          │
                                                                          ▼
                     AxVigilCollectible.mint() / recordSolve()  ──►  tradeable NFT
                                                              + soulbound skill record
```

A solve is only ever rewarded after the verifier confirms it, and each verified
solve (`submissionHash`) drives at most one on-chain action.

## Repository

| Path | What it is | Status |
|---|---|---|
| [`contracts/`](contracts/) | Foundry: `AxVigilCollectible` (ERC-721, EIP-712 mint, staged tier pools, commit-reveal) + `AxVigilSkill` (ERC-5192 soulbound record, on-chain SVG) | 65 tests passing |
| [`challenges/`](challenges/) | Challenge format + `reentrancy-vault` (vuln class 0) with hidden tests and a reference solution | 1 challenge |
| [`verifier/`](verifier/) | Deterministic sandboxed grader (`python -m verifier`), zero deps | 5 tests passing |
| [`backend/`](backend/) | FastAPI grade-then-sign service | e2e verified |
| [`agent/`](agent/) | Autonomous propose→grade→retry solve loop (Meta Model API) | offline dry-run passing |
| [`SPEC.md`](SPEC.md) | The binding interface shared by all modules | — |

## Quick start

```bash
# 0. tooling
curl -L https://foundry.paradigm.xyz | bash && foundryup   # forge
# (this repo was also validated with forge 1.7.1 from npm @foundry-rs/forge and a pinned solc 0.8.28)

# 1. contracts
cd contracts && git submodule update --init --recursive && forge test

# 2. the grader, against the challenge's own reference solution
cd ../verifier && python -m verifier selfcheck --challenge ../challenges/reentrancy-vault

# 3. the agent loop, offline (no API key): fail -> feedback -> pass
cd ../agent && python -m axvigil_agent solve --challenge ../challenges/reentrancy-vault --oracle

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
- Added the verifier, the first challenge, the backend and the agent loop (this was
  the `agent/`, `verifier/`, `backend/` work the SPEC reserved).

## Not for production

Hackathon-grade randomness (commit-reveal, not VRF) and a testnet-only
`MockAgentID`. See the caveats in [`contracts/README.md`](contracts/README.md).
