"""Variant generator CLI.

    # Render one concrete, gradeable variant:
    python -m variantgen render --mother ../mothers/reentrancy --seed 7 --out /tmp/v7

    # Render K UNIQUE variants (structural fingerprint dedup) into a dir:
    python -m variantgen batch --mother ../mothers/reentrancy --count 20 --out /tmp/batch

    # Verify a mother: render N seeds, grade each reference solution, report unique count.
    python -m variantgen verify-mother --mother ../mothers/reentrancy --count 20
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from .fingerprint import fingerprint
from .render import Mother, render_challenge, render_src, build_context

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_verifier_on_path() -> None:
    p = str(REPO_ROOT / "verifier")
    if p not in sys.path:
        sys.path.insert(0, p)


def _default_solc():
    _ensure_verifier_on_path()
    from axvigil_verifier.toolchain import discover_solc
    return discover_solc()


def _default_forge():
    return os.environ.get("FORGE") or (shutil.which("forge") or "forge")


def _cmd_render(args) -> int:
    mother = Mother(Path(args.mother))
    ch = render_challenge(mother, args.seed, Path(args.out))
    print(f"rendered {ch['challengeId']} -> {args.out}  (contract {ch['contractName']})")
    return 0


def _unique_variants(mother: Mother, count: int, start_seed: int = 0, max_seeds: int | None = None):
    """Yield (seed, fingerprint) for up to `count` structurally-unique variants."""
    seen: set[str] = set()
    seed = start_seed
    limit = max_seeds if max_seeds is not None else count * 50
    produced = 0
    while produced < count and seed < start_seed + limit:
        ctx = build_context(mother, seed)
        fp = fingerprint(render_src(mother, ctx))
        if fp not in seen:
            seen.add(fp)
            produced += 1
            yield seed, fp
        seed += 1


def _cmd_batch(args) -> int:
    mother = Mother(Path(args.mother))
    out = Path(args.out)
    n = 0
    for seed, fp in _unique_variants(mother, args.count):
        ch = render_challenge(mother, seed, out / f"{mother.mother_id}-{seed}")
        print(f"  seed {seed:4d}  fp {fp}  {ch['contractName']}")
        n += 1
    print(f"wrote {n} unique variants to {out}")
    return 0 if n == args.count else 1


def _cmd_verify_mother(args) -> int:
    _ensure_verifier_on_path()
    from axvigil_verifier.grader import grade

    mother = Mother(Path(args.mother))
    forge, solc = _default_forge(), _default_solc()
    tmp = Path(args.workdir) if args.workdir else Path("/tmp") / f"axv-vm-{mother.mother_id}"
    shutil.rmtree(tmp, ignore_errors=True)

    fps: set[str] = set()
    passed = 0
    failed_seeds = []
    rendered = 0
    for seed, fp in _unique_variants(mother, args.count):
        fps.add(fp)
        vdir = tmp / f"{mother.mother_id}-{seed}"
        render_challenge(mother, seed, vdir)
        rendered += 1
        res = grade(vdir, vdir / "solution", seed=seed, forge_bin=forge, solc=solc, timeout_s=args.timeout)
        status = "PASS" if res.passed else "FAIL"
        print(f"  seed {seed:4d}  fp {fp}  reference {status}")
        if res.passed:
            passed += 1
        else:
            failed_seeds.append((seed, res.log))
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{mother.mother_id}: {rendered} rendered, {len(fps)} unique fingerprints, "
          f"{passed}/{rendered} reference solutions pass")
    for seed, log in failed_seeds:
        print(f"  FAILED seed {seed}: {log}")
    ok = (passed == rendered == args.count) and (len(fps) == args.count)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="variantgen")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render")
    r.add_argument("--mother", required=True)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", required=True)
    r.set_defaults(func=_cmd_render)

    b = sub.add_parser("batch")
    b.add_argument("--mother", required=True)
    b.add_argument("--count", type=int, default=20)
    b.add_argument("--out", required=True)
    b.set_defaults(func=_cmd_batch)

    v = sub.add_parser("verify-mother")
    v.add_argument("--mother", required=True)
    v.add_argument("--count", type=int, default=20)
    v.add_argument("--timeout", type=int, default=120)
    v.add_argument("--workdir", default=None)
    v.set_defaults(func=_cmd_verify_mother)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
