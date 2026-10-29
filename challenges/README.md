# Challenges

Concrete, gradeable challenge directories (`src/`, `test/Hidden.t.sol`, optional
`solution/`). Two live here, each with a distinct role; the reentrancy bug also exists
as a template in [`../mothers/reentrancy`](../mothers/reentrancy), which is its canonical,
seed-rendered source. These are intentionally separate, not duplicates:

- `reentrancy-001/` — the **deployed live-demo** instance (patch-based submission under
  `submissions/`); graded by `axvigil_verifier grade --patch` and used by the BSC testnet
  demo and `scripts/*.sh`.
- `reentrancy-vault/` — a **fixed-name test fixture** with a reference `solution/`, used by
  the verifier's self-check and adversarial tests (`verifier/tests/test_grader.py`).

For real play, the platform never serves these static files — it renders a fresh variant
from a mother per session (see [`../variantgen`](../variantgen)).
