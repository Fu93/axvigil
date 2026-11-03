"""Pinned Foundry fuzz schedule for the `invariantsHold` check.

Validators re-grade from the evidence bundle. Foundry's corpus is reproducible
only when the seed, fuzz run count, and invariant depth are the same on every
machine, so those numbers live here and are copied into the bundle. They are
not derived from the variant seed.
"""

from __future__ import annotations

# 0xA11CE. Decimal in the bundle so JSON stays an integer.
FUZZ_SEED = 0xA11CE
FUZZ_RUNS = 2000
INVARIANT_RUNS = 256
INVARIANT_DEPTH = 32


def profile(*, applied: bool) -> dict:
    return {
        "fuzzSeed": FUZZ_SEED,
        "fuzzRuns": FUZZ_RUNS,
        "invariantRuns": INVARIANT_RUNS,
        "invariantDepth": INVARIANT_DEPTH,
        "applied": bool(applied),
    }
