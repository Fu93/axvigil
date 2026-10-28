# AxVigil verifier

A deterministic, sandboxed grader. Given a **challenge** (a vulnerable contract +
hidden functional tests) and a **submission** (a patched contract + a PoC test), it
decides whether the agent genuinely found and fixed the bug, and emits the result
JSON defined in [`../SPEC.md`](../SPEC.md).

It has **no third-party Python dependencies** (keccak-256 is implemented in
`verifier/keccak.py`) so it runs identically on a laptop, in CI, and in the demo
backend. The only external tools are `forge` and a Solidity compiler.

## Install / run

```bash
# forge + a solc must be on PATH, or pass them via env:
export FORGE=$(which forge)
export SOLC=$(which solc)     # or a pinned solc-0.8.28 binary

# Grade the reference solution shipped with a challenge (CI sanity check):
python -m verifier selfcheck --challenge ../challenges/reentrancy-vault

# Grade a real submission:
python -m verifier grade \
  --challenge  ../challenges/reentrancy-vault \
  --submission /path/to/submission \
  --seed 0 --solve-seconds 143 --pretty

# Just compute a submissionHash (what the backend signs, what the chain checks):
python -m verifier hash --challenge-id reentrancy-vault --seed 0 \
  --patch submission/patched/Vault.sol --poc submission/poc/Poc.t.sol
```

`grade` prints the SPEC result JSON to stdout and exits `0` if `passed`, else `1`.

## Layout

```
challenges/<id>/
  challenge.json          # metadata + patch limits (see below)
  src/*.sol               # the vulnerable target(s); solver patches targetFile
  test/Hidden.t.sol       # hidden functional tests the patch must keep green
  solution/               # reference fix, graded by `selfcheck`
    patched/<targetFile>
    poc/*.t.sol

submission/
  patched/<targetFile>    # the agent's fixed contract
  poc/*.t.sol             # the agent's proof-of-concept exploit test
```

`challenge.json`:

```json
{
  "challengeId": "reentrancy-vault",
  "vulnClass": 0, "difficulty": 0,
  "targetFile": "Vault.sol", "contractName": "Vault",
  "requiredFunctions": ["deposit", "withdraw", "totalAssets"],
  "hiddenTests": "Hidden.t.sol",
  "limits": { "maxChangedLines": 30, "maxBytes": 4000 }
}
```

## How grading works

Four independent, deterministic checks (`passed` = all four):

| Field | Meaning |
|---|---|
| `pocProvesBug` | the PoC **passes** against the **original** contract — it really triggers the vuln |
| `pocFailsAfterPatch` | the same PoC **fails** against the **patched** contract — the fix closes exactly that hole |
| `hiddenTestsPass` | the hidden functional tests **pass** against the **patched** contract — the fix didn't break intended behaviour |
| `patchWithinLimits` | bounded changed lines / bytes, and the target contract + its public interface still exist |

The anti-gaming guarantees fall out of combining these, not from any one:

- A **fake fix** (unchanged contract) → PoC still drains it → `pocFailsAfterPatch=false`.
- A **gutted contract** (delete the vulnerable function) → `patchWithinLimits=false` (interface removed) and `hiddenTestsPass=false`.
- A **no-op PoC** (`assertTrue(true)`) passes on the original *and* the patch, so it never "fails after patch" → `pocFailsAfterPatch=false`. Credit needs the **differential**: pass-on-vulnerable **and** fail-on-patched.

Each check runs in a throwaway temp project with `FOUNDRY_OFFLINE=true`, a fixed
fuzz seed, and a wall-clock timeout. Submitted code never touches the host project.

`tests/test_grader.py` exercises the reference solution and all three adversarial
cases above; it skips automatically if `forge`/`solc` are not present.

## submissionHash (shared with the backend and the chain)

`submissionHash` binds the signed mint/skill authorization to the exact solve. It is
`keccak256` of a length-prefixed canonical encoding:

```
keccak256(
  b"AXV1"
  || u32be(len(challengeId)) || challengeId
  || u64be(seed)
  || u32be(len(patch_canon)) || patch_canon
  || u32be(len(poc_canon))   || poc_canon
)
```

`patch_canon` / `poc_canon` are the source normalized to LF line endings with
per-line trailing whitespace stripped and a single trailing newline, so cosmetic
reformatting does not change the hash but any semantic change does. The backend
recomputes this before signing an `EIP-712` `MintAuth` / `SkillAuth`, and the
contract stores it so a verified solve drives at most one on-chain action.
