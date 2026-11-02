"""Offline tests for the tool-using solver. No network and no forge."""

from __future__ import annotations

import json
from pathlib import Path

from axvigil_agent.agentic import (
    ScriptedToolClient,
    build_workspace,
    forge_trace_command,
    run_agentic,
    tool_specs,
)
from axvigil_agent.arena import parse_contestant_spec, run_arena
from axvigil_agent.model import MetaModelClient, parse_assistant_message

SOURCE = "contract Vault {\n    function withdraw() external {}\n}\n"
HIDDEN = "contract HiddenTest {\n    function test_secret() public { /* HIDDEN_SENTINEL */ }\n}\n"
REFERENCE = "contract Vault {\n    /* REFERENCE_SENTINEL */\n}\n"
PUBLIC = "contract PublicTest {\n    function test_publicOk() public {}\n}\n"
FIXED_DIFF = """--- a/src/Vault.sol
+++ b/src/Vault.sol
@@ -1,3 +1,4 @@
 contract Vault {
     function withdraw() external {}
+    // FIXED
 }
"""
POC = "contract Poc { function test_exploit() public {} }\n"
POC_DIFF = """--- /dev/null
+++ b/poc/Poc.t.sol
@@ -0,0 +1,3 @@
+contract Poc {
+    function test_exploit() public {}
+}
"""


def _challenge(tmp_path: Path) -> Path:
    root = tmp_path / "chal"
    (root / "src").mkdir(parents=True)
    (root / "src" / "Vault.sol").write_text(SOURCE)
    (root / "test").mkdir()
    (root / "test" / "Hidden.t.sol").write_text(HIDDEN)
    (root / "test" / "Public.t.sol").write_text(PUBLIC)
    (root / "solution" / "patched").mkdir(parents=True)
    (root / "solution" / "patched" / "Vault.sol").write_text(REFERENCE)
    (root / "challenge.json").write_text(json.dumps({
        "challengeId": "reentrancy-1",
        "targetFile": "Vault.sol",
        "contractName": "Vault",
        "vulnClass": 0,
        "difficulty": 0,
        "requiredFunctions": ["withdraw"],
        "hiddenTests": "Hidden.t.sol",
        "pragma": "0.8.28",
        "limits": {"maxChangedLines": 12, "maxBytes": 6000},
    }))
    return root


class _Obs:
    def __init__(self, ok=True, output="ok"):
        self.ok = ok
        self.output = output


def _runner_factory(calls):
    def runner(*, sources, tests, match_test, verbosity, forge_bin, solc, timeout_s):
        calls.append({
            "sources": sources, "tests": tests, "match_test": match_test, "verbosity": verbosity,
        })
        return _Obs(True, "forge-ok")
    return runner


def _submit_args():
    return {
        "analysis": "fixed",
        "patched_contract": SOURCE + "// FIXED\n",
        "poc_test": POC,
    }


def test_workspace_hides_the_reference_and_hidden_test(tmp_path):
    challenge = _challenge(tmp_path)
    workspace = build_workspace(challenge, tmp_path / "ws")
    listing = "\n".join(workspace._rel_files())
    blob = listing + (workspace.root / "challenge.json").read_text()
    assert "HIDDEN_SENTINEL" not in blob
    assert "REFERENCE_SENTINEL" not in blob
    assert "Hidden.t.sol" not in blob
    assert "solution" not in listing
    assert "test/Public.t.sol" in listing
    assert "src/Vault.sol" in listing


def test_dispatch_reads_patches_and_submits(tmp_path):
    challenge = _challenge(tmp_path)
    calls = []
    client = ScriptedToolClient([
        {"tool_calls": [{"name": "list_files", "arguments": {"path": "."}}]},
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]},
        {"tool_calls": [{"name": "apply_patch", "arguments": {"diff": FIXED_DIFF}}]},
        {"tool_calls": [{"name": "apply_patch", "arguments": {"diff": POC_DIFF}}]},
        {"tool_calls": [{"name": "run_poc", "arguments": {}}]},
        {"tool_calls": [{"name": "run_tests", "arguments": {}}]},
        {"tool_calls": [{"name": "forge_trace", "arguments": {"name": "test_publicOk"}}]},
        {"tool_calls": [{"name": "submit", "arguments": {}}]},
    ])
    result = run_agentic(
        client, challenge, protocol="tools", max_steps=8, forge_runner=_runner_factory(calls),
    )
    assert result.stop_reason == "submit"
    assert "// FIXED" in (result.patch or "")
    assert "test_exploit" in (result.poc or "")
    names = [row["tool"] for row in result.transcript]
    assert names == ["list_files", "read_file", "apply_patch", "apply_patch", "run_poc", "run_tests", "forge_trace", "submit"]
    assert client.seen_tools[0]  # tools array was offered
    assert any(spec["function"]["name"] == "submit" for spec in tool_specs())
    blob = json.dumps(result.transcript)
    assert "HIDDEN_SENTINEL" not in blob and "REFERENCE_SENTINEL" not in blob
    assert calls, "public forge should have run"
    for call in calls:
        joined = json.dumps(call)
        assert "HIDDEN_SENTINEL" not in joined
        assert "Hidden.t.sol" not in joined


