#!/usr/bin/env python3
"""Time one full reference grade per mother (all five checks).

    PATH="$HOME/.foundry/bin:$PATH" python3 scripts/bench_invariants.py
    python3 scripts/bench_invariants.py --count 20

`--count 20` is the ship check: 20 structurally unique variants, each reference
solution must pass, including invariantsHold. Prints per-mother wall time.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "variantgen"))
sys.path.insert(0, str(ROOT / "verifier"))

from variantgen.__main__ import _unique_variants  # noqa: E402
from variantgen.render import Mother, render_challenge  # noqa: E402
from axvigil_verifier.grader import grade  # noqa: E402
from axvigil_verifier.toolchain import discover_solc, forge_executable  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Time AxVigil reference grades")
    p.add_argument("--count", type=int, default=1, help="unique variants to grade per mother")
    p.add_argument("--timeout", type=int, default=180)
    args = p.parse_args()
    forge = forge_executable() or "forge"
    solc = discover_solc()
    mothers = sorted(d for d in (ROOT / "mothers").iterdir() if (d / "mother.json").is_file())
    failed = 0
    print(f"forge={forge} solc={solc or 'svm'} count={args.count}")
    for mdir in mothers:
        mother = Mother(mdir)
        tmp = Path(tempfile.mkdtemp(prefix=f"axv-bench-{mother.mother_id}-"))
        passed = 0
        worst = 0.0
        total = 0.0
        try:
            t0 = time.perf_counter()
            for seed, _fp in _unique_variants(mother, args.count):
                vdir = tmp / str(seed)
                render_challenge(mother, seed, vdir)
                one = time.perf_counter()
                res = grade(vdir, vdir / "solution", seed=seed, forge_bin=forge, solc=solc, timeout_s=args.timeout)
                dt = time.perf_counter() - one
                total += dt
                worst = max(worst, dt)
                if res.passed:
                    passed += 1
                else:
                    failed += 1
                    print(f"  FAIL {mother.mother_id} seed {seed}: {res.log}")
            wall = time.perf_counter() - t0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        mean = total / args.count if args.count else 0
        print(
            f"{mother.mother_id}: {passed}/{args.count} pass  "
            f"mean {mean:.2f}s  worst {worst:.2f}s  wall {wall:.1f}s"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    os.environ.setdefault("FOUNDRY_OFFLINE", "true")
    raise SystemExit(main())
