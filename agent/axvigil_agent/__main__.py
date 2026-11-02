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

from .agentic import run_agentic
from .arena import (
    DEFAULT_MOTHERS,
    ensemble_contestant,
    parse_contestant_spec,
    run_arena,
)
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


def _cmd_solve_agentic(args, client, challenge_dir: Path) -> int:
    result = run_agentic(
        client, challenge_dir, protocol=args.tool_protocol, max_steps=args.max_steps,
        token_budget=20_000, forge_bin=_default_forge(), solc=_default_solc(),
        forge_timeout_s=args.timeout,
    )
    graded = None
    if result.patch and result.poc:
        import axvigil_agent.solver as solver_mod
        meta = json.loads((challenge_dir / "challenge.json").read_text())
        graded = solver_mod._grade(
            challenge_dir, meta["targetFile"], result.patch, result.poc,
            args.seed, _default_forge(), _default_solc(), args.timeout,
        )
    passed = bool(graded and graded.passed)
    payload = {
        "solved": passed,
        "stopReason": result.stop_reason,
        "steps": result.steps,
        "evidence": result.evidence(args.tool_protocol),
    }
    if graded is not None:
        payload["checks"] = {
            "pocProvesBug": graded.pocProvesBug,
            "pocFailsAfterPatch": graded.pocFailsAfterPatch,
            "hiddenTestsPass": graded.hiddenTestsPass,
            "patchWithinLimits": graded.patchWithinLimits,
        }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"agentic stop: {result.stop_reason}  steps: {result.steps}  solved: {passed}")
    return 0 if passed else 1


def _meta_factory(model: str) -> MetaModelClient:
    # Temperature 0 keeps arena calls as deterministic as the provider allows.
    # The model HTTP timeout is the client default, 300s.
    return MetaModelClient(model=model, timeout_s=300, temperature=0)


def _cmd_arena(args) -> int:
    try:
        contestants = [parse_contestant_spec(spec) for spec in (args.contestant or [])]
        if args.ensemble:
            models = [part.strip() for part in args.ensemble.split(",") if part.strip()]
            contestants.append(ensemble_contestant(
                models, id=args.ensemble_id, member_strategy=args.ensemble_strategy,
            ))
        mothers = [part.strip() for part in args.mothers.split(",") if part.strip()]
        seeds = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]
    except ValueError as exc:
        print(f"arena: {exc}", file=sys.stderr)
        return 2
    if not contestants:
        print("arena: pass at least one --contestant or --ensemble", file=sys.stderr)
        return 2
    if not mothers or not seeds:
        print("arena: mothers and seeds must be non-empty", file=sys.stderr)
        return 2
    if args.max_iters < 1 or args.concurrency < 1 or args.request_cap < 0:
        print("arena: max-iters and concurrency must be >= 1; request-cap must be >= 0", file=sys.stderr)
        return 2
    if not (os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        print(
            "arena: set META_API_KEY (or MODEL_API_KEY). The key is never written to the results.",
            file=sys.stderr,
        )
        return 2
    try:
        result = run_arena(
            contestants,
            mothers,
            seeds,
            out_path=args.out,
            summary_path=args.summary,
            request_cap=args.request_cap,
            max_iters=args.max_iters,
            concurrency=args.concurrency,
            client_factory=_meta_factory,
            resume=not args.fresh,
            timeout_s=args.timeout,
            forge_bin=_default_forge(),
            solc=_default_solc(),
            on_event=lambda message: print(message, file=sys.stderr),
            tool_protocol=args.tool_protocol,
            max_steps=args.max_steps,
            token_budget=args.token_budget,
        )
    except ValueError as exc:
        print(f"arena: {exc}", file=sys.stderr)
        return 2
    summary = args.summary or str(Path(args.out).with_suffix(".md"))
    passes = sum(1 for run in result["runs"] if run.get("pass"))
    print(f"wrote {args.out}")
    print(f"wrote {summary}")
    print(
        f"completed cells: {passes} passed / {len(result['runs'])} started, "
        f"requests {result['budget']['requestsUsed']}/{result['budget']['requestCap']}"
    )
    for row in result["ranking"]:
        print(
            f"  #{row['rank']} {row['contestantId']}  "
            f"pass {row['passes']}/{row['runs']}  attempts {row['attempts']}  "
            f"tokens {row['tokens']['total']}"
        )
    return 0


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
    s.add_argument("--agentic", action="store_true", help="tool-using loop instead of a single JSON patch")
    s.add_argument("--tool-protocol", default="tools", choices=("tools", "json"), dest="tool_protocol",
                   help="tools = OpenAI tool_calls; json = one JSON action per turn")
    s.add_argument("--max-steps", type=int, default=10, dest="max_steps")

    arena = sub.add_parser(
        "arena",
        help="rank Meta models on the same rendered challenges",
        description=(
            "Run each contestant on the same variantgen challenges, grade with the "
            "AxVigil verifier, and write arena_results.json (schema version 1) plus "
            "a markdown summary. See axvigil_agent.arena for the schema. "
            "The API key is never written to the output."
        ),
    )
    arena.add_argument(
        "--contestant", action="append", default=[],
        help="model, model:strategy, or model:strategy:id. "
             "strategy is baseline, self-critique, plan-then-patch, or agentic",
    )
    arena.add_argument(
        "--ensemble", default=None,
        help="comma-separated model ids. The verifier keeps the first passing member",
    )
    arena.add_argument("--ensemble-id", default=None, help="id for the ensemble contestant")
    arena.add_argument(
        "--ensemble-strategy", default="baseline", dest="ensemble_strategy",
        help="strategy each ensemble member uses (default baseline)",
    )
    arena.add_argument("--mothers", default=",".join(DEFAULT_MOTHERS), help="comma-separated mother ids")
    arena.add_argument("--seeds", default="1", help="comma-separated integer seeds")
    arena.add_argument("--max-iters", type=int, default=3, dest="max_iters")
    arena.add_argument("--request-cap", type=int, default=60, dest="request_cap")
    arena.add_argument("--concurrency", type=int, default=1)
    arena.add_argument("--timeout", type=int, default=120, help="per-grade forge timeout in seconds")
    arena.add_argument("--out", default="arena_results.json")
    arena.add_argument("--summary", default=None, help="markdown path (default: beside --out)")
    arena.add_argument("--fresh", action="store_true", help="ignore completed rows already in --out")
    arena.add_argument("--tool-protocol", default="tools", choices=("tools", "json"), dest="tool_protocol",
                       help="agentic protocol: tools (OpenAI tool_calls) or json (one action per turn)")
    arena.add_argument("--max-steps", type=int, default=10, dest="max_steps",
                       help="agentic model rounds per challenge")
    arena.add_argument("--token-budget", type=int, default=20000, dest="token_budget",
                       help="agentic prompt+completion token budget per challenge")

    args = p.parse_args(argv)
    if args.cmd == "arena":
        return _cmd_arena(args)
    challenge_dir = Path(args.challenge)

    if args.oracle and args.agentic:
        print("solve: --agentic and --oracle cannot be combined", file=sys.stderr)
        return 2
    if args.oracle:
        client = _oracle_client(challenge_dir)
    else:
        try:
            client = MetaModelClient()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    if args.agentic:
        return _cmd_solve_agentic(args, client, challenge_dir)

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
