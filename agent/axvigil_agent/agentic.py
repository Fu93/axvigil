"""Tool-using solver loop for Muse Spark.

Two request shapes, selected by the caller (never by a live probe):

  tools   OpenAI function calling. The chat-completions body includes `tools`
          and the assistant reply may carry `tool_calls`. This is the format
          the Meta base URL documents (OpenAI-compatible `/chat/completions`).
  json    One JSON action per turn, `{"action": "...", "arguments": {...}}`.
          Use this when a model build ignores `tool_calls`.

Tools see a workspace copy of the challenge. The hidden test file and the
reference solution are not copied, not listed, and not readable. Forge runs
offline, with ffi disabled, and only the public PoC or public tests.

Hard stops: max steps (model rounds), max tool-output bytes, wall clock, and
a token budget. The transcript of tool calls and trimmed results is the
evidence of the session; the arena stores it on the run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .model import ClientStop, ModelTurn, ToolCall
from .solver import extract_json

TOOL_NAMES = (
    "read_file",
    "list_files",
    "run_poc",
    "run_tests",
    "forge_trace",
    "apply_patch",
    "replace_in_file",
    "submit",
)
PROTOCOLS = ("tools", "json")
_PRIVATE_META_KEYS = ("hiddenTests", "hiddenTest", "solution", "referencePatch", "reference")
_TEST_FN = re.compile(r"function\s+(test_[A-Za-z0-9_]*)\s*\(")
_MAX_DIFF_CHARS = 20_000


def tool_specs() -> list[dict]:
    """OpenAI tools array. Descriptions never name the hidden test or the fix."""

    def fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        }

    path = {"type": "string", "description": "Workspace-relative path."}
    return [
        fn("read_file", "Read one workspace file. Hidden tests and the reference solution are not in the workspace.",
           {"path": path}, ["path"]),
        fn("list_files", "List workspace files under a relative directory. Defaults to the workspace root.",
           {"path": path}, []),
        fn("run_poc", "Run poc/Poc.t.sol with forge against the current sources. Offline, no network. Do not use vm.readFile; fs_permissions is empty, so import \"../src/<TargetFile>\" instead.",
           {}, []),
        fn("run_tests", "Run public tests only. Hidden tests are not available and are not run.",
           {}, []),
        fn("forge_trace", "forge test -vvvv for one public test function. The name must appear in the PoC or a public test.",
           {"name": {"type": "string", "description": "Public test function name, such as test_exploit."}}, ["name"]),
        fn("apply_patch", "Apply a unified diff to the target source or poc/Poc.t.sol. Wrong hunk line numbers are tolerated. Size-limited.",
           {"diff": {"type": "string", "description": "Unified diff (--- a/path / +++ b/path)."}}, ["diff"]),
        fn("replace_in_file", "Replace one exact occurrence of old with new in the target source or poc/Poc.t.sol. old must match exactly once.",
           {
               "path": path,
               "old": {"type": "string", "description": "Exact text to replace. Must occur once."},
               "new": {"type": "string", "description": "Replacement text."},
           }, ["path", "old", "new"]),
        fn("submit", "Finish. Provide the full patched target and the full PoC, or omit them to submit the workspace copies.",
           {
               "analysis": {"type": "string"},
               "patched_contract": {"type": "string"},
               "poc_test": {"type": "string"},
           }, []),
    ]


def system_prompt(protocol: str) -> str:
    names = ", ".join(TOOL_NAMES)
    shared = (
        "You are AxVigil, a whitehat smart-contract agent in a sandbox. "
        "Fix the vulnerability with a minimal patch and a Foundry PoC that shows the exploit. "
        f"Tools: {names}. "
        "The workspace has the vulnerable source and any public tests. "
        "Hidden tests and the reference solution are not available; do not try to read them. "
        "Edits may only touch the target source and poc/Poc.t.sol. "
        "Prefer replace_in_file when you can quote the exact old text. "
        "Do this in as few turns as you can: write the PoC, run_poc (it should pass on the vulnerable code), "
        "patch the contract, run_poc (it should then fail) and run_tests (they should pass), then submit. "
        "Batch several tool calls in one turn. Do not spend steps re-reading files you already have. "
        "Forge has no network and fs_permissions is empty. "
        "Do not call vm.readFile, vm.readLine, vm.writeFile, or any other filesystem cheatcode. "
        "vm.readFile(\"src/Target.sol\") is rejected. Import the target from \"../src/<TargetFile>\" instead."
    )
    if protocol == "json":
        return shared + (
            " Reply with ONLY JSON. One tool is "
            '{"action": "<tool>", "arguments": { ... }}. '
            "Several tools in one turn are "
            '{"actions": [{"action": "<tool>", "arguments": { ... }}, ...]}. '
            "No other text."
        )
    return shared + (
        " Use the function tools. Several tool calls in one turn are better than one. "
        "Do not wrap tool calls in prose."
    )


@dataclass
class AgenticResult:
    patch: str | None
    poc: str | None
    analysis: str
    transcript: list[dict]
    stop_reason: str
    steps: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    auto_submitted: bool = False

    def evidence(self, protocol: str) -> dict:
        return {
            "kind": "agentic-transcript",
            "protocol": protocol,
            "stopReason": self.stop_reason,
            "autoSubmitted": self.auto_submitted,
            "steps": self.steps,
            "transcript": self.transcript,
        }


@dataclass
class _ForgeObs:
    ok: bool
    output: str


@dataclass
class Workspace:
    root: Path
    meta: dict
    target_file: str
    original_target: str
    hidden_name: str | None
    max_changed_lines: int
    max_bytes: int
    files_written: dict[str, str] = field(default_factory=dict)

    def public_test_names(self) -> set[str]:
        names: set[str] = set()
        for rel in self._rel_files():
            if rel == "poc/Poc.t.sol" or (rel.startswith("test/") and rel.endswith(".t.sol")):
                names.update(_TEST_FN.findall((self.root / rel).read_text()))
        return names

    def _rel_files(self) -> list[str]:
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
            for name in filenames:
                path = Path(dirpath) / name
                if path.is_symlink():
                    continue
                rel = path.relative_to(self.root).as_posix()
                found.append(rel)
        return sorted(found)


def build_workspace(challenge_dir: Path, root: Path) -> Workspace:
    """Copy the public challenge into `root`. Hidden tests and solution/ stay behind."""
    challenge_dir = Path(challenge_dir)
    meta_full = json.loads((challenge_dir / "challenge.json").read_text())
    hidden = meta_full.get("hiddenTests")
    if isinstance(hidden, str):
        hidden = Path(hidden).name
    else:
        hidden = None
    public_meta = {k: v for k, v in meta_full.items() if k not in _PRIVATE_META_KEYS}
    limits = public_meta.get("limits") or {}
    target = meta_full["targetFile"]
    src = challenge_dir / "src"
    if not (src / target).is_file():
        raise FileNotFoundError(f"missing target {target}")
    (root / "src").mkdir(parents=True, exist_ok=True)
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(src)
        if ".." in rel.parts or hidden and hidden in rel.parts:
            continue
        dest = root / "src" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(path.read_text())
    test_dir = challenge_dir / "test"
    if test_dir.is_dir():
        for path in sorted(test_dir.glob("*.t.sol")):
            if path.is_symlink() or path.name == hidden:
                continue
            dest_dir = root / "test"
            dest_dir.mkdir(exist_ok=True)
            (dest_dir / path.name).write_text(path.read_text())
    (root / "challenge.json").write_text(json.dumps(public_meta, indent=2))
    original = (root / "src" / target).read_text()
    return Workspace(
        root=root,
        meta=public_meta,
        target_file=target,
        original_target=original,
        hidden_name=hidden,
        max_changed_lines=int(limits.get("maxChangedLines", 80)),
        max_bytes=int(limits.get("maxBytes", 16000)),
    )


def _safe_rel(workspace: Workspace, raw: str) -> tuple[str | None, str | None]:
    if not isinstance(raw, str) or not raw.strip():
        return None, "path is required"
    text = raw.strip().replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return None, "path is outside the workspace"
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None, "path is outside the workspace"
    if any(p == "solution" for p in parts):
        return None, "path is outside the workspace"
    rel = "/".join(parts)
    if workspace.hidden_name and workspace.hidden_name in parts:
        return None, "path is outside the workspace"
    candidate = (workspace.root / rel).resolve()
    try:
        candidate.relative_to(workspace.root.resolve())
    except ValueError:
        return None, "path is outside the workspace"
    return rel, None


class ScriptedToolClient:
    """Offline model. Each turn is either tool_calls or a JSON-action content string.

    No network. ``usage`` is the token pair reported after every turn.
    """

    def __init__(self, turns: list[dict], usage: tuple[int, int] = (4, 2)):
        if not turns:
            raise ValueError("ScriptedToolClient needs at least one turn")
        self.turns = turns
        self.usage = (int(usage[0]), int(usage[1]))
        self.calls = 0
        self.seen_tools: list = []
        self.history: list[list[tuple[str, str]]] = []
        self.last_usage = {"prompt": self.usage[0], "completion": self.usage[1]}

    def complete_turn(self, messages: list[dict], *, tools: list[dict] | None = None) -> ModelTurn:
        self.seen_tools.append(tools)
        self.history.append([(str(m.get("role")), str(m.get("content") or "")) for m in messages])
        spec = self.turns[min(self.calls, len(self.turns) - 1)]
        self.calls += 1
        self.last_usage = {"prompt": self.usage[0], "completion": self.usage[1]}
        if "tool_calls" in spec:
            calls = []
            raw = []
            for index, item in enumerate(spec["tool_calls"]):
                call = _call_from_spec(item, index)
                calls.append(call)
                raw.append({
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": item.get("name") or "",
                        "arguments": item.get("arguments") if isinstance(item.get("arguments"), str)
                        else json.dumps(item.get("arguments") or {}),
                    },
                })
            text = spec.get("text") or ""
            return ModelTurn(text=text, tool_calls=calls, message={"role": "assistant", "content": text or None, "tool_calls": raw})
        content = spec.get("content") or ""
        return ModelTurn(text=content, tool_calls=[], message={"role": "assistant", "content": content})


def _call_from_spec(item: dict, index: int) -> ToolCall:
    call_id = str(item.get("id") or f"call_{index}")
    name = str(item.get("name") or "")
    raw_args = item.get("arguments")
    if item.get("error"):
        return ToolCall(call_id, name, None, str(item["error"]))
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return ToolCall(call_id, name, None, "arguments are not JSON")
        if not isinstance(parsed, dict):
            return ToolCall(call_id, name, None, "arguments are not a JSON object")
        return ToolCall(call_id, name, parsed)
    if isinstance(raw_args, dict) or raw_args is None:
        return ToolCall(call_id, name, raw_args or {})
    return ToolCall(call_id, name, None, "arguments are not JSON")


def parse_json_actions(text: str) -> list[ToolCall]:
    """One action, or an `actions` list so a JSON turn can batch tools."""
    try:
        obj = extract_json(text)
    except (ValueError, TypeError):
        return [ToolCall("action", "", None, "malformed tool call")]
    batch = obj.get("actions")
    if isinstance(batch, list):
        calls: list[ToolCall] = []
        for index, item in enumerate(batch):
            if not isinstance(item, dict):
                calls.append(ToolCall(f"action_{index}", "", None, "malformed tool call"))
                continue
            calls.append(_action_call(item, f"action_{index}"))
        return calls or [ToolCall("action", "", None, "malformed tool call")]
    return [parse_json_action(text)]


def parse_json_action(text: str) -> ToolCall:
    try:
        obj = extract_json(text)
    except (ValueError, TypeError):
        return ToolCall("action", "", None, "malformed tool call")
    return _action_call(obj, "action")


def _action_call(obj: dict, call_id: str) -> ToolCall:
    name = obj.get("action") or obj.get("tool")
    if not isinstance(name, str) or not name:
        return ToolCall(call_id, "", None, "malformed tool call")
    args = obj.get("arguments", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return ToolCall(call_id, name, None, "arguments are not a JSON object")
    return ToolCall(call_id, name, args)


def _shrink_tool_history(messages: list[dict], keep_last: int) -> None:
    """Keep the last few tool results intact and replace earlier ones with one line.

    The evidence transcript stays complete. Only the messages sent back to the
    model shrink, so a long run does not resend every forge log.
    """
    indexes = []
    for index, message in enumerate(messages):
        role = message.get("role")
        content = message.get("content") or ""
        if role == "tool" or (role == "user" and str(content).startswith("Tool result:")):
            indexes.append(index)
    if keep_last < 0:
        keep_last = 0
    stale = indexes if keep_last == 0 else indexes[:-keep_last]
    for index in stale:
        content = str(messages[index].get("content") or "")
        if content.startswith("[earlier "):
            continue
        messages[index] = {**messages[index], "content": _summarize_tool_output(content)}


def _summarize_tool_output(content: str) -> str:
    first = ""
    for line in content.splitlines():
        if line.strip():
            first = line.strip()[:80]
            break
    return f"[earlier tool result, {len(content)} chars] {first}"


def trim_output(text: str, limit: int) -> tuple[str, bool]:
    if limit < 1:
        return "", True
    raw = text if isinstance(text, str) else str(text)
    data = raw.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return raw, False
    clipped = data[:limit].decode("utf-8", errors="ignore")
    return clipped + "\n…[truncated]", True


def run_agentic(
    client,
    challenge_dir: str | Path,
    *,
    protocol: str = "tools",
    max_steps: int = 10,
    max_output_bytes: int = 4096,
    wall_clock_s: float = 180,
    token_budget: int = 40_000,
    max_total_output_bytes: int = 262_144,
    keep_full_results: int = 4,
    forge_runner=None,
    clock=None,
    forge_bin: str = "forge",
    solc: str | None = None,
    forge_timeout_s: int = 60,
) -> AgenticResult:
    if protocol not in PROTOCOLS:
        raise ValueError(f"tool protocol must be one of {PROTOCOLS}")
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    now = clock or time.monotonic
    started = now()
    prompt_tokens = 0
    completion_tokens = 0
    transcript: list[dict] = []
    patch = poc = None
    analysis = ""
    stop = "max_steps"

    with tempfile.TemporaryDirectory(prefix="axv-agent-") as tmp:
        workspace = build_workspace(Path(challenge_dir), Path(tmp))
        messages = [
            {"role": "system", "content": system_prompt(protocol)},
            {"role": "user", "content": _opening_user(workspace)},
        ]
        tools = tool_specs() if protocol == "tools" else None

        def _stop(reason: str) -> AgenticResult:
            nonlocal patch, poc, analysis
            auto = False
            if patch is None and reason != "submit" and _autosubmit(
                workspace, forge_runner, forge_bin=forge_bin, solc=solc,
                forge_timeout_s=forge_timeout_s,
            ):
                patch = workspace.files_written.get("patch")
                poc = workspace.files_written.get("poc")
                analysis = workspace.files_written.get("analysis") or ""
                transcript.append({
                    "step": step, "tool": "submit", "arguments": {"auto": True},
                    "ok": True, "malformed": None, "output": "auto-submitted", "truncated": False,
                })
                auto = True
            return AgenticResult(
                patch=patch, poc=poc, analysis=analysis, transcript=transcript,
                stop_reason=reason, auto_submitted=auto,
                steps=len({row["step"] for row in transcript}) if transcript else 0,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            )

        for step in range(1, max_steps + 1):
            if now() - started > wall_clock_s:
                return _stop("wall_clock")
            if prompt_tokens + completion_tokens >= token_budget:
                return _stop("token_budget")
            _shrink_tool_history(messages, keep_full_results)
            try:
                turn = client.complete_turn(messages, tools=tools)
            except ClientStop:
                return _stop("request_cap")
            usage = getattr(client, "last_usage", None) or {}
            prompt_tokens += int(usage.get("prompt") or 0)
            completion_tokens += int(usage.get("completion") or 0)
            calls = _calls_for_turn(turn, protocol)
            messages.append(turn.message or {"role": "assistant", "content": turn.text})
            if not calls:
                note, truncated = trim_output(turn.text or "no tool call", max_output_bytes)
                transcript.append({
                    "step": step, "tool": None, "arguments": None, "ok": False,
                    "malformed": "no tool call", "output": note, "truncated": truncated,
                })
                messages.append({"role": "user", "content": "Tool result:\n" + note})
            else:
                submitted = False
                for call in calls:
                    record, output, done = _execute_call(
                        workspace, call, forge_runner, max_output_bytes,
                        forge_bin=forge_bin, solc=solc, forge_timeout_s=forge_timeout_s,
                    )
                    record["step"] = step
                    transcript.append(record)
                    if protocol == "tools" and turn.tool_calls:
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                    else:
                        messages.append({"role": "user", "content": "Tool result:\n" + output})
                    if done:
                        patch = workspace.files_written.get("patch")
                        poc = workspace.files_written.get("poc")
                        analysis = workspace.files_written.get("analysis") or ""
                        submitted = True
                        break
                if submitted:
                    return _stop("submit")
            produced = sum(len((row.get("output") or "").encode("utf-8")) for row in transcript)
            if produced > max_total_output_bytes:
                return _stop("output_bytes")
            if prompt_tokens + completion_tokens >= token_budget:
                return _stop("token_budget")
            if now() - started > wall_clock_s:
                return _stop("wall_clock")
        return _stop("max_steps")


def _calls_for_turn(turn: ModelTurn, protocol: str) -> list[ToolCall]:
    if protocol == "json":
        if not (turn.text or "").strip():
            return []
        return parse_json_actions(turn.text)
    if turn.tool_calls:
        return list(turn.tool_calls)
    if (turn.text or "").strip():
        parsed = parse_json_actions(turn.text)
        if parsed and parsed[0].error is None:
            return parsed
    return []


def _opening_user(workspace: Workspace) -> str:
    files = "\n".join(workspace._rel_files()) or "(empty)"
    return (
        f"Challenge: {workspace.meta.get('challengeId')}\n"
        f"Target file: src/{workspace.target_file} (contract {workspace.meta.get('contractName')})\n"
        f"Patch budget: at most {workspace.max_changed_lines} changed lines and "
        f"{workspace.max_bytes} bytes.\n"
        f"Public files:\n{files}\n"
        "Write the PoC, run it, patch the contract, run_poc and run_tests, then submit. "
        "Several tools per turn. Do not re-read."
    )


def _execute_call(workspace, call: ToolCall, forge_runner, limit: int, **forge_kw) -> tuple[dict, str, bool]:
    if call.error:
        output, truncated = trim_output(call.error, limit)
        return _row(call, False, output, truncated, malformed=call.error), output, False
    if call.name not in TOOL_NAMES:
        output, truncated = trim_output(f"unknown tool {call.name}", limit)
        return _row(call, False, output, truncated, malformed=f"unknown tool {call.name}"), output, False
    try:
        text, done = _dispatch(workspace, call.name, call.arguments or {}, forge_runner, **forge_kw)
        ok = not text.startswith("error:")
    except Exception as exc:
        text, done = f"error: {type(exc).__name__}", False
        ok = False
    output, truncated = trim_output(text, limit)
    return _row(call, ok, output, truncated), output, done


def _row(call: ToolCall, ok: bool, output: str, truncated: bool, malformed: str | None = None) -> dict:
    return {
        "tool": call.name or None,
        "arguments": call.arguments,
        "ok": ok,
        "malformed": malformed,
        "output": output,
        "truncated": truncated,
    }


def _dispatch(workspace: Workspace, name: str, args: dict, forge_runner, **forge_kw) -> tuple[str, bool]:
    if name == "read_file":
        return _read_file(workspace, args.get("path")), False
    if name == "list_files":
        return _list_files(workspace, args.get("path") or "."), False
    if name == "run_poc":
        return _run_poc(workspace, forge_runner, **forge_kw), False
    if name == "run_tests":
        return _run_tests(workspace, forge_runner, **forge_kw), False
    if name == "forge_trace":
        return _forge_trace(workspace, args.get("name"), forge_runner, **forge_kw), False
    if name == "apply_patch":
        return _apply_patch(workspace, args.get("diff")), False
    if name == "replace_in_file":
        return _replace_in_file(workspace, args), False
    if name == "submit":
        return _submit(workspace, args)
    return f"error: unknown tool {name}", False


def _read_file(workspace: Workspace, raw) -> str:
    rel, err = _safe_rel(workspace, raw if isinstance(raw, str) else "")
    if err:
        return f"error: {err}"
    path = workspace.root / rel
    if not path.is_file() or path.is_symlink():
        return "error: file not found"
    return path.read_text()


def _list_files(workspace: Workspace, raw) -> str:
    rel, err = _safe_rel(workspace, raw if isinstance(raw, str) else ".")
    if err:
        return f"error: {err}"
    base = workspace.root / rel
    if rel == "":
        base = workspace.root
    if not base.exists():
        return "error: file not found"
    if base.is_file():
        return rel
    lines = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not (Path(dirpath) / d).is_symlink())
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            lines.append(path.relative_to(workspace.root).as_posix())
    return "\n".join(lines) if lines else "(no files)"


def _run_poc(workspace: Workspace, forge_runner, **forge_kw) -> str:
    poc = workspace.root / "poc" / "Poc.t.sol"
    if not poc.is_file():
        return "error: no public PoC yet; apply_patch poc/Poc.t.sol first"
    return _forge(workspace, forge_runner, tests={"Poc.t.sol": poc.read_text()}, match_test=None, verbosity=0, **forge_kw)


def _run_tests(workspace: Workspace, forge_runner, **forge_kw) -> str:
    tests = {}
    test_dir = workspace.root / "test"
    if test_dir.is_dir():
        for path in sorted(test_dir.glob("*.t.sol")):
            if path.is_symlink() or path.name == workspace.hidden_name:
                continue
            tests[path.name] = path.read_text()
    if not tests:
        return "no public tests"
    return _forge(workspace, forge_runner, tests=tests, match_test=None, verbosity=0, **forge_kw)


def _forge_trace(workspace: Workspace, name, forge_runner, **forge_kw) -> str:
    if not isinstance(name, str) or not name.strip():
        return "error: name is required"
    name = name.strip()
    if name not in workspace.public_test_names():
        return "error: not a public test"
    tests = {}
    poc = workspace.root / "poc" / "Poc.t.sol"
    if poc.is_file() and name in _TEST_FN.findall(poc.read_text()):
        tests["Poc.t.sol"] = poc.read_text()
    test_dir = workspace.root / "test"
    if test_dir.is_dir():
        for path in sorted(test_dir.glob("*.t.sol")):
            if path.name == workspace.hidden_name or path.is_symlink():
                continue
            body = path.read_text()
            if name in _TEST_FN.findall(body):
                tests[path.name] = body
    if not tests:
        return "error: not a public test"
    return _forge(workspace, forge_runner, tests=tests, match_test=name, verbosity=4, **forge_kw)


def _sources(workspace: Workspace) -> dict[str, str]:
    sources = {}
    src = workspace.root / "src"
    for path in sorted(src.rglob("*.sol")):
        if path.is_symlink():
            continue
        sources[path.relative_to(src).as_posix()] = path.read_text()
    return sources


def _forge(workspace, forge_runner, *, tests, match_test, verbosity, forge_bin, solc, forge_timeout_s) -> str:
    sources = _sources(workspace)
    runner = forge_runner or default_forge_runner
    obs = runner(
        sources=sources, tests=tests, match_test=match_test, verbosity=verbosity,
        forge_bin=forge_bin, solc=solc, timeout_s=forge_timeout_s,
    )
    if hasattr(obs, "ok") and hasattr(obs, "output"):
        body = str(obs.output)
        ok = bool(obs.ok)
    elif isinstance(obs, str):
        body = obs
        ok = body.startswith("pass:")
    else:
        body = str(obs)
        ok = False
    flag = "true" if ok else "false"
    return f"pass: {flag}\n{body}"


def _submit(workspace: Workspace, args: dict) -> tuple[str, bool]:
    target_rel = f"src/{workspace.target_file}"
    patch = args.get("patched_contract")
    poc = args.get("poc_test")
    if patch is None:
        path = workspace.root / target_rel
        patch = path.read_text() if path.is_file() else None
    if poc is None:
        poc_path = workspace.root / "poc" / "Poc.t.sol"
        poc = poc_path.read_text() if poc_path.is_file() else None
    if not isinstance(patch, str) or not patch.strip():
        return "error: submit needs a patched contract", False
    if not isinstance(poc, str) or not poc.strip():
        return "error: submit needs a PoC", False
    if len(patch.encode("utf-8")) > workspace.max_bytes:
        return "error: patched file exceeds the byte limit", False
    if _changed_lines(workspace.original_target, patch) > workspace.max_changed_lines:
        return "error: patch exceeds the line budget", False
    workspace.files_written["patch"] = patch
    workspace.files_written["poc"] = poc
    workspace.files_written["analysis"] = str(args.get("analysis") or "")
    return "submitted", True


def _changed_lines(before: str, after: str) -> int:
    import difflib
    a = before.replace("\r\n", "\n").split("\n")
    b = after.replace("\r\n", "\n").split("\n")
    count = 0
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def apply_unified_to(base_for, diff: str) -> dict[str, str]:
    """`base_for(rel) -> str | None`. None means the file must be created."""
    lines = diff.replace("\r\n", "\n").splitlines()
    index = 0
    out: dict[str, str] = {}
    saw = False
    while index < len(lines):
        line = lines[index]
        if not line.startswith("--- "):
            index += 1
            continue
        saw = True
        old = _diff_path(line[4:])
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise ValueError("diff header is incomplete")
        new = _diff_path(lines[index + 1][4:])
        rel = new or old
        if not rel:
            raise ValueError("diff header is incomplete")
        index += 2
        hunks = []
        while index < len(lines) and lines[index].startswith("@@"):
            hunk, index = _parse_hunk(lines, index)
            hunks.append(hunk)
        base = "" if old is None else base_for(rel)
        if base is None:
            raise ValueError("diff does not match a workspace file")
        out[rel] = _apply_hunks(base, hunks)
    if not saw:
        raise ValueError("diff has no files")
    return out


def _diff_path(header: str) -> str | None:
    text = header.strip()
    if "\t" in text:
        text = text.split("\t", 1)[0].strip()
    if text in ("/dev/null", "dev/null"):
        return None
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    return text


def _parse_hunk(lines: list[str], index: int):
    header = lines[index]
    match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
    if not match:
        raise ValueError("malformed hunk")
    old_start = int(match.group(1))
    body = []
    index += 1
    while index < len(lines):
        line = lines[index]
        if line.startswith("--- ") or line.startswith("@@"):
            break
        if line.startswith("\\"):
            index += 1
            continue
        if not line:
            # A blank line in a diff is a context line of empty text only when
            # it was prefixed. An entirely empty line is not a valid hunk line.
            break
        tag = line[0]
        if tag not in " +-":
            break
        body.append((tag, line[1:]))
        index += 1
    return {"old_start": old_start, "lines": body}, index


def _apply_hunks(original: str, hunks: list[dict]) -> str:
    """Apply hunks, sliding them when the header line number is wrong.

    A stated count is ignored: the hunk body is what gets matched. Search
    starts at the header line, then anywhere later in the file. Up to two
    context lines are dropped from each end (fuzz) if the full context misses.
    """
    src = original.splitlines(keepends=True)
    norms = [_norm(line) for line in src]
    out: list[str] = []
    cursor = 0
    for hunk in hunks:
        located = _locate_hunk(norms, hunk, cursor)
        if located is None:
            raise ValueError("hunk does not apply")
        start, end, new_lines = located
        out.extend(src[cursor:start])
        out.extend(new_lines)
        cursor = end
    out.extend(src[cursor:])
    return "".join(out)


def _locate_hunk(norms: list[str], hunk: dict, cursor: int):
    hint = 0 if hunk["old_start"] == 0 else max(hunk["old_start"] - 1, 0)
    for fuzz in (0, 1, 2):
        pattern, replacement = _hunk_pattern(hunk, fuzz)
        found = _find_pattern(norms, pattern, cursor, hint)
        if found is not None:
            start, end = found
            return start, end, replacement
    return None


def _hunk_pattern(hunk: dict, fuzz: int) -> tuple[list[str], list[str]]:
    body = hunk["lines"]
    lead = 0
    while lead < len(body) and body[lead][0] == " ":
        lead += 1
    trail = 0
    while trail < len(body) - lead and body[-1 - trail][0] == " ":
        trail += 1
    drop_lead = min(fuzz, lead)
    drop_trail = min(fuzz, trail)
    if drop_trail:
        kept = body[drop_lead:len(body) - drop_trail]
    else:
        kept = body[drop_lead:]
    pattern = [_norm(text) for tag, text in kept if tag in (" ", "-")]
    replacement = []
    for tag, text in kept:
        if tag in (" ", "+"):
            replacement.append(text if text.endswith("\n") else text + "\n")
    return pattern, replacement


def _find_pattern(norms: list[str], pattern: list[str], cursor: int, hint: int):
    if cursor > len(norms):
        return None
    if not pattern:
        at = min(max(hint, cursor), len(norms))
        return at, at
    width = len(pattern)
    best = None
    best_dist = None
    last = len(norms) - width
    for index in range(cursor, last + 1):
        if norms[index:index + width] == pattern:
            dist = abs(index - hint)
            if best is None or dist < best_dist:
                best = index
                best_dist = dist
                if dist == 0:
                    break
    if best is None:
        return None
    return best, best + width


def _norm(line: str) -> str:
    return line[:-1] if line.endswith("\n") else line


def _allowed_edit(workspace: Workspace, rel: str) -> str | None:
    safe, err = _safe_rel(workspace, rel)
    if err or safe not in {f"src/{workspace.target_file}", "poc/Poc.t.sol"}:
        return None
    return safe


def _apply_patch(workspace: Workspace, diff) -> str:
    if not isinstance(diff, str) or not diff.strip():
        return "error: diff is required"
    if len(diff) > _MAX_DIFF_CHARS:
        return "error: diff exceeds the size limit"
    rels = _diff_rels(diff)
    if not rels:
        return "error: diff has no files"
    if any(_allowed_edit(workspace, rel) is None for rel in rels):
        return "error: path is outside the workspace"

    files = _git_apply(workspace, diff, rels)
    if files is None:
        def base_for(rel: str):
            safe = _allowed_edit(workspace, rel)
            if safe is None:
                raise ValueError("path is outside the workspace")
            path = workspace.root / safe
            if path.is_file():
                return path.read_text()
            if safe == "poc/Poc.t.sol":
                return ""
            raise ValueError("diff does not match a workspace file")

        try:
            files = apply_unified_to(base_for, diff)
        except ValueError:
            return _hunk_mismatch(workspace, diff)
    return _write_edits(workspace, files)


def _replace_in_file(workspace: Workspace, args: dict) -> str:
    safe = _allowed_edit(workspace, args.get("path") if isinstance(args.get("path"), str) else "")
    if safe is None:
        return "error: path is outside the workspace"
    old = args.get("old")
    new = args.get("new")
    if not isinstance(old, str) or old == "":
        return "error: old is required"
    if not isinstance(new, str):
        return "error: new is required"
    path = workspace.root / safe
    if path.is_file():
        text = path.read_text()
    elif safe == "poc/Poc.t.sol":
        text = ""
    else:
        return "error: file not found"
    found = text.count(old)
    if found == 0:
        return "error: old text not found"
    if found != 1:
        return f"error: old text matched {found} times; need a unique match"
    written = _write_edits(workspace, {safe: text.replace(old, new, 1)})
    if written.startswith("error:"):
        return written
    return "replaced 1 match"


def _write_edits(workspace: Workspace, files: dict[str, str]) -> str:
    staged: dict[str, str] = {}
    for rel, new_text in files.items():
        safe = _allowed_edit(workspace, rel)
        if safe is None:
            return "error: path is outside the workspace"
        if not new_text.endswith("\n") and new_text != "":
            new_text += "\n"
        if safe.startswith("src/") and len(new_text.encode("utf-8")) > workspace.max_bytes:
            return "error: patched file exceeds the byte limit"
        if safe.startswith("src/") and _changed_lines(workspace.original_target, new_text) > workspace.max_changed_lines:
            return "error: patch exceeds the line budget"
        staged[safe] = new_text
    for safe, new_text in staged.items():
        dest = workspace.root / safe
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(new_text)
    return "applied " + ", ".join(sorted(staged))


def _autosubmit(workspace: Workspace, forge_runner, **forge_kw) -> bool:
    """Last-step save: the patch closed the PoC and public tests still pass."""
    target = workspace.root / "src" / workspace.target_file
    poc_path = workspace.root / "poc" / "Poc.t.sol"
    if not target.is_file() or not poc_path.is_file():
        return False
    current = target.read_text()
    if current == workspace.original_target:
        return False
    if len(current.encode("utf-8")) > workspace.max_bytes:
        return False
    if _changed_lines(workspace.original_target, current) > workspace.max_changed_lines:
        return False
    poc_out = _run_poc(workspace, forge_runner, **forge_kw)
    if not str(poc_out).startswith("pass: false"):
        return False
    tests_out = _run_tests(workspace, forge_runner, **forge_kw)
    if tests_out != "no public tests" and not str(tests_out).startswith("pass: true"):
        return False
    workspace.files_written["patch"] = current
    workspace.files_written["poc"] = poc_path.read_text()
    workspace.files_written["analysis"] = "auto-submitted on the last step"
    return True


def _diff_rels(diff: str) -> list[str]:
    rels: list[str] = []
    for line in diff.replace("\r\n", "\n").splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            rel = _diff_path(line[4:])
            if rel:
                rels.append(rel)
        elif line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                for item in parts[2:4]:
                    rel = _diff_path(item)
                    if rel:
                        rels.append(rel)
    # Preserve order, drop duplicates.
    seen: list[str] = []
    for rel in rels:
        if rel not in seen:
            seen.append(rel)
    return seen


def _git_apply(workspace: Workspace, diff: str, rels: list[str]) -> dict[str, str] | None:
    """`git apply --recount`, then again with one line of context fuzz (`-C1`)."""
    if shutil.which("git") is None:
        return None
    strip = "1" if _diff_uses_ab_prefix(diff) else "0"
    with tempfile.TemporaryDirectory(prefix="axv-apply-") as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q"], cwd=root, check=False, capture_output=True)
        originals: dict[str, str | None] = {}
        for rel in rels:
            safe = _allowed_edit(workspace, rel)
            if safe is None:
                return None
            dest = root / safe
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = workspace.root / safe
            if src.is_file():
                originals[safe] = src.read_text()
                dest.write_text(originals[safe])
            else:
                # A new PoC is created by the diff. Do not pre-create it:
                # git apply treats /dev/null as "file must not exist yet".
                originals[safe] = None
        patch = root / "incoming.diff"
        patch.write_text(diff if diff.endswith("\n") else diff + "\n")
        for extra in ([], ["-C1"]):
            for safe, text in originals.items():
                dest = root / safe
                if text is None:
                    if dest.exists():
                        dest.unlink()
                else:
                    dest.write_text(text)
            proc = subprocess.run(
                ["git", "apply", "--recount", "--whitespace=nowarn", f"-p{strip}", *extra, str(patch)],
                cwd=root, capture_output=True, text=True, check=False,
            )
            if proc.returncode == 0 and all((root / safe).is_file() for safe in originals):
                return {safe: (root / safe).read_text() for safe in originals}
    return None


def _diff_uses_ab_prefix(diff: str) -> bool:
    for line in diff.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            text = line[4:].strip()
            return text.startswith("a/") or text.startswith("b/") or text.startswith("/dev/null")
    return True


def _hunk_mismatch(workspace: Workspace, diff: str) -> str:
    """Short failure: the claimed lines, then the file lines around that number."""
    target = workspace.root / "src" / workspace.target_file
    text = target.read_text() if target.is_file() else ""
    file_lines = text.splitlines()
    hunk = _first_hunk(diff)
    if hunk is None:
        return "error: hunk does not apply"
    claimed = [_norm(line) for tag, line in hunk["lines"] if tag in (" ", "-")][:4]
    start = hunk["old_start"] if hunk["old_start"] else 1
    begin = max(start - 1, 1)
    end = min(begin + 5, len(file_lines))
    actual = [f"{number}:{file_lines[number - 1]}" for number in range(begin, end + 1)]
    claimed_s = " | ".join(claimed)[:160]
    actual_s = " | ".join(actual)[:220]
    return (
        f"error: hunk does not apply near line {hunk['old_start']}; "
        f"claimed: {claimed_s}; actual: {actual_s}"
    )


def _first_hunk(diff: str):
    lines = diff.replace("\r\n", "\n").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("@@"):
            try:
                hunk, _ = _parse_hunk(lines, index)
            except ValueError:
                return None
            return hunk
    return None


def default_forge_runner(*, sources, tests, match_test, verbosity, forge_bin, solc, timeout_s):
    """Offline forge. Public files only; the caller never passes hidden tests."""
    if verbosity:
        return _run_trace(sources, tests, match_test, forge_bin, solc, timeout_s)
    from axvigil_verifier.forge_runner import run_test
    observations = []
    ok = True
    for name in sorted(tests):
        result = run_test(
            sources=sources, tests={name: tests[name]}, match_path=f"test/{name}",
            forge_bin=forge_bin, solc=solc, timeout_s=timeout_s,
        )
        if not result.all_passed:
            ok = False
        observations.append(f"{name}: {'pass' if result.all_passed else 'fail'}")
        if result.raw and not result.all_passed:
            observations.append(result.raw[-1500:])
    return _ForgeObs(ok=ok and bool(tests), output="\n".join(observations) or "no tests")


def forge_trace_command(forge_bin: str, match_test: str, solc: str | None) -> list[str]:
    cmd = [forge_bin, "test", "-vvvv", "--match-test", match_test, "--fuzz-seed", "0xA11CE"]
    if solc:
        cmd += ["--use", solc]
    return cmd


def _run_trace(sources, tests, match_test, forge_bin, solc, timeout_s) -> _ForgeObs:
    from axvigil_verifier.forge_runner import DEFAULT_FORGE_STD, DEFAULT_OZ, _foundry_toml
    workdir = Path(tempfile.mkdtemp(prefix="axv-trace-"))
    try:
        (workdir / "src").mkdir()
        (workdir / "test").mkdir()
        (workdir / "foundry.toml").write_text(_foundry_toml(DEFAULT_FORGE_STD, DEFAULT_OZ, solc))
        for name, text in sources.items():
            dest = workdir / "src" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        for name, text in tests.items():
            (workdir / "test" / name).write_text(text)
        env = dict(os.environ)
        env["FOUNDRY_OFFLINE"] = "true"
        cmd = forge_trace_command(forge_bin, match_test or "", solc)
        try:
            proc = subprocess.run(
                cmd, cwd=workdir, env=env, capture_output=True, text=True,
                timeout=timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            return _ForgeObs(False, "timeout")
        except FileNotFoundError:
            return _ForgeObs(False, "forge was not found")
        output = (proc.stdout or "") + (proc.stderr or "")
        return _ForgeObs(proc.returncode == 0, output)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

