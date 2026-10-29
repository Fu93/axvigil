# AxVigil verifier

Two graders live here, sharing the SPEC result shape:

- **`axvigil_verifier/`** — the canonical, general grader (`python -m axvigil_verifier`).
  Grades any challenge directory (`src/`, `test/Hidden.t.sol`, a submission's
  `patched/` + `poc/`), powers the seed-variant challenges in [`../mothers/`](../mothers/)
  and [`../variantgen/`](../variantgen/), and runs submitted code in a hardened sandbox.
  Zero third-party deps (keccak-256 is vendored).
- **`reentrancy_grader.py`** — the single-file, patch-based grader used by the deployed
  `reentrancy-001` live demo and the `scripts/*.sh` / `*Demo.s.sol` flows
  (`python -m verifier.reentrancy_grader`). Kept for reproducibility of the on-chain
  demo; needs `pycryptodome` (see `requirements.txt`).

## Canonical grader

```bash
export FORGE=$(which forge); export SOLC=$(which solc)      # or a pinned solc-0.8.28

# grade a challenge's own reference solution:
python -m axvigil_verifier selfcheck --challenge ../challenges/reentrancy-vault

# grade a submission:
python -m axvigil_verifier grade --challenge <dir> --submission <dir> --pretty

# compute a submissionHash:
python -m axvigil_verifier hash --challenge-id <id> --seed 0 --patch p.sol --poc Poc.t.sol
```

Four deterministic checks → `passed` = all four:

| Field | Meaning |
|---|---|
| `pocProvesBug` | the PoC **passes** on the **original** contract |
| `pocFailsAfterPatch` | the same PoC **fails** on the **patched** contract |
| `hiddenTestsPass` | the hidden functional tests **pass** on the **patched** contract |
| `patchWithinLimits` | bounded changed lines/bytes, contract + public interface preserved |

The anti-gaming guarantees come from the **differential** (pass-on-vulnerable ∧
fail-on-patched) plus the limits check: a fake fix, a gutted contract and a no-op PoC
are all rejected (`tests/test_grader.py`).

## Sandbox

Submitted code is untrusted, so every run is isolated: a throwaway project, `ffi`
disabled, no network (`FOUNDRY_OFFLINE`), a fixed fuzz seed, a wall-clock timeout, and
POSIX resource limits (CPU / memory / file-size / process count) in a new process
group. `tests/test_sandbox.py` proves `vm.ffi` and `vm.readFile` are refused.

## submissionHash

`axvigil_verifier` binds the solve with a length-prefixed canonical hash
`keccak256("AXV1" ‖ challengeId ‖ seed ‖ patch ‖ poc)` (details in `keccak.py`), so
different variants of a mother hash differently. The legacy `reentrancy_grader.py`
uses its own `keccak256("AXVIGIL\n" ‖ patch ‖ "---POC---" ‖ poc)` scheme, which is what
the deployed `reentrancy-001` demo recorded. Both are opaque to the contract, which
only dedups the value.
