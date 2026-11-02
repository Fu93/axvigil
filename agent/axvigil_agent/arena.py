"""Multi-model arena.

Each contestant faces the same rendered mother/seed challenges. Submissions are
graded by the AxVigil verifier (the same ``solve`` loop as the single-agent
demo). Results land in ``arena_results.json`` (schema version 1) plus a
markdown summary.

Schema
------
Top level
  schemaVersion            1
  schema                   field list and the ranking rule (also below)
  generatedAt              UTC timestamp of this write
  note                     short description; real runs are not placeholders
  placeholder              omitted, or true only for the page's sample data
  config                   contestants, mothers, seeds, maxIters, requestCap, concurrency
  budget.requestCap        cap for this process
  budget.requestsUsed      model HTTP calls this process actually made
  ranking                  pass rate, then fewer attempts, then fewer tokens
  runs                     one object per started cell

Run object
  runId                    ``{contestantId}|{mother}|{seed}``
  contestantId             stable id (model, model:strategy, or an ensemble id)
  model                    model id, or null for an ensemble
  strategy                 baseline | self-critique | plan-then-patch | ensemble
  models                   member model ids (ensemble) or the single model
  mother, seed             challenge cell
  challengeId              id written into the rendered challenge
  status                   completed | budget | error
                           ``budget`` and ``error`` are retried on the next launch;
                           ``completed`` is skipped (resume)
  pass                     verifier passed
  attempts                 graded submissions (unparseable replies are not attempts)
  requests                 model completions purchased from the shared cap
  tokens.prompt            prompt tokens summed across those completions
  tokens.completion        completion tokens summed the same way
  latencyMs                wall time for the cell, including grading
  failedChecks             checks the last graded attempt failed.
                           Empty when ``pass`` is true. Order is the verifier's
                           four checks: pocProvesBug, pocFailsAfterPatch,
                           hiddenTestsPass, patchWithinLimits
  patchDiffLines           added plus deleted lines versus the original target.
                           Same count the verifier uses for the line budget
  ensembleWinner           member whose patch passed, or null
  error                    scrubbed message when status is error, else null

Ranking uses ``completed`` runs only. Pass rate is passes/runs (0 when a
contestant has no completed run). Ties break by fewer total attempts, then
fewer total tokens (prompt + completion), then contestant id. ``byMother``
breaks the same contestant down per mother; a mother that was only cut off by
the cap shows passes 0.

The API key is never written. ``META_API_KEY`` / ``MODEL_API_KEY`` values are
stripped from results, the summary, and progress lines.

Strategies
----------
  baseline          one completion per graded attempt (the normal solve loop)
  self-critique     the model reviews its own draft and the reviewed JSON is
                    what the verifier sees
  plan-then-patch   a plan completion, then a patch completion that must follow it
  agentic           tool-using loop (read, list, public forge, patch, submit).
                    The transcript is stored on the run as ``evidence``.
  ensemble          each member model runs the member strategy in order; the
                    verifier keeps the first passing patch and later members
                    are not called

Resume
------
A cell with status ``completed`` in the output file is not run again and does
not spend the cap. ``--fresh`` ignores the file. The cap applies to this
process only. With ``--concurrency 1`` the schedule is deterministic: contestant
order, then mother order, then seed order, and the cap stops at an attempt
boundary. Higher concurrency still cannot exceed the cap; the set of attempts
that receive the last few requests can interleave.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model import ClientStop
from .agentic import run_agentic
from .solver import solve

SCHEMA_VERSION = 1
CHECK_NAMES = (
    "pocProvesBug",
    "pocFailsAfterPatch",
    "hiddenTestsPass",
    "patchWithinLimits",
)
STRATEGIES = ("baseline", "self-critique", "plan-then-patch", "agentic")
DEFAULT_MOTHERS = (
    "reentrancy",
    "price-manipulation",
    "access-control",
    "signature-replay",
    "bridge-phantom-deposit",
    "empty-market-inflation",
)
RUN_FIELDS = (
    "runId",
    "contestantId",
    "model",
    "strategy",
    "models",
    "mother",
    "seed",
    "challengeId",
    "status",
    "pass",
    "attempts",
    "requests",
    "tokens",
    "latencyMs",
    "failedChecks",
    "attemptChecks",
    "patchDiffLines",
    "ensembleWinner",
    "error",
    "evidence",
)
SCHEMA = {
    "version": SCHEMA_VERSION,
    "description": (
        "Arena ledger. ranking is pass rate on completed runs, then fewer "
        "total attempts, then fewer total tokens (prompt + completion). "
        "Each run's attemptChecks lists pocProvesBug, pocFailsAfterPatch, "
        "hiddenTestsPass, and patchWithinLimits for every graded attempt. "
        "Agentic runs add evidence.transcript and evidence.autoSubmitted."
    ),
    "run": list(RUN_FIELDS),
    "tokens": ["prompt", "completion"],
    "status": ["completed", "budget", "error"],
    "ranking": "pass rate (completed runs), then fewer total attempts, then fewer total tokens",
}
_SECRET_ENVS = ("META_API_KEY", "MODEL_API_KEY")

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeModelClient:
    """Deterministic offline model. No network.

    ``handler`` is a list of response strings (the last one repeats) or a
    callable ``(system, user, call_index) -> str``. ``usage`` is the
    ``(prompt, completion)`` token pair reported for every call.
    """

    def __init__(self, handler, usage: tuple[int, int] = (11, 7)):
        self.handler = handler
        self.usage = (int(usage[0]), int(usage[1]))
        self.calls = 0
        self.prompts: list[tuple[str, str]] = []
        self.last_usage = {"prompt": self.usage[0], "completion": self.usage[1]}

    def complete(self, system: str, user: str) -> str:
        idx = self.calls
        self.calls += 1
        self.prompts.append((system, user))
        self.last_usage = {"prompt": self.usage[0], "completion": self.usage[1]}
        if callable(self.handler):
            return self.handler(system, user, idx)
        if not self.handler:
            return ""
        return self.handler[min(idx, len(self.handler) - 1)]


@dataclass(frozen=True)
class Contestant:
    id: str
    strategy: str
    model: str | None = None
    models: tuple[str, ...] = ()
    member_strategy: str = "baseline"

    def public(self) -> dict:
        models = list(self.models) if self.models else ([self.model] if self.model else [])
        return {
            "id": self.id,
            "strategy": self.strategy,
            "model": self.model,
            "models": models,
            "memberStrategy": self.member_strategy,
        }


def parse_contestant_spec(spec: str) -> Contestant:
    """``model``, ``model:strategy``, or ``model:strategy:id``."""
    parts = spec.split(":")
    if not parts or not parts[0].strip():
        raise ValueError(f"empty contestant spec: {spec!r}")
    model = parts[0].strip()
    if len(parts) == 1:
        return Contestant(id=model, strategy="baseline", model=model)
    if len(parts) == 2:
        strategy = parts[1].strip()
        _check_strategy(strategy)
        cid = model if strategy == "baseline" else f"{model}:{strategy}"
        return Contestant(id=cid, strategy=strategy, model=model)
    if len(parts) == 3:
        strategy = parts[1].strip()
        cid = parts[2].strip()
        _check_strategy(strategy)
        if not cid:
            raise ValueError(f"contestant spec {spec!r} is missing an id")
        return Contestant(id=cid, strategy=strategy, model=model)
    raise ValueError(
        f"contestant spec {spec!r} should be model, model:strategy, or model:strategy:id"
    )


def ensemble_contestant(
    models: list[str],
    id: str | None = None,
    member_strategy: str = "baseline",
) -> Contestant:
    ids = tuple(m.strip() for m in models if m and m.strip())
    if not ids:
        raise ValueError("ensemble needs at least one model")
    _check_strategy(member_strategy)
    cid = id or ("ensemble:" + "+".join(ids))
    return Contestant(
        id=cid, strategy="ensemble", model=None, models=ids, member_strategy=member_strategy,
    )


def _check_strategy(strategy: str) -> None:
    if strategy not in STRATEGIES:
        known = ", ".join(STRATEGIES)
        raise ValueError(f"unknown strategy {strategy!r} (expected {known})")


def render_mother(mother_id: str, seed: int, out_dir: str | Path) -> Path:
    """Render one variantgen challenge. Offline; no forge."""
    out_dir = Path(out_dir)
    variantgen = str(REPO_ROOT / "variantgen")
    import sys
    if variantgen not in sys.path:
        sys.path.insert(0, variantgen)
    from variantgen.render import Mother, render_challenge

    mother = Mother(REPO_ROOT / "mothers" / mother_id)
    render_challenge(mother, int(seed), out_dir)
    return out_dir


def changed_lines(before: str, after: str) -> int:
    """Added plus deleted lines. Matches the verifier's patch line count."""
    import difflib
    a_lines = before.replace("\r\n", "\n").split("\n")
    b_lines = after.replace("\r\n", "\n").split("\n")
    count = 0
    for line in difflib.unified_diff(a_lines, b_lines, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def rank_contestants(runs: list[dict]) -> list[dict]:
    """Pass rate, then fewer total attempts, then fewer total tokens."""
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for run in runs:
        cid = run["contestantId"]
        if cid not in grouped:
            grouped[cid] = []
            order.append(cid)
        grouped[cid].append(run)

    rows = []
    for cid in order:
        items = grouped[cid]
        completed = [r for r in items if r.get("status", "completed") == "completed"]
        passes = sum(1 for r in completed if r.get("pass"))
        attempts = sum(int(r.get("attempts") or 0) for r in completed)
        prompt = sum(int((r.get("tokens") or {}).get("prompt") or 0) for r in completed)
        completion = sum(int((r.get("tokens") or {}).get("completion") or 0) for r in completed)
        scored = len(completed)
        by_mother: dict[str, dict] = {}
        for run in items:
            slot = by_mother.setdefault(run["mother"], {
                "passes": 0,
                "runs": 0,
                "attempts": 0,
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "passRate": 0.0,
            })
            if run.get("status", "completed") != "completed":
                continue
            slot["runs"] += 1
            slot["passes"] += 1 if run.get("pass") else 0
            slot["attempts"] += int(run.get("attempts") or 0)
            tp = int((run.get("tokens") or {}).get("prompt") or 0)
            tc = int((run.get("tokens") or {}).get("completion") or 0)
            slot["tokens"]["prompt"] += tp
            slot["tokens"]["completion"] += tc
            slot["tokens"]["total"] += tp + tc
        for slot in by_mother.values():
            slot["passRate"] = (slot["passes"] / slot["runs"]) if slot["runs"] else 0.0
        sample = completed[0] if completed else items[0]
        rows.append({
            "contestantId": cid,
            "strategy": sample.get("strategy"),
            "model": sample.get("model"),
            "passes": passes,
            "runs": scored,
            "passRate": (passes / scored) if scored else 0.0,
            "attempts": attempts,
            "tokens": {"prompt": prompt, "completion": completion, "total": prompt + completion},
            "byMother": by_mother,
        })
    rows.sort(key=lambda row: (
        -row["passRate"],
        row["attempts"],
        row["tokens"]["total"],
        row["contestantId"],
    ))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def render_summary(doc: dict) -> str:
    lines = [
        "# AxVigil arena",
        "",
        "Powered by Meta Muse Spark.",
        "",
        "Same rendered challenges for every contestant. The AxVigil verifier grades",
        "each patch and proof of concept. Ranked by pass rate, then fewer attempts,",
        "then fewer tokens. Only completed runs count.",
        "",
        f"Requests this process: {doc['budget']['requestsUsed']} / {doc['budget']['requestCap']}.",
        "",
        "## Ranking",
        "",
        "| Rank | Contestant | Strategy | Pass rate | Passes | Runs | Attempts | Prompt tokens | Completion tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in doc.get("ranking") or []:
        rate = f"{row['passRate'] * 100:.0f}%"
        tokens = row["tokens"]
        lines.append(
            f"| {row['rank']} | {row['contestantId']} | {row.get('strategy') or ''} | {rate} | "
            f"{row['passes']} | {row['runs']} | {row['attempts']} | {tokens['prompt']} | {tokens['completion']} |"
        )
    mothers: list[str] = []
    for row in doc.get("ranking") or []:
        for mother in row.get("byMother") or {}:
            if mother not in mothers:
                mothers.append(mother)
    if mothers:
        lines.extend(["", "## Per mother", ""])
        header = "| Contestant | " + " | ".join(mothers) + " |"
        sep = "|---|" + "|".join("---" for _ in mothers) + "|"
        lines.extend([header, sep])
        for row in doc.get("ranking") or []:
            cells = []
            for mother in mothers:
                slot = (row.get("byMother") or {}).get(mother)
                cells.append("—" if not slot else f"{slot['passes']}/{slot['runs']}")
            lines.append(f"| {row['contestantId']} | " + " | ".join(cells) + " |")
    lines.extend(["", "## Runs", ""])
    lines.append("| Contestant | Mother | Seed | Status | Pass | Attempts | Requests | Tokens | Latency ms | Checks | Diff lines |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for run in doc.get("runs") or []:
        tokens = run.get("tokens") or {}
        total = int(tokens.get("prompt") or 0) + int(tokens.get("completion") or 0)
        lines.append(
            f"| {run.get('contestantId')} | {run.get('mother')} | {run.get('seed')} | {run.get('status')} | "
            f"{run.get('pass')} | {run.get('attempts')} | {run.get('requests')} | {total} | "
            f"{run.get('latencyMs')} | {_format_attempt_checks(run)} | {run.get('patchDiffLines')} |"
        )
    lines.append("")
    return "\n".join(lines)


@dataclass
class _Sink:
    prompt: int = 0
    completion: int = 0
    calls: int = 0


class _Budget:
    def __init__(self, cap: int):
        if cap < 0:
            raise ValueError("request_cap must be >= 0")
        self.cap = cap
        self.used = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            if self.used >= self.cap:
                return False
            self.used += 1
            return True

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return self.used >= self.cap

    def snapshot(self) -> int:
        with self._lock:
            return self.used


class _Meter:
    """Counts one request per inner completion and stops at the shared cap."""

    def __init__(self, inner, budget: _Budget, sink: _Sink):
        self.inner = inner
        self.budget = budget
        self.sink = sink
        self.last_usage = {"prompt": 0, "completion": 0}

    def complete(self, system: str, user: str) -> str:
        if not self.budget.try_acquire():
            raise ClientStop("request_cap")
        try:
            text = self.inner.complete(system, user)
        except Exception:
            self.sink.calls += 1
            raise
        prompt, completion = _read_usage(self.inner)
        self.sink.prompt += prompt
        self.sink.completion += completion
        self.sink.calls += 1
        self.last_usage = {"prompt": prompt, "completion": completion}
        return text

    def complete_turn(self, messages, *, tools=None):
        if not self.budget.try_acquire():
            raise ClientStop("request_cap")
        try:
            turn = self.inner.complete_turn(messages, tools=tools)
        except ClientStop:
            raise
        except Exception:
            self.sink.calls += 1
            raise
        prompt, completion = _read_usage(self.inner)
        self.sink.prompt += prompt
        self.sink.completion += completion
        self.sink.calls += 1
        self.last_usage = {"prompt": prompt, "completion": completion}
        return turn


class _Strategy:
    def __init__(self, inner, strategy: str):
        self.inner = inner
        self.strategy = strategy

    def complete(self, system: str, user: str) -> str:
        if self.strategy == "baseline":
            return self.inner.complete(system, user)
        if self.strategy == "self-critique":
            draft = self.inner.complete(system, user)
            review = (
                "Review this candidate submission before it is graded. "
                "Return ONLY a JSON object with keys analysis, patched_contract, poc_test. "
                "Correct the patch or the proof of concept if the exploit would still succeed "
                "or the patch would break legitimate behaviour. "
                "If it is already right, return it unchanged.\n\n"
                f"Candidate:\n{draft}\n\nTask:\n{user}"
            )
            return self.inner.complete(
                "You are reviewing your own smart-contract patch before the verifier grades it. "
                "Return only the JSON object.",
                review,
            )
        if self.strategy == "plan-then-patch":
            plan = self.inner.complete(
                "You are planning a minimal smart-contract fix. Reply with a short plan only.",
                "Plan only. Describe the minimal fix and the proof of concept. "
                "Do not return the final JSON yet.\n\n" + user,
            )
            return self.inner.complete(
                system,
                "Follow this plan, then return the JSON object with keys "
                "analysis, patched_contract, poc_test.\n\n"
                f"Plan:\n{plan}\n\n{user}",
            )
        raise ValueError(f"unknown strategy {self.strategy!r}")


def _read_usage(client) -> tuple[int, int]:
    usage = getattr(client, "last_usage", None)
    if not isinstance(usage, dict):
        return (0, 0)

    def num(*keys: str) -> int:
        for key in keys:
            if key in usage and usage[key] is not None:
                try:
                    return int(usage[key])
                except (TypeError, ValueError):
                    return 0
        return 0

    return (num("prompt", "prompt_tokens"), num("completion", "completion_tokens"))


def _failed_checks(checks: dict) -> list[str]:
    return [name for name in CHECK_NAMES if not checks.get(name, False)]


def collect_secrets(extra: list[str] | None = None) -> list[str]:
    found: list[str] = []
    for name in _SECRET_ENVS:
        value = os.environ.get(name) or ""
        if len(value) >= 6:
            found.append(value)
    for value in extra or []:
        if value and len(value) >= 6 and value not in found:
            found.append(value)
    found.sort(key=len, reverse=True)
    return found


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


@dataclass
class _Task:
    contestant: Contestant
    mother: str
    seed: int

    @property
    def run_id(self) -> str:
        return f"{self.contestant.id}|{self.mother}|{self.seed}"


def run_arena(
    contestants: list[Contestant],
    mothers: list[str],
    seeds: list[int],
    *,
    out_path: str | Path,
    request_cap: int = 60,
    max_iters: int = 3,
    concurrency: int = 1,
    client_factory,
    grader=None,
    summary_path: str | Path | None = None,
    resume: bool = True,
    timeout_s: int = 120,
    forge_bin: str = "forge",
    solc: str | None = None,
    on_event=None,
    secrets: list[str] | None = None,
    render_fn=None,
    tool_protocol: str = "tools",
    max_steps: int = 10,
    max_output_bytes: int = 4096,
    agent_wall_clock_s: float = 180,
    token_budget: int = 40000,
    forge_runner=None,
) -> dict:
    """Run the matrix. ``client_factory(model_id)`` must return a fresh client.

    ``grader``, when set, replaces the real verifier (tests). ``render_fn``,
    when set, replaces variantgen. The real path uses both.
    """
    if not contestants:
        raise ValueError("arena needs at least one contestant")
    if not mothers or not seeds:
        raise ValueError("arena needs at least one mother and one seed")
    if max_iters < 1:
        raise ValueError("max_iters must be >= 1")
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    out_path = Path(out_path)
    summary_path = Path(summary_path) if summary_path else out_path.with_suffix(".md")
    render = render_fn or render_mother
    secret_values = collect_secrets(secrets)
    budget = _Budget(request_cap)
    tasks = [
        _Task(contestant, mother, int(seed))
        for contestant in contestants
        for mother in mothers
        for seed in seeds
    ]
    kept = _load_completed(out_path) if resume else {}
    pending = [task for task in tasks if task.run_id not in kept]
    fresh: dict[str, dict] = {}
    lock = threading.Lock()

    def emit(message: str) -> None:
        if on_event:
            on_event(redact(message, secret_values))

    def persist() -> None:
        doc = _document(
            contestants, mothers, seeds, max_iters, request_cap, concurrency,
            tasks, kept, fresh, budget.snapshot(),
        )
        _write_outputs(doc, out_path, summary_path, secret_values)

    def store(record: dict) -> None:
        with lock:
            fresh[record["runId"]] = record
            persist()

    def worker(task: _Task) -> dict:
        return _run_cell(
            task,
            render=render,
            grader=grader,
            budget=budget,
            max_iters=max_iters,
            client_factory=client_factory,
            forge_bin=forge_bin,
            solc=solc,
            timeout_s=timeout_s,
            emit=emit,
            secrets=secret_values,
            tool_protocol=tool_protocol,
            max_steps=max_steps,
            max_output_bytes=max_output_bytes,
            agent_wall_clock_s=agent_wall_clock_s,
            token_budget=token_budget,
            forge_runner=forge_runner,
        )

    if concurrency <= 1:
        for task in pending:
            if budget.exhausted:
                emit(f"[arena] request cap reached; not starting {task.run_id}")
                break
            store(worker(task))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(worker, task) for task in pending]
            for future in futures:
                store(future.result())

    if not fresh and kept:
        persist()
    doc = _document(
        contestants, mothers, seeds, max_iters, request_cap, concurrency,
        tasks, kept, fresh, budget.snapshot(),
    )
    _write_outputs(doc, out_path, summary_path, secret_values)
    return doc


def _load_completed(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    kept = {}
    for run in data.get("runs") or []:
        if isinstance(run, dict) and run.get("status") == "completed" and run.get("runId"):
            kept[run["runId"]] = run
    return kept


def _document(
    contestants, mothers, seeds, max_iters, request_cap, concurrency,
    tasks, kept, fresh, requests_used,
) -> dict:
    runs = []
    for task in tasks:
        if task.run_id in fresh:
            runs.append(fresh[task.run_id])
        elif task.run_id in kept:
            runs.append(kept[task.run_id])
    doc = {
        "schemaVersion": SCHEMA_VERSION,
        "schema": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Graded by the AxVigil verifier. Powered by Meta Muse Spark.",
        "config": {
            "contestants": [c.public() for c in contestants],
            "mothers": list(mothers),
            "seeds": [int(s) for s in seeds],
            "maxIters": max_iters,
            "requestCap": request_cap,
            "concurrency": concurrency,
        },
        "budget": {"requestCap": request_cap, "requestsUsed": requests_used},
        "runs": runs,
    }
    doc["ranking"] = rank_contestants(runs)
    return doc


def _write_outputs(doc: dict, out_path: Path, summary_path: Path, secrets: list[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = redact(json.dumps(doc, indent=2) + "\n", secrets)
    summary = redact(render_summary(doc), secrets)
    _atomic_write(out_path, payload)
    _atomic_write(summary_path, summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8")
    try:
        handle.write(text)
        handle.close()
        os.replace(handle.name, path)
    except Exception:
        handle.close()
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _run_cell(
    task: _Task,
    *,
    render,
    grader,
    budget: _Budget,
    max_iters: int,
    client_factory,
    forge_bin: str,
    solc: str | None,
    timeout_s: int,
    emit,
    secrets: list[str],
    tool_protocol: str = "tools",
    max_steps: int = 10,
    max_output_bytes: int = 4096,
    agent_wall_clock_s: float = 180,
    token_budget: int = 40000,
    forge_runner=None,
) -> dict:
    started = time.perf_counter()
    sink = _Sink()
    try:
        with tempfile.TemporaryDirectory(prefix="axv-arena-") as tmp:
            render(task.mother, task.seed, Path(tmp))
            challenge_dir = Path(tmp)
            meta = json.loads((challenge_dir / "challenge.json").read_text())
            target = meta["targetFile"]
            original = (challenge_dir / "src" / target).read_text()
            solved, winner, cut_short, last_patch, attempts, failed, challenge_id, evidence, attempt_checks = _solve_contestant(
                task.contestant,
                challenge_dir,
                seed=task.seed,
                sink=sink,
                budget=budget,
                max_iters=max_iters,
                client_factory=client_factory,
                grader=grader,
                forge_bin=forge_bin,
                solc=solc,
                timeout_s=timeout_s,
                emit=emit,
                tool_protocol=tool_protocol,
                max_steps=max_steps,
                max_output_bytes=max_output_bytes,
                agent_wall_clock_s=agent_wall_clock_s,
                token_budget=token_budget,
                forge_runner=forge_runner,
            )
        diff = changed_lines(original, last_patch) if isinstance(last_patch, str) else 0
        status = "completed" if solved or not cut_short else "budget"
        record = _record(
            task, challenge_id=challenge_id or f"{task.mother}-{task.seed}",
            status=status, passed=solved, attempts=attempts, sink=sink,
            latency_ms=_latency(started), failed=failed if not solved else [],
            diff=diff, winner=winner, error=None, evidence=evidence,
            attempt_checks=attempt_checks,
        )
        emit(
            f"[arena] {task.run_id} status={status} pass={solved} "
            f"attempts={attempts} requests={sink.calls}"
        )
        return record
    except Exception as exc:
        message = redact(f"{type(exc).__name__}: {exc}", secrets)
        emit(f"[arena] {task.run_id} error {message}")
        return _record(
            task, challenge_id=f"{task.mother}-{task.seed}", status="error",
            passed=False, attempts=0, sink=sink, latency_ms=_latency(started),
            failed=[], diff=0, winner=None, error=message,
        )


def _live_grade(*args, **kwargs):
    import axvigil_agent.solver as solver_mod
    return solver_mod._grade(*args, **kwargs)


def _run_agentic_member(
    client, challenge_dir, *, seed, grader, forge_bin, solc, timeout_s, emit,
    tool_protocol, max_steps, max_output_bytes, agent_wall_clock_s, token_budget,
    forge_runner,
):
    result = run_agentic(
        client, challenge_dir, protocol=tool_protocol, max_steps=max_steps,
        max_output_bytes=max_output_bytes, wall_clock_s=agent_wall_clock_s,
        token_budget=token_budget, forge_runner=forge_runner,
        forge_bin=forge_bin, solc=solc, forge_timeout_s=timeout_s,
    )
    meta = json.loads((Path(challenge_dir) / "challenge.json").read_text())
    evidence = result.evidence(tool_protocol)
    cut = result.stop_reason == "request_cap"
    if emit:
        emit(f"[agentic] stop={result.stop_reason} steps={result.steps}")
    original = (Path(challenge_dir) / "src" / meta["targetFile"]).read_text()
    target_changed = isinstance(result.patch, str) and result.patch != original
    if not target_changed:
        # A finished run that never edited the target is a graded miss, not an
        # ungraded gap. A request-cap stop stays ungraded so resume can retry it.
        if cut:
            return False, True, None, [], meta.get("challengeId"), evidence, None
        return False, False, None, ["no patch submitted"], meta.get("challengeId"), evidence, None
    if not result.poc:
        return False, cut, result.patch, [], meta.get("challengeId"), evidence, None
    grade_fn = grader if grader is not None else _live_grade
    res = grade_fn(
        challenge_dir, meta["targetFile"], result.patch, result.poc,
        seed, forge_bin, solc, timeout_s,
    )
    checks = _named_checks({
        "pocProvesBug": res.pocProvesBug,
        "pocFailsAfterPatch": res.pocFailsAfterPatch,
        "hiddenTestsPass": res.hiddenTestsPass,
        "patchWithinLimits": res.patchWithinLimits,
    })
    failed = [] if res.passed else _failed_checks(checks)
    return bool(res.passed), cut, result.patch, failed, meta.get("challengeId"), evidence, checks


def _solve_contestant(
    contestant: Contestant,
    challenge_dir: Path,
    *,
    seed: int,
    sink: _Sink,
    budget: _Budget,
    max_iters: int,
    client_factory,
    grader,
    forge_bin: str,
    solc: str | None,
    timeout_s: int,
    emit,
    tool_protocol: str = "tools",
    max_steps: int = 10,
    max_output_bytes: int = 4096,
    agent_wall_clock_s: float = 180,
    token_budget: int = 40000,
    forge_runner=None,
):
    if contestant.strategy == "ensemble":
        models = contestant.models
        strategy = contestant.member_strategy
    else:
        if not contestant.model:
            raise ValueError(f"contestant {contestant.id} has no model")
        models = (contestant.model,)
        strategy = contestant.strategy

    winner = None
    cut_short = False
    last_patch = None
    attempts = 0
    failed: list[str] = []
    challenge_id = None
    solved = False
    ran = False
    evidence = None
    attempt_checks: list[dict] = []

    for model in models:
        if budget.exhausted:
            cut_short = True
            break
        raw = client_factory(model)
        metered = _Meter(raw, budget, sink)
        if strategy == "agentic":
            solved_one, cut_one, patch, failed_one, challenge_id, evidence, graded = _run_agentic_member(
                metered, challenge_dir, seed=seed, grader=grader, forge_bin=forge_bin,
                solc=solc, timeout_s=timeout_s, emit=emit, tool_protocol=tool_protocol,
                max_steps=max_steps, max_output_bytes=max_output_bytes,
                agent_wall_clock_s=agent_wall_clock_s, token_budget=token_budget,
                forge_runner=forge_runner,
            )
            ran = True
            attempts += 1 if patch or "no patch submitted" in (failed_one or []) else 0
            if graded:
                attempt_checks.append(graded)
            if patch is not None:
                last_patch = patch
            failed = failed_one
            if cut_one:
                cut_short = True
                break
            if solved_one:
                solved = True
                failed = []
                if contestant.strategy == "ensemble":
                    winner = model
                break
            continue
        client = _Strategy(metered, strategy)
        outcome = solve(
            client, challenge_dir, seed=seed, max_iters=max_iters, grader=grader,
            forge_bin=forge_bin, solc=solc, timeout_s=timeout_s, on_event=emit,
        )
        ran = True
        challenge_id = outcome.challenge_id
        attempts += len(outcome.iterations)
        if outcome.last_patch is not None:
            last_patch = outcome.last_patch
        if outcome.iterations:
            for it in outcome.iterations:
                attempt_checks.append(_named_checks(it.checks))
            failed = _failed_checks(outcome.iterations[-1].checks)
        if outcome.stopped:
            cut_short = True
            break
        if outcome.solved:
            solved = True
            failed = []
            if contestant.strategy == "ensemble":
                winner = model
            break
    if not ran and cut_short:
        failed = []
    return solved, winner, cut_short, last_patch, attempts, failed, challenge_id, evidence, attempt_checks


def _format_attempt_checks(run: dict) -> str:
    rows = run.get("attemptChecks") or []
    if not rows:
        if "no patch submitted" in (run.get("failedChecks") or []):
            return "no patch submitted"
        return "—"
    rendered = []
    for checks in rows:
        rendered.append(" ".join(
            f"{name}={'yes' if checks.get(name) else 'no'}" for name in CHECK_NAMES
        ))
    return " || ".join(rendered)


def _named_checks(checks: dict) -> dict:
    return {name: bool(checks.get(name)) for name in CHECK_NAMES}


def _latency(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _record(
    task: _Task,
    *,
    challenge_id: str,
    status: str,
    passed: bool,
    attempts: int,
    sink: _Sink,
    latency_ms: int,
    failed: list[str],
    diff: int,
    winner: str | None,
    error: str | None,
    evidence: dict | None = None,
    attempt_checks: list[dict] | None = None,
) -> dict:
    models = list(task.contestant.models) if task.contestant.strategy == "ensemble" else [task.contestant.model]
    return {
        "runId": task.run_id,
        "contestantId": task.contestant.id,
        "model": task.contestant.model,
        "strategy": task.contestant.strategy,
        "models": models,
        "mother": task.mother,
        "seed": task.seed,
        "challengeId": challenge_id,
        "status": status,
        "pass": passed,
        "attempts": attempts,
        "requests": sink.calls,
        "tokens": {"prompt": sink.prompt, "completion": sink.completion},
        "latencyMs": latency_ms,
        "failedChecks": list(failed),
        "attemptChecks": list(attempt_checks or []),
        "patchDiffLines": diff,
        "ensembleWinner": winner,
        "error": error,
        "evidence": evidence,
    }
