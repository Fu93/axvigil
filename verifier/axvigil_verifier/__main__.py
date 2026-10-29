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
import subprocess
import tempfile
from pathlib import Path
import sys

from .grader import grade
from .keccak import submission_hash


def _apply_patch_to_submission(challenge_dir: Path, patch_path: Path, poc_path: Path) -> Path:
    """Build a dir-based submission from a unified-diff patch + a PoC file.

    Applies the patch to the challenge's targetFile with `git apply` and lays the
    result out as patched/<targetFile> + poc/Poc.t.sol so the normal grader runs.
    """
    meta = json.loads((challenge_dir / "challenge.json").read_text())
    target = meta["targetFile"]
    tmp = Path(tempfile.mkdtemp(prefix="axv-patch-"))
    (tmp / "src").mkdir()
    shutil.copy(challenge_dir / "src" / target, tmp / "src" / target)
    # git apply strips a/ b/ prefixes with -p1; run inside tmp so paths resolve.
    proc = subprocess.run(
        ["git", "apply", "-p1", "--whitespace=nowarn", str(patch_path.resolve())],
        cwd=tmp, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit(f"patch did not apply: {proc.stderr.strip()}")
    sub = tmp / "submission"
    (sub / "patched").mkdir(parents=True)
    (sub / "poc").mkdir(parents=True)
    shutil.copy(tmp / "src" / target, sub / "patched" / target)
    shutil.copy(poc_path, sub / "poc" / "Poc.t.sol")
    return sub


def _default_solc() -> str | None:
    return os.environ.get("SOLC") or (shutil.which("solc") or None)


def _default_forge() -> str:
    return os.environ.get("FORGE") or (shutil.which("forge") or "forge")


def _cmd_grade(args) -> int:
    cleanup = None
    if args.patch:
        if not args.poc:
            print("--patch requires --poc", file=sys.stderr)
            return 2
        submission = _apply_patch_to_submission(Path(args.challenge), Path(args.patch), Path(args.poc))
        cleanup = submission.parent
    elif args.submission:
        submission = args.submission
    else:
        print("provide either --submission <dir> or --patch <file> --poc <file>", file=sys.stderr)
        return 2
    try:
        res = grade(
            args.challenge, submission,
            seed=args.seed, solve_seconds=args.solve_seconds,
            forge_bin=_default_forge(), solc=_default_solc(), timeout_s=args.timeout,
        )
    finally:
        if cleanup is not None:
            shutil.rmtree(cleanup, ignore_errors=True)
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
    g.add_argument("--submission", help="submission dir (patched/ + poc/)")
    g.add_argument("--patch", help="unified-diff patch of the target file (alternative to --submission)")
    g.add_argument("--poc", help="PoC test file (required with --patch)")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--solve-seconds", type=int, default=None, dest="solve_seconds")
    g.add_argument("--pretty", action="store_true")
    g.add_argument("--json", action="store_true", help="accepted for compatibility; output is always JSON")
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
