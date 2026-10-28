# AxVigil verifier

The first verifier slice grades `reentrancy-001` deterministically:

1. Run the submitted PoC against the vulnerable baseline; it must pass.
2. Apply the submitted patch with `git apply`; malformed or oversized patches fail.
3. Run the same PoC again; it must fail after the fix.
4. Run hidden behavior tests; they must pass after the fix.
5. Hash the canonical patch and PoC bytes with Keccak-256.

## Usage

From the repository root:

```bash
pip install -r verifier/requirements.txt
python -m verifier.verifier \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol \
  --json
```

Foundry and the repository's `forge-std` submodule are required to execute the Solidity tests. The command emits the result shape described in [`SPEC.md`](../SPEC.md), including `submissionHash` and the individual grading booleans.
