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
behaviour. This is the only accepted class of fix: patches that merely neutralize the
`address(0)` instance (a `token != address(0)` guard, or un-listing `address(0)`) are
**rejected**, because any other codeless address still phantom-deposits (see Closed gaps).

### Verify

```bash
PATH=$HOME/.foundry/bin:$PATH python3 scripts/realbank_verify.py mothers/bridge-phantom-deposit 20
```

The script renders 20 unique variants and checks that 20/20 reference fixes pass. It then
runs grader negative controls on seed 0:

- A no-op patch fails.
- An over-eager "require a bool return" fix fails the hidden tests (it breaks no-return tokens).
- A gutted deposit fails the hidden tests.
- Both address(0)-only instance patches fail the hidden tests: a `token != address(0)`
  guard (`instance_zero_address_guard`) and un-listing `address(0)` (`instance_unlist_zero`).

The last recorded run is in [`verify_log.txt`](verify_log.txt).

### Closed gaps

1. **`require(token != address(0))` (and un-listing `address(0)`) no longer pass** — closed
   2026-10-30. The canonical PoC uses the `address(0)` special case, so a patch that only
   neutralizes the zero address makes that PoC revert and would otherwise look fixed. But
   the bug class is "a low-level call succeeds on any address with no code", so every
   non-zero codeless token is still exploitable. The hidden test
   `test_codelessNonZeroTokenCannotPhantomDeposit` lists a non-zero codeless token and
   requires the deposit to be refused; only the class fix (reject codeless tokens) passes.
   Because un-listing `address(0)` shares the identical blind spot, it is rejected too —
   both are reproduced as negative controls in `realbank_verify.py`.

## `empty-market-inflation` · Empty-Market Share Inflation

| | |
|---|---|
| Incident | Compound-fork empty-market share inflation — Hundred Finance (Apr 2023, ~$7M) and Sonne Finance (May 2024, ~$20M). Patched and public. |
| Mother | [`mothers/empty-market-inflation/`](../../mothers/empty-market-inflation/) |
| vulnClass | **1 (price manipulation)** — an economic/accounting exploit of a manipulable live value. Within the deployed `NUM_CLASSES = 3` cap. |
| Difficulty | 1 (advanced) |
| Reference fix | `fix_share_inflation` in [`variantgen/variantgen/fixes.py`](../../variantgen/variantgen/fixes.py) (`fixId` `share_inflation`). Pools in `variantgen/variantgen/pools.py`. |
| Sources | rekt.news (Hundred, Sonne) and the OpenZeppelin ERC-4626 inflation-attack note (links in `mother.json` → `realWorld`). Re-implemented from the public description; no protocol code copied. |

**Self-contained, no fork.** A minimal share vault over one mock ERC20, with PoC and hidden
tests as plain Foundry tests on a fresh local EVM.

**The bug.** The vault prices shares off its **live asset balance** (`balanceOf(this)`). An
attacker seeds the empty vault with 1 wei (1 share), then transfers a large amount straight
to the vault — a *donation* that inflates the share price without minting shares. A later
honest deposit rounds down against the inflated price (to a single share or zero), and the
attacker redeems its one share for the whole pool, including the victim's deposit.

**Reference fix.** Value the pool by the assets actually deposited **through** the vault (a
donation-resistant book value the mother already tracks), not the raw token balance — so a
direct transfer cannot move the share price. The fix reroutes the pricing reads from the live
balance helper to the book-value helper (a minimal, interface-preserving change).

**Grading.** The PoC passes on the original and fails after the fix (differential). A hidden
test, `test_donationCannotStealFromLaterDepositor`, encodes the economic invariant: after a
donation, an honest depositor must recover ~their principal. This rejects partial patches
that merely block zero-share deposits (e.g. `require(shares > 0)`), which still let the
inflated price skew a real deposit and lose the depositor's funds — only the donation-resistant
class fix passes. Verify with `scripts/verify_empty_market.py`.
