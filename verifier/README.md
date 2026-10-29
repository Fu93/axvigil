# AxVigil verifier

One canonical grader: **`axvigil_verifier/`** (`python -m axvigil_verifier`). It grades any
challenge — the seed-variant challenges from [`../mothers/`](../mothers/) /
[`../variantgen/`](../variantgen/) and the patch-based `reentrancy-001` demo — in a hardened
sandbox. **Zero third-party dependencies** (keccak-256 is vendored).

## Use

```bash
# forge is required. It downloads solc; run `cd ../contracts && forge build` once,
# online, before the first grade. Set SOLC only to pin a binary.
export FORGE=$(which forge)

# grade a challenge's own reference solution:
python -m axvigil_verifier selfcheck --challenge ../challenges/reentrancy-vault

# grade a dir-based submission (patched/ + poc/):
python -m axvigil_verifier grade --challenge <dir> --submission <dir> --pretty

# grade a patch-based submission (a unified diff of the target + a PoC):
python -m axvigil_verifier grade --challenge ../challenges/reentrancy-001 \
  --patch .../sample.patch --poc .../sample_poc.t.sol

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

A length-prefixed canonical hash binds the solve:
`keccak256("AXV1" ‖ challengeId ‖ seed ‖ patched-source ‖ poc)` (details in `keccak.py`),
so different variants of a mother hash differently and the hash is independent of patch
formatting. The contract treats the value as opaque and only dedups it.

> The originally deployed `reentrancy-001` demo recorded its `submissionHash` with an
> earlier `AXVIGIL`-prefixed scheme (see `deployments/bsc-testnet-97.json`). The grader is
> now unified on the `AXV1` scheme above; a re-run or re-deploy uses the new value.
