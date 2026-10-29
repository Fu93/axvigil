"""AxVigil verifier CLI.

    python -m axvigil_verifier grade  --challenge <dir> --submission <dir> [--seed N] [--solve-seconds S]
    python -m axvigil_verifier hash   --challenge-id <id> --seed N --patch <file> --poc <file>
    python -m axvigil_verifier selfcheck --challenge <dir>   # grade the reference solution shipped with a challenge

`grade` prints exactly the SPEC.md result JSON to stdout and exits 0 if passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .grader import grade
from .keccak import submission_hash


def _default_solc() -> str | None:
    return os.environ.get("SOLC") or (shutil.which("solc") or None)


def _default_forge() -> str:
    return os.environ.get("FORGE") or (shutil.which("forge") or "forge")


def _cmd_grade(args) -> int:
    res = grade(
        args.challenge, args.submission,
        seed=args.seed, solve_seconds=args.solve_seconds,
        forge_bin=_default_forge(), solc=_default_solc(), timeout_s=args.timeout,
    )
    print(json.dumps(res.to_json(), indent=2 if args.pretty else None))
    return 0 if res.passed else 1


def _cmd_hash(args) -> int:
    patch = Path(args.patch).read_text()
    poc = Path(args.poc).read_text()
    h = "0x" + submission_hash(args.challenge_id, args.seed, patch, poc).hex()
    print(h)
    return 0


def _cmd_selfcheck(args) -> int:
    """Grade the reference solution a challenge ships for its own CI:
    challenge/solution/patched/<targetFile> + challenge/solution/poc/*.t.sol."""
    sol = Path(args.challenge) / "solution"
    if not sol.is_dir():
        print(f"no reference solution at {sol}", file=sys.stderr)
        return 2
    res = grade(
        args.challenge, sol,
        seed=args.seed, forge_bin=_default_forge(), solc=_default_solc(), timeout_s=args.timeout,
    )
    print(json.dumps(res.to_json(), indent=2))
    return 0 if res.passed else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="verifier", description="AxVigil deterministic grader")
    p.add_argument("--timeout", type=int, default=120, help="per-forge-run wall limit (s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grade", help="grade a submission against a challenge")
    g.add_argument("--challenge", required=True)
    g.add_argument("--submission", required=True)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--solve-seconds", type=int, default=None, dest="solve_seconds")
    g.add_argument("--pretty", action="store_true")
    g.set_defaults(func=_cmd_grade)

    h = sub.add_parser("hash", help="compute a submissionHash")
    h.add_argument("--challenge-id", required=True, dest="challenge_id")
    h.add_argument("--seed", type=int, default=0)
    h.add_argument("--patch", required=True)
    h.add_argument("--poc", required=True)
    h.set_defaults(func=_cmd_hash)

    s = sub.add_parser("selfcheck", help="grade a challenge's own reference solution")
    s.add_argument("--challenge", required=True)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=_cmd_selfcheck)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
