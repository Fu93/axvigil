# Mothers (母題)

Each mother is one vulnerability template. The seed variant generator in
[`../variantgen/`](../variantgen/) renders a mother + seed into a concrete,
gradeable challenge. The six mothers span three distinct vulnerability classes
and all three difficulty tiers (basic, advanced, legendary), and are derived from
well-known, publicly documented bug patterns (sandbox toys — do not deploy to
mainnet).

| Mother | Vuln class | Difficulty | The bug | The intended fix |
|---|---|---|---|---|
| `reentrancy` | 0 reentrancy | 0 basic | `withdraw` makes the external call before zeroing the balance | checks-effects-interactions (zero first) |
| `price-manipulation` | 1 price manipulation | 1 advanced | collateral is valued at the live spot price, movable by a swap in the same tx | value at the manipulation-resistant reference price |
| `access-control` | 2 access control | 0 basic | a privileged treasury sweep has no owner check | restrict to the owner |
| `signature-replay` | 2 access control | 2 legendary | a signed voucher is never recorded as spent, so the signature can be replayed to drain the treasury | mark each voucher digest spent after the signature check |
| `bridge-phantom-deposit` (real incident) | 2 access control | 1 advanced | a bridge credits ERC20 deposits pulled via a low-level call that "succeeds" on an address with no code (the native resource maps to `address(0)`), so a deposit that moved nothing is withdrawn as real coin | refuse tokens with no code in the pull helper |
| `empty-market-inflation` (real incident) | 1 price manipulation | 1 advanced | a share vault prices deposits off its live asset balance, so a direct transfer (donation) inflates the share price and rounds a later deposit down to almost nothing, which the first depositor then seizes | value the pool by assets deposited through the vault, not the raw balance |

The last two are **real-incident** challenges, rebuilt self-contained with no fork, and both
graded so that only the class fix passes:

- `bridge-phantom-deposit` (Qubit QBridge, Jan 2022): only rejecting codeless tokens is accepted;
  `address(0)`-only instance patches (a `token != address(0)` guard, or un-listing `address(0)`)
  are rejected by a hidden codeless-token test.
- `empty-market-inflation` (Hundred Finance / Sonne): only donation-resistant book-value pricing
  is accepted; partial patches such as `require(shares > 0)` are rejected by a hidden test that
  requires a depositor to recover their principal after a donation.

See [`../docs/realbank/`](../docs/realbank/README.md).

Each PoC passes on the vulnerable version and fails on the patched one, so the
grader scores the **differential**, not an absolute test.

## Template format

```
mothers/<id>/
  mother.json          metadata + identifier→pool map + distractor range + limits + fixId
  src.sol.tmpl         vulnerable contract, with sentinel identifiers and shuffle fences
  hidden.t.sol.tmpl    hidden functional tests (sentinel identifiers)
  poc.t.sol.tmpl       reference PoC exploit (sentinel identifiers)
```

**Sentinel identifiers** are valid Solidity names (`Czz`, `fzzWithdraw`, `vzzBal`,
`lzzAmt`, …) so the template itself compiles. `mother.json`'s `identifiers` maps each
sentinel to a pool in `variantgen/pools.py`; the generator substitutes a seed-chosen
concrete name uniformly across all files.

**Shuffle fences** mark the reorderable region of the contract:

```solidity
// @@SHUF_BEGIN@@
// @@SHUF@@
    function fzzDeposit() external payable { ... }
// @@SHUF@@
    function fzzWithdraw() external { ... }
// @@SHUF_END@@
```

Distractor functions are injected into this region and the whole set is shuffled.

**The reference fix** is not a template file — it is a function registered in
`variantgen/fixes.py` under `mother.json`'s `fixId`, applied to the *rendered* source
so the patch is a minimal, interface-preserving diff on every variant.

After adding a mother, verify it:

```bash
cd variantgen && python -m variantgen verify-mother --mother ../mothers/<id> --count 20
```
