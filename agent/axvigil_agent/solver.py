"""The AxVigil solve loop: propose -> grade -> feed back -> retry."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .model import ModelClient
from .prompts import SYSTEM, build_retry_prompt, build_user_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
VULN_CLASS_NAMES = {0: "reentrancy", 1: "price manipulation", 2: "access control"}


def _ensure_verifier_on_path() -> None:
    p = str(REPO_ROOT / "verifier")
    if p not in sys.path:
        sys.path.insert(0, p)


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response (handles ``` fences and prose)."""
    text = text.strip()
    # fenced ```json ... ``` or ``` ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if fence:
        candidates.append(fence.group(1))
    candidates.append(text)
    # first '{' to last '}'
    i, j = text.find("{"), text.rfind("}")
    if i != -1 and j != -1 and j > i:
        candidates.append(text[i : j + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON object found in model response")


@dataclass
class Iteration:
    index: int
    analysis: str
    passed: bool
    checks: dict
    log: str
    submission_hash: str


@dataclass
class SolveOutcome:
    challenge_id: str
    solved: bool
    iterations: list[Iteration] = field(default_factory=list)
    solve_seconds: int | None = None
    final_patch: str | None = None
    final_poc: str | None = None
    final_result: dict | None = None


def _grade(challenge_dir: Path, target_file: str, patch: str, poc: str, seed: int,
           forge_bin: str, solc: str | None, timeout_s: int):
    _ensure_verifier_on_path()
    from verifier.grader import grade

    tmp = Path(tempfile.mkdtemp(prefix="axv-agent-"))
    try:
        (tmp / "patched").mkdir()
        (tmp / "poc").mkdir()
        (tmp / "patched" / target_file).write_text(patch)
        (tmp / "poc" / "Poc.t.sol").write_text(poc)
        return grade(challenge_dir, tmp, seed=seed, forge_bin=forge_bin, solc=solc, timeout_s=timeout_s)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def solve(
    client: ModelClient,
    challenge_dir: str | Path,
    *,
    seed: int = 0,
    max_iters: int = 4,
    forge_bin: str = "forge",
    solc: str | None = None,
    timeout_s: int = 120,
    on_event=None,
) -> SolveOutcome:
    challenge_dir = Path(challenge_dir)
    meta = json.loads((challenge_dir / "challenge.json").read_text())
    target_file = meta["targetFile"]
    source = (challenge_dir / "src" / target_file).read_text()

    def emit(msg: str) -> None:
        if on_event:
            on_event(msg)

    user = build_user_prompt(
        challenge_id=meta["challengeId"], target_file=target_file,
        contract_name=meta["contractName"],
        vuln_class_name=VULN_CLASS_NAMES.get(int(meta["vulnClass"]), "unknown"),
        pragma=meta.get("pragma", "0.8.28"), source=source,
        required_functions=meta.get("requiredFunctions", []),
    )

    outcome = SolveOutcome(challenge_id=meta["challengeId"], solved=False)
    start = time.time()
    prev_patch = prev_poc = ""

    for i in range(max_iters):
        emit(f"[iter {i}] asking model…")
        raw = client.complete(SYSTEM, user)
        try:
            obj = extract_json(raw)
            patch = obj["patched_contract"]
            poc = obj["poc_test"]
            analysis = obj.get("analysis", "")
        except (ValueError, KeyError) as e:
            emit(f"[iter {i}] unparseable response ({e}); retrying")
            user = f"Your last response could not be parsed as the required JSON ({e}). " \
                   f"Return ONLY the JSON object with keys analysis, patched_contract, poc_test."
            continue

        emit(f"[iter {i}] grading…")
        res = _grade(challenge_dir, target_file, patch, poc, seed, forge_bin, solc, timeout_s)
        checks = {
            "pocProvesBug": res.pocProvesBug,
            "pocFailsAfterPatch": res.pocFailsAfterPatch,
            "hiddenTestsPass": res.hiddenTestsPass,
            "patchWithinLimits": res.patchWithinLimits,
        }
        outcome.iterations.append(
            Iteration(i, analysis, res.passed, checks, res.log, res.submissionHash)
        )
        emit(f"[iter {i}] passed={res.passed} checks={checks}")

        prev_patch, prev_poc = patch, poc
        if res.passed:
            outcome.solved = True
            outcome.final_patch = patch
            outcome.final_poc = poc
            outcome.final_result = res.to_json()
            break

        user = build_retry_prompt(prev_patch=patch, prev_poc=poc, result_log=res.log, checks=checks)

    outcome.solve_seconds = int(time.time() - start)
    if outcome.final_result:
        outcome.final_result["solveSeconds"] = outcome.solve_seconds
    return outcome
