# AxVigil backend

FastAPI service that turns a verified solve into an on-chain authorization. It
**grades first, signs second**: a `MintAuth` / `SkillAuth` is only ever signed for
a submission the verifier passed, and it carries the exact `submissionHash` the
verifier computed — so the signature, the grade and the chain all agree on one
solve.

```
GET  /health       signer address, chainId, verifyingContract, known challenges
GET  /challenges   list challenges (id, class, difficulty, title)
POST /submit       grade a submission; if it passes, return a signed auth
```

## Run

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env            # set SIGNER_KEY + VERIFYING_CONTRACT (deployed address)
set -a && . ./.env && set +a    # forge + solc must be reachable (PATH or FORGE/SOLC)
uvicorn axvigil_backend.app:app --reload --port 8000
```

Without `SIGNER_KEY`/`VERIFYING_CONTRACT` the service still grades and returns the
result, just with no signature (handy for local challenge development).

## `POST /submit`

```jsonc
{
  "challengeId": "reentrancy-vault",
  "agentId": 7,                 // Agent ID token the caller owns in the registry
  "to": "0x...",                // collectible recipient (mint action)
  "patch": "<patched Vault.sol source>",
  "poc":   "<Poc.t.sol source>",
  "pool": 1,                    // 0 NORMAL, 1 PREMIUM
  "seed": 0,
  "action": "mint"             // or "skill" (record only, no collectible, no quota)
}
```

On a pass:

```jsonc
{
  "passed": true,
  "result": { /* the full SPEC grade JSON, incl. submissionHash */ },
  "action": "mint",
  "auth": {
    "agentId": 7, "to": "0x...", "vulnClass": 0, "difficulty": 0, "pool": 1,
    "submissionHash": "0x...", "nonce": 123456789, "deadline": 1893456000
  },
  "signature": "0x<65-byte r||s||v>",
  "signer": "0x..."
}
```

The caller (the Agent ID owner) submits `auth` + `signature` to
`AxVigilCollectible.mint(auth, sig)` (or `recordSolve(auth, sig)` for the skill
action). The contract re-checks the signature, the caller's Agent ID ownership,
nonce and `submissionHash` uniqueness.

## Security notes (for the demo talk)

- **The signer key is not the owner/seed key.** Whoever holds the commit-reveal
  seed can predict rarity; keeping the signer separate is the mitigation the
  contract README calls for.
- **One solve, one action.** `submissionHash` is deduped on-chain across both
  `mint` and `recordSolve`, so a signed auth can't be replayed into both.
- **Nonces are random 256-bit.** No shared counter to coordinate or corrupt;
  collisions are negligible and the chain rejects any reuse.
- EIP-712 encoding is cross-checked against the contract in
  `contracts/test/EIP712Digest.t.sol`.
