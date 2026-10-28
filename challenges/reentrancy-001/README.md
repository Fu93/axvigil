# Reentrancy 001

This is a deliberately vulnerable training fixture for AxVigil. The `Vault.withdraw` function sends ETH before reducing the caller's balance.

## Expected submission

A valid submission must:

1. Include a patch for `src/Vault.sol`.
2. Make `test/SubmittedPoC.t.sol` pass against the baseline, proving the bug exists.
3. Make the same PoC fail after the patch, proving the exploit no longer succeeds.
4. Pass `test/Hidden.t.sol` after the patch.
5. Stay within the verifier's patch limits.

The sample patch uses checks-effects-interactions: it reduces the balance before making the external call and relies on the transaction reverting if the transfer fails.
