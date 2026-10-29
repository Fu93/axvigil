# Reentrancy 001

This is a deliberately vulnerable training fixture for AxVigil. `Vault.withdrawAll` sends ETH before clearing the caller's balance.

## Expected submission

A valid submission must:

1. Include a patch for `src/Vault.sol`. The sample is `submissions/sample.patch`.
2. Include a Foundry PoC. The sample is `submissions/sample_poc.t.sol`. It must pass against the original contract, proving the bug exists.
3. Make that same PoC fail after the patch, proving the exploit no longer succeeds.
4. Pass `test/Hidden.t.sol` after the patch.
5. Stay within the verifier's patch limits.

Grade the sample from the repo root after `cd contracts && forge build` has cached solc:

```bash
PYTHONPATH=verifier python3 -m axvigil_verifier grade \
  --challenge challenges/reentrancy-001 \
  --patch challenges/reentrancy-001/submissions/sample.patch \
  --poc challenges/reentrancy-001/submissions/sample_poc.t.sol
```

The sample patch uses checks-effects-interactions: it reduces the balance before making the external call and relies on the transaction reverting if the transfer fails.
