# AxVigil variant generator

The anti-memorization engine. A **mother** (母題) is one vulnerability template; a
**variant** is a concrete, gradeable challenge rendered from a mother + a seed. Two
variants of the same mother teach the *same bug class* but look different enough that
a model which merely memorized the public mother's answer cannot pass — which is the
whole point of the PRD: *we test the general skill of fixing a class of bug, not
recall of one known hack.*

```bash
# Render one concrete, gradeable variant (standard challenge layout):
python -m variantgen render --mother ../mothers/reentrancy --seed 7 --out /tmp/v7

# Render K structurally-unique variants:
python -m variantgen batch --mother ../mothers/reentrancy --count 20 --out /tmp/batch

# Verify a mother: render N unique seeds, grade each reference solution, report.
python -m variantgen verify-mother --mother ../mothers/reentrancy --count 20
```

A rendered variant is an ordinary challenge directory (`src/`, `test/Hidden.t.sol`,
`solution/`, `challenge.json`), so the verifier, backend and agent all operate on it
unchanged.

## What a seed changes

Deterministically, from `random.Random("axvigil::<mother>::<seed>")`:

- **Identifier renaming** — contract name, functions, state variables, locals, drawn from role-specific pools (`pools.py`). Applied consistently across the contract, hidden tests, PoC and reference solution so everything still compiles.
- **Distractor functions** — 1–4 structurally-distinct harmless functions inserted among the real ones (a counter, a pure math fn, an event emitter, …), so the file shape changes, not just names.
- **Function reordering** — the real functions and distractors are shuffled.

The reference fix is applied to the *rendered* source (`fixes.py`), so the patch stays
a minimal, interface-preserving diff regardless of how the variant was shuffled or
renamed.

## Uniqueness (the "discard if too alike" rule)

`fingerprint.py` canonicalizes a variant: strip comments, collapse whitespace, and
replace every non-keyword identifier and numeric literal with a placeholder. So two
variants that differ **only** by renaming hash identically and one is discarded —
real structural variety (which distractors, what order) is what makes a variant
count as new. `batch` and `verify-mother` dedup on this fingerprint.

## Every variant is checked before it ships

`verify-mother` renders each unique seed and runs the full verifier against its
reference solution: `pocProvesBug`, `pocFailsAfterPatch`, `hiddenTestsPass`,
`patchWithinLimits` must all hold, or the variant is reported as failed. This is the
"check the reference solution before a variant ships" guarantee. The four shipped mothers
are `reentrancy`, `price-manipulation`, `access-control`, and `signature-replay`
(see [`../mothers/README.md`](../mothers/README.md)). The first three were recorded at
20/20 unique, solvable variants:

```
reentrancy:         20 rendered, 20 unique fingerprints, 20/20 reference solutions pass
price-manipulation: 20 rendered, 20 unique fingerprints, 20/20 reference solutions pass
access-control:     20 rendered, 20 unique fingerprints, 20/20 reference solutions pass
```

## Writing a mother

See [`../mothers/README.md`](../mothers/README.md) for the template format
(`mother.json`, `src.sol.tmpl`, `hidden.t.sol.tmpl`, `poc.t.sol.tmpl`, and the
reference fix registered in `fixes.py`).