def test_json_protocol_does_not_send_tools_and_submits(tmp_path):
    challenge = _challenge(tmp_path)
    client = ScriptedToolClient([
        {"content": json.dumps({"action": "read_file", "arguments": {"path": "src/Vault.sol"}})},
        {"content": json.dumps({"action": "submit", "arguments": _submit_args()})},
    ])
    result = run_agentic(client, challenge, protocol="json", max_steps=4, forge_runner=_runner_factory([]))
    assert result.stop_reason == "submit"
    assert result.patch.endswith("// FIXED\n") or "// FIXED" in result.patch
    assert client.seen_tools == [None, None]
    assert result.evidence("json")["protocol"] == "json"
    assert result.evidence("json")["transcript"][0]["tool"] == "read_file"


def test_malformed_tool_call_is_recorded_and_does_not_crash(tmp_path):
    challenge = _challenge(tmp_path)
    client = ScriptedToolClient([
        {"tool_calls": [{"name": "read_file", "arguments": "{not json"}]},
        {"tool_calls": [{"name": "shell", "arguments": {}}]},
        {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
    ])
    result = run_agentic(client, challenge, protocol="tools", max_steps=4, forge_runner=_runner_factory([]))
    assert result.stop_reason == "submit"
    assert result.transcript[0]["malformed"] == "arguments are not JSON"
    assert "unknown tool" in (result.transcript[1]["malformed"] or "")
    assert result.transcript[2]["tool"] == "submit"


def test_path_traversal_and_hidden_paths_are_rejected(tmp_path):
    challenge = _challenge(tmp_path)
    secret = tmp_path / "outside.txt"
    secret.write_text("OUTSIDE_SENTINEL")
    attacks = [
        "../../outside.txt",
        "../outside.txt",
        "/etc/passwd",
        "solution/patched/Vault.sol",
        "test/Hidden.t.sol",
        "src/../../outside.txt",
    ]
    turns = [{"tool_calls": [{"name": "read_file", "arguments": {"path": path}}]} for path in attacks]
    turns.append({"tool_calls": [{"name": "apply_patch", "arguments": {"diff":
        "--- a/../outside.txt\n+++ b/../outside.txt\n@@ -0,0 +1 @@\n+pwn\n"}}]})
    turns.append({"tool_calls": [{"name": "forge_trace", "arguments": {"name": "test_secret"}}]})
    turns.append({"tool_calls": [{"name": "submit", "arguments": _submit_args()}]})
    calls = []
    result = run_agentic(
        ScriptedToolClient(turns), challenge, protocol="tools", max_steps=len(turns),
        forge_runner=_runner_factory(calls),
    )
    blob = json.dumps(result.transcript)
    assert "OUTSIDE_SENTINEL" not in blob
    assert "HIDDEN_SENTINEL" not in blob
    assert "REFERENCE_SENTINEL" not in blob
    assert all("outside the workspace" in (row["output"] or "") or "not a public test" in (row["output"] or "")
               for row in result.transcript if row["tool"] != "submit")
    assert calls == []
    assert result.stop_reason == "submit"


def test_run_tests_with_only_a_hidden_file_does_not_call_forge(tmp_path):
    challenge = _challenge(tmp_path)
    (challenge / "test" / "Public.t.sol").unlink()
    calls = []
    client = ScriptedToolClient([
        {"tool_calls": [{"name": "run_tests", "arguments": {}}]},
        {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
    ])
    result = run_agentic(client, challenge, max_steps=3, forge_runner=_runner_factory(calls))
    assert calls == []
    assert result.transcript[0]["output"] == "no public tests"
    assert "HIDDEN_SENTINEL" not in result.transcript[0]["output"]


def test_max_steps_token_budget_and_output_trim(tmp_path):
    challenge = _challenge(tmp_path)
    client = ScriptedToolClient(
        [{"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]}],
        usage=(80, 80),
    )
    stopped = run_agentic(client, challenge, max_steps=1, forge_runner=_runner_factory([]))
    assert stopped.stop_reason == "max_steps"
    assert client.calls == 1

    rich = ScriptedToolClient(
        [{"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]}],
        usage=(40, 40),
    )
    budget = run_agentic(rich, challenge, max_steps=4, token_budget=50, forge_runner=_runner_factory([]))
    assert budget.stop_reason == "token_budget"
    assert rich.calls == 1

    noisy = ScriptedToolClient([
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]},
        {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
    ])
    trimmed = run_agentic(noisy, challenge, max_steps=3, max_output_bytes=24, forge_runner=_runner_factory([]))
    assert trimmed.transcript[0]["truncated"] is True
    assert len(trimmed.transcript[0]["output"].encode()) <= 24 + len("\n…[truncated]".encode())


def test_wall_clock_stops_before_a_second_model_call(tmp_path):
    challenge = _challenge(tmp_path)
    ticks = iter([0, 0, 100])

    def clock():
        return next(ticks)

    client = ScriptedToolClient([
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]},
        {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
    ])
    result = run_agentic(
        client, challenge, max_steps=4, wall_clock_s=10, clock=clock, forge_runner=_runner_factory([]),
    )
    assert result.stop_reason == "wall_clock"
    assert client.calls == 1
    assert result.patch is None


def test_arena_agentic_records_the_transcript_and_grades(tmp_path):
    def render(mother, seed, out):
        out = Path(out)
        (out / "src").mkdir(parents=True)
        (out / "src" / "Vault.sol").write_text(SOURCE)
        (out / "test").mkdir()
        (out / "test" / "Hidden.t.sol").write_text(HIDDEN)
        (out / "solution" / "patched").mkdir(parents=True)
        (out / "solution" / "patched" / "Vault.sol").write_text(REFERENCE)
        (out / "challenge.json").write_text(json.dumps({
            "challengeId": f"{mother}-{seed}",
            "targetFile": "Vault.sol",
            "contractName": "Vault",
            "vulnClass": 0,
            "requiredFunctions": ["withdraw"],
            "hiddenTests": "Hidden.t.sol",
            "pragma": "0.8.28",
            "limits": {"maxChangedLines": 12, "maxBytes": 6000},
        }))

    class Grade:
        def __init__(self, passed):
            self.passed = passed
            self.pocProvesBug = True
            self.pocFailsAfterPatch = passed
            self.hiddenTestsPass = passed
            self.patchWithinLimits = True
            self.log = "ok"
            self.submissionHash = "0x" + "ab" * 32

    def grade(challenge_dir, target_file, patch, poc, seed, forge_bin, solc, timeout_s):
        assert "HIDDEN_SENTINEL" not in patch and "HIDDEN_SENTINEL" not in poc
        return Grade("// FIXED" in patch)

    def factory(_model):
        return ScriptedToolClient([
            {"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]},
            {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
        ], usage=(3, 1))

    result = run_arena(
        [parse_contestant_spec("muse-spark-1.1:agentic")],
        ["reentrancy"], [1],
        out_path=tmp_path / "arena_results.json",
        request_cap=6, max_iters=1, max_steps=4,
        client_factory=factory, grader=grade, render_fn=render, forge_runner=_runner_factory([]),
    )
    run = result["runs"][0]
    assert run["strategy"] == "agentic"
    assert run["pass"] is True
    assert run["attempts"] == 1
    assert run["requests"] == 2
    assert run["tokens"] == {"prompt": 6, "completion": 2}
    assert run["evidence"]["transcript"][0]["tool"] == "read_file"
    assert run["evidence"]["stopReason"] == "submit"
    assert "HIDDEN_SENTINEL" not in json.dumps(run["evidence"])
    assert run["patchDiffLines"] >= 1


def test_request_cap_stops_the_agentic_loop(tmp_path):
    def render(mother, seed, out):
        out = Path(out)
        (out / "src").mkdir(parents=True)
        (out / "src" / "Vault.sol").write_text(SOURCE)
        (out / "challenge.json").write_text(json.dumps({
            "challengeId": f"{mother}-{seed}", "targetFile": "Vault.sol", "contractName": "Vault",
            "vulnClass": 0, "requiredFunctions": ["withdraw"], "pragma": "0.8.28",
            "limits": {"maxChangedLines": 12, "maxBytes": 6000},
        }))

    def factory(_model):
        return ScriptedToolClient([
            {"tool_calls": [{"name": "read_file", "arguments": {"path": "src/Vault.sol"}}]},
            {"tool_calls": [{"name": "submit", "arguments": _submit_args()}]},
        ])

    result = run_arena(
        [parse_contestant_spec("muse-spark-1.1:agentic")],
        ["reentrancy"], [1],
        out_path=tmp_path / "out.json", request_cap=1, max_steps=4,
        client_factory=factory, grader=lambda *a, **k: (_ for _ in ()).throw(AssertionError("no grade")),
        render_fn=render,
    )
    run = result["runs"][0]
    assert run["status"] == "budget"
    assert run["requests"] == 1
    assert run["pass"] is False
    assert run["evidence"]["stopReason"] == "request_cap"


def test_parse_assistant_message_and_client_sends_tools(monkeypatch):
    bad = parse_assistant_message({
        "content": None,
        "tool_calls": [{
            "id": "c1",
            "type": "function",
            "function": {"name": "read_file", "arguments": "not-json"},
        }],
    })
    assert bad.tool_calls[0].error == "arguments are not JSON"
    good = parse_assistant_message({
        "content": "",
        "tool_calls": [{
            "id": "c2",
            "type": "function",
            "function": {"name": "list_files", "arguments": "{\"path\":\".\"}"},
        }],
    })
    assert good.tool_calls[0].arguments == {"path": "."}

    monkeypatch.setenv("META_API_KEY", "super-secret-key-zz")
    monkeypatch.delenv("META_MAX_TOKENS", raising=False)

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "c3",
                        "type": "function",
                        "function": {"name": "submit", "arguments": "{\"analysis\":\"a\"}"},
                    }],
                }}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }).encode()

    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data.decode())
        seen["timeout"] = timeout
        return Resp()

    monkeypatch.setattr("axvigil_agent.model.urllib.request.urlopen", fake_urlopen)
    client = MetaModelClient(temperature=0)
    turn = client.complete_turn(
        [{"role": "user", "content": "go"}],
        tools=[{"type": "function", "function": {"name": "submit"}}],
    )
    assert seen["body"]["tools"][0]["function"]["name"] == "submit"
    assert seen["body"]["tool_choice"] == "auto"
    assert "super-secret-key-zz" not in json.dumps(seen["body"])
    assert turn.tool_calls[0].name == "submit"
    assert client.last_usage == {"prompt": 5, "completion": 2}
    plain = client.complete_turn([{"role": "user", "content": "go"}], tools=None)
    assert "tools" not in seen["body"]
    assert plain.tool_calls[0].arguments == {"analysis": "a"}


