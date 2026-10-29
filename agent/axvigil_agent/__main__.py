"""AxVigil agent CLI.

    # Solve with the real Meta Model API (needs META_API_KEY):
    python -m axvigil_agent solve --challenge ../challenges/reentrancy-vault --max-iters 4

    # Dry-run the loop offline with the challenge's own reference solution:
    python -m axvigil_agent solve --challenge ../challenges/reentrancy-vault --oracle
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .model import MetaModelClient, ScriptedClient
from .solver import solve


def _default_solc() -> str | None:
    verifier = Path(__file__).resolve().parents[2] / "verifier"
    if str(verifier) not in sys.path:
        sys.path.insert(0, str(verifier))
    from axvigil_verifier.toolchain import discover_solc
    return discover_solc()


def _default_forge() -> str:
    return os.environ.get("FORGE") or (shutil.which("forge") or "forge")


def _oracle_client(challenge_dir: Path) -> ScriptedClient:
    """A scripted client that first submits the untouched (still vulnerable) contract,
    then the reference solution — exercising the fail->feedback->pass path offline.
    Works for any challenge (hand-authored or a rendered variant) via challenge.json."""
    meta = json.loads((challenge_dir / "challenge.json").read_text())
    target = meta["targetFile"]
    poc_files = sorted((challenge_dir / "solution" / "poc").glob("*.t.sol"))
    vuln = (challenge_dir / "src" / target).read_text()
    fix = (challenge_dir / "solution" / "patched" / target).read_text()
    poc = poc_files[0].read_text()
    first = json.dumps({
        "analysis": "First attempt: submitting the contract unchanged, to show the loop reject it.",
        "patched_contract": vuln, "poc_test": poc,
    })
    second = json.dumps({
        "analysis": "Applying the reference fix for this vulnerability class.",
        "patched_contract": fix, "poc_test": poc,
    })
    return ScriptedClient([first, second])


def _outcome_payload(outcome) -> dict:
    return {
        "challengeId": outcome.challenge_id,
        "solved": outcome.solved,
        "solveSeconds": outcome.solve_seconds,
        "iterations": [
            {"index": it.index, "passed": it.passed, "checks": it.checks,
             "analysis": it.analysis, "log": it.log,
             "submissionHash": it.submission_hash}
            for it in outcome.iterations
        ],
        "result": outcome.final_result,
        "finalPatch": outcome.final_patch,
        "finalPoc": outcome.final_poc,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="axvigil_agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve")
    s.add_argument("--challenge", required=True)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--max-iters", type=int, default=4, dest="max_iters")
    s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--oracle", action="store_true", help="offline dry-run with the reference solution")
    s.add_argument("--json", action="store_true", help="print the outcome as JSON")

    args = p.parse_args(argv)
    challenge_dir = Path(args.challenge)

    if args.oracle:
        client = _oracle_client(challenge_dir)
    else:
        try:
            client = MetaModelClient()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    outcome = solve(
        client, challenge_dir, seed=args.seed, max_iters=args.max_iters,
        forge_bin=_default_forge(), solc=_default_solc(), timeout_s=args.timeout,
        on_event=lambda m: print(m, file=sys.stderr),
    )

    if args.json:
        print(json.dumps(_outcome_payload(outcome), indent=2))
    else:
        print(f"\nchallenge: {outcome.challenge_id}")
        print(f"solved:    {outcome.solved} in {len(outcome.iterations)} iteration(s), {outcome.solve_seconds}s")
        for it in outcome.iterations:
            print(f"  iter {it.index}: passed={it.passed} {it.checks}")
        if outcome.solved:
            print(f"  submissionHash: {outcome.final_result['submissionHash']}")

    return 0 if outcome.solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
