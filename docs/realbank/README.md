# Real-incident challenges

AxVigil's first challenges were synthetic patterns. This track rebuilds **real, already
patched and publicly documented exploits** as self-contained mothers. They use the same
format and the same `variantgen` and grader pipeline as the rest of the bank.

## `bridge-phantom-deposit` · Phantom Bridge Deposit (first real-incident challenge)

| | |
|---|---|
| Incident | Qubit Finance QBridge, 27–28 Jan 2022 (~$80M reported). Patched and public. |
| Mother | [`mothers/bridge-phantom-deposit/`](../../mothers/bridge-phantom-deposit/) |
| vulnClass | **2 (access control)**. Deposit validation is missing. Class 2 is used because the deployed contracts cap `NUM_CLASSES` at 3. |
| Difficulty | 1 (advanced) |
| Reference fix | `fix_bridge_phantom_deposit` in [`variantgen/variantgen/fixes.py`](../../variantgen/variantgen/fixes.py) (`fixId` `bridge_phantom_deposit`). Pools are in `variantgen/variantgen/pools.py`. |
| Sources | Qubit post-mortem, rekt.news, CertiK and DeFiHackLabs `Qubit_exp.sol` (links in `mother.json` → `realWorld`). Re-implemented from the public description. No Qubit code is copied. |

**Self-contained, no fork.** The bridge, PoC and hidden tests are plain Foundry tests on a
fresh local EVM, with no RPC, no mainnet fork and no external state.

**The bug.** The native coin is tracked as token `address(0)`, and that token is listed.
The ERC20 deposit path pulls tokens with a low-level `transferFrom` call that tolerates
empty return data. A call to an address with no code succeeds and returns nothing, so
depositing against the native resource credits a deposit that moved nothing. The attacker
then withdraws it as real native coin locked by honest users.

**Reference fix.** The pull helper refuses tokens with no code
(`require(token.code.length > 0)`), which is the OpenZeppelin SafeERC20 / `Address`
behaviour. Un-listing `address(0)` is also accepted.

### Verify

```bash
PATH=$HOME/.foundry/bin:$PATH python3 scripts/realbank_verify.py mothers/bridge-phantom-deposit 20
```

The script renders 20 unique variants and checks that 20/20 reference fixes pass. It then
runs grader negative controls on seed 0:

- A no-op patch fails.
- The alternative un-list fix passes.
- An over-eager "require a bool return" fix fails the hidden tests.
- A gutted deposit fails the hidden tests.

The last recorded run is in [`verify_log.txt`](verify_log.txt).

### Known gaps

1. **`require(token != address(0))` falsely passes.** The canonical PoC relies on the
   `address(0)` special case. A patch that only blocks the zero address makes that PoC
   revert, so `pocFailsAfterPatch` holds and the grader accepts it. Every other codeless
   token is still exploitable. `realbank_verify.py` reproduces this as the
   `known_gap1_zero_address_only` control, which is reported but does not fail the run.
   Planned fix: add a hidden invariant test that a deposit is only credited for what the
   bridge actually received, run against a codeless non-zero token.