def test_trace_command_is_verbose_and_names_only_the_public_test():
    cmd = forge_trace_command("forge", "test_publicOk", None)
    assert cmd[:4] == ["forge", "test", "-vvvv", "--match-test"]
    assert "test_publicOk" in cmd
    assert "Hidden" not in " ".join(cmd)


def test_cli_agentic_flag(tmp_path, monkeypatch):
    from axvigil_agent.__main__ import main
    monkeypatch.setenv("META_API_KEY", "cli-test-key-not-logged")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    class Stub:
        def __init__(self, **kwargs):
            self.last_usage = {"prompt": 1, "completion": 1}
            Stub.kwargs = kwargs

        def complete_turn(self, messages, *, tools=None):
            self.last_usage = {"prompt": 2, "completion": 2}
            from axvigil_agent.model import ModelTurn
            payload = json.dumps({"action": "submit", "arguments": _submit_args()})
            return ModelTurn(text=payload, tool_calls=[], message={"role": "assistant", "content": payload})

    class Grade:
        passed = True
        pocProvesBug = True
        pocFailsAfterPatch = True
        hiddenTestsPass = True
        patchWithinLimits = True
        log = "ok"
        submissionHash = "0x" + "cd" * 32

    def fake_render(mother, seed, out):
        out = Path(out)
        (out / "src").mkdir(parents=True)
        (out / "src" / "Vault.sol").write_text(SOURCE)
        (out / "challenge.json").write_text(json.dumps({
            "challengeId": f"{mother}-{seed}", "targetFile": "Vault.sol", "contractName": "Vault",
            "vulnClass": 0, "requiredFunctions": ["withdraw"], "pragma": "0.8.28",
            "limits": {"maxChangedLines": 12, "maxBytes": 6000}, "hiddenTests": "Hidden.t.sol",
        }))

    monkeypatch.setattr("axvigil_agent.__main__.MetaModelClient", Stub)
    monkeypatch.setattr("axvigil_agent.solver._grade", lambda *a, **k: Grade())
    monkeypatch.setattr("axvigil_agent.arena.render_mother", fake_render)
    out = tmp_path / "arena_results.json"
    code = main([
        "arena", "--contestant", "muse-spark-1.1:agentic",
        "--mothers", "reentrancy", "--seeds", "1",
        "--max-steps", "2", "--request-cap", "4",
        "--tool-protocol", "json", "--out", str(out),
    ])
    assert code == 0
    data = json.loads(out.read_text())
    assert data["runs"][0]["pass"] is True
    assert data["runs"][0]["evidence"]["protocol"] == "json"
    assert "cli-test-key-not-logged" not in out.read_text()
    assert Stub.kwargs["temperature"] == 0
