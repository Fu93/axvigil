"""Offline arena tests. No network and no forge: a fake model client and a fake grader."""

from __future__ import annotations

import json
from pathlib import Path

from axvigil_agent.arena import (
    SCHEMA_VERSION,
    ClientStop,
    Contestant,
    FakeModelClient,
    ensemble_contestant,
    parse_contestant_spec,
    rank_contestants,
    render_mother,
    run_arena,
)
from axvigil_agent.model import MetaModelClient, usage_from_response
from axvigil_agent.solver import solve
from axvigil_agent.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "contract Vault {\n    function withdraw() external {}\n}\n"
FIXED = SOURCE + "// FIXED\n"


def _submission(patch: str) -> str:
    return json.dumps({
        "analysis": "offline",
        "patched_contract": patch,
        "poc_test": "contract Poc {}",
    })


class _Grade:
    def __init__(self, passed: bool):
        self.passed = passed
        self.pocProvesBug = True
        self.pocFailsAfterPatch = passed
        self.hiddenTestsPass = passed
        self.patchWithinLimits = True
        self.log = "ok" if passed else "still exploitable"
        self.submissionHash = "0x" + "ab" * 32

    def to_json(self) -> dict:
        return {"passed": self.passed, "submissionHash": self.submissionHash}


def _grade(challenge_dir, target_file, patch, poc, seed, forge_bin, solc, timeout_s):
    return _Grade("FIXED" in patch)


def _render(mother: str, seed: int, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "src").mkdir(exist_ok=True)
    (out / "src" / "Vault.sol").write_text(SOURCE)
    meta = {
        "challengeId": f"{mother}-{seed}",
        "targetFile": "Vault.sol",
        "contractName": "Vault",
        "vulnClass": 0,
        "difficulty": 0,
        "requiredFunctions": ["withdraw"],
        "pragma": "0.8.28",
        "limits": {"maxChangedLines": 12, "maxBytes": 6000},
        "hiddenTests": "Hidden.t.sol",
    }
    (out / "challenge.json").write_text(json.dumps(meta))
    return meta


def _cell(cid, *, pass_=False, attempts=1, prompt=10, completion=1, mother="reentrancy",
          seed=1, status="completed", strategy="baseline"):
    return {
        "runId": f"{cid}|{mother}|{seed}",
        "contestantId": cid,
        "model": cid,
        "strategy": strategy,
        "mother": mother,
        "seed": seed,
        "status": status,
        "pass": pass_,
        "attempts": attempts,
        "requests": attempts,
        "tokens": {"prompt": prompt, "completion": completion},
        "latencyMs": 1,
        "failedChecks": [] if pass_ else ["pocFailsAfterPatch"],
        "patchDiffLines": 1 if pass_ else 0,
    }


def test_rank_by_pass_rate_then_attempts_then_tokens():
    runs = [
        _cell("slow", pass_=True, attempts=2, prompt=10, completion=5, mother="reentrancy"),
        _cell("slow", pass_=True, attempts=2, prompt=10, completion=5, mother="access-control"),
        _cell("fast", pass_=True, attempts=1, prompt=10, completion=1, mother="reentrancy"),
        _cell("fast", pass_=True, attempts=1, prompt=10, completion=1, mother="access-control"),
        _cell("weak", pass_=False, attempts=2, prompt=10, completion=1, mother="reentrancy"),
        _cell("weak", pass_=True, attempts=2, prompt=10, completion=1, mother="access-control"),
        _cell("cheap", pass_=True, attempts=1, prompt=1, completion=1),
        _cell("pricey", pass_=True, attempts=1, prompt=8, completion=8),
        # A capped run is not a finished sample and must not change `fast`.
        _cell("fast", pass_=False, attempts=9, prompt=100, completion=100,
              mother="price-manipulation", status="budget"),
    ]
    ranking = rank_contestants(runs)
    assert [row["contestantId"] for row in ranking] == ["cheap", "pricey", "fast", "slow", "weak"]
    fast = ranking[2]
    assert fast["passes"] == 2 and fast["runs"] == 2 and fast["attempts"] == 2
    assert fast["passRate"] == 1
    assert fast["tokens"] == {"prompt": 20, "completion": 2, "total": 22}
    assert fast["byMother"]["reentrancy"]["passes"] == 1
    assert fast["byMother"]["price-manipulation"]["passes"] == 0
    weak = ranking[4]
    assert weak["passes"] == 1 and weak["runs"] == 2 and weak["passRate"] == 0.5


def test_solve_stops_on_client_stop_without_grading(tmp_path):
    challenge = tmp_path / "chal"
    _render("reentrancy", 1, challenge)

    def boom(*_a, **_k):
        raise AssertionError("grader should not run after the request cap")

    class Stop:
        def complete(self, system, user):
            raise ClientStop("request_cap")

    outcome = solve(Stop(), challenge, max_iters=4, grader=boom)
    assert outcome.stopped == "request_cap"
    assert outcome.solved is False
    assert outcome.iterations == []


def test_run_records_verifier_fields(tmp_path):
    def factory(_model):
        return FakeModelClient([_submission(SOURCE), _submission(FIXED)], usage=(12, 6))

    out = tmp_path / "arena_results.json"
    result = run_arena(
        [parse_contestant_spec("muse-spark-1.1")],
        ["reentrancy"],
        [1],
        out_path=out,
        request_cap=10,
        max_iters=3,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    assert result["schemaVersion"] == SCHEMA_VERSION == 1
    run = result["runs"][0]
    assert run["pass"] is True
    assert run["attempts"] == 2
    assert run["requests"] == 2
    assert run["tokens"] == {"prompt": 24, "completion": 12}
    assert isinstance(run["latencyMs"], int) and run["latencyMs"] >= 0
    assert run["failedChecks"] == []
    assert run["patchDiffLines"] == 1
    assert run["status"] == "completed"
    assert run["challengeId"] == "reentrancy-1"
    assert "pass" in result["schema"]["run"]
    summary = (tmp_path / "arena_results.md").read_text()
    assert "muse-spark-1.1" in summary
    assert "Powered by Meta Muse Spark" in summary
    text = out.read_text()
    assert "schemaVersion" in text


def test_failed_checks_come_from_the_last_graded_attempt(tmp_path):
    def factory(_model):
        return FakeModelClient([_submission(SOURCE)], usage=(1, 1))

    result = run_arena(
        [Contestant(id="base", strategy="baseline", model="base")],
        ["reentrancy"],
        [4],
        out_path=tmp_path / "out.json",
        request_cap=5,
        max_iters=1,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    run = result["runs"][0]
    assert run["pass"] is False
    assert run["failedChecks"] == ["pocFailsAfterPatch", "hiddenTestsPass"]
    assert run["patchDiffLines"] == 0
    assert run["attempts"] == 1


def test_self_critique_submits_the_reviewed_patch(tmp_path):
    def factory(_model):
        def handle(_system, user, idx):
            if idx == 0:
                return _submission(SOURCE)
            assert "review" in user.lower()
            assert SOURCE.strip() in user
            return _submission(FIXED)

        return FakeModelClient(handle, usage=(4, 3))

    result = run_arena(
        [parse_contestant_spec("muse-spark-1.2:self-critique")],
        ["access-control"],
        [2],
        out_path=tmp_path / "out.json",
        request_cap=8,
        max_iters=1,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    run = result["runs"][0]
    assert run["strategy"] == "self-critique"
    assert run["pass"] is True
    assert run["attempts"] == 1
    assert run["requests"] == 2
    assert run["patchDiffLines"] == 1
    assert run["tokens"]["prompt"] == 8


def test_plan_then_patch_includes_the_plan(tmp_path):
    def factory(_model):
        def handle(_system, user, idx):
            if idx == 0:
                assert "plan only" in user.lower()
                return "DO-THIS-PLAN"
            assert "DO-THIS-PLAN" in user
            return _submission(FIXED)

        return FakeModelClient(handle, usage=(2, 2))

    result = run_arena(
        [parse_contestant_spec("muse-spark-1.3:plan-then-patch:planner")],
        ["signature-replay"],
        [0],
        out_path=tmp_path / "out.json",
        request_cap=8,
        max_iters=1,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    run = result["runs"][0]
    assert run["contestantId"] == "planner"
    assert run["pass"] is True
    assert run["attempts"] == 1
    assert run["requests"] == 2


def test_ensemble_picks_the_first_passing_model(tmp_path):
    seen: list[str] = []

    def factory(model):
        seen.append(model)

        def handle(_system, _user, _idx, model=model):
            patch = FIXED if model == "good" else SOURCE
            return _submission(patch)

        return FakeModelClient(handle, usage=(3, 1))

    result = run_arena(
        [ensemble_contestant(["bad", "good", "later"], id="orch")],
        ["reentrancy"],
        [1],
        out_path=tmp_path / "out.json",
        request_cap=10,
        max_iters=1,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    run = result["runs"][0]
    assert seen == ["bad", "good"]
    assert run["pass"] is True
    assert run["attempts"] == 2
    assert run["requests"] == 2
    assert run["ensembleWinner"] == "good"
    assert run["models"] == ["bad", "good", "later"]
    assert run["tokens"] == {"prompt": 6, "completion": 2}
    assert run["failedChecks"] == []


def test_request_cap_and_resume_skips_completed(tmp_path):
    calls = {"n": 0}

    def factory(_model):
        def handle(_system, _user, _idx):
            calls["n"] += 1
            return _submission(FIXED)

        return FakeModelClient(handle, usage=(1, 1))

    contestants = [parse_contestant_spec("muse-spark-1.1")]
    mothers = ["reentrancy", "price-manipulation"]
    out = tmp_path / "arena_results.json"
    first = run_arena(
        contestants, mothers, [1],
        out_path=out, request_cap=1, max_iters=2, client_factory=factory,
        grader=_grade, render_fn=_render,
    )
    assert first["budget"]["requestsUsed"] == 1
    assert calls["n"] == 1
    assert [r["status"] for r in first["runs"]] == ["completed"]
    assert first["runs"][0]["mother"] == "reentrancy"

    second = run_arena(
        contestants, mothers, [1],
        out_path=out, request_cap=5, max_iters=2, client_factory=factory,
        grader=_grade, render_fn=_render, resume=True,
    )
    assert calls["n"] == 2  # the completed mother was not asked again
    assert second["budget"]["requestsUsed"] == 1
    assert [(r["mother"], r["status"], r["pass"]) for r in second["runs"]] == [
        ("reentrancy", "completed", True),
        ("price-manipulation", "completed", True),
    ]

    third = run_arena(
        contestants, mothers, [1],
        out_path=out, request_cap=5, max_iters=2, client_factory=factory,
        grader=_grade, render_fn=_render, resume=False,
    )
    assert calls["n"] == 4
    assert third["budget"]["requestsUsed"] == 2


def test_cap_stops_between_graded_attempts(tmp_path):
    def factory(_model):
        return FakeModelClient([_submission(SOURCE)], usage=(1, 1))

    result = run_arena(
        [parse_contestant_spec("muse-spark-1.1")],
        ["reentrancy", "access-control"],
        [1],
        out_path=tmp_path / "out.json",
        request_cap=3,
        max_iters=2,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    assert result["budget"]["requestsUsed"] == 3
    assert sum(r["requests"] for r in result["runs"]) == 3
    first, second = result["runs"]
    assert first["status"] == "completed" and first["attempts"] == 2 and first["pass"] is False
    assert second["status"] == "budget" and second["attempts"] == 1 and second["pass"] is False


def test_concurrency_matches_serial_and_never_exceeds_the_cap(tmp_path):
    def factory(model):
        patch = FIXED if model == "pass" else SOURCE
        return FakeModelClient([_submission(patch)], usage=(2, 2))

    contestants = [
        parse_contestant_spec("pass"),
        parse_contestant_spec("fail"),
    ]
    mothers = ["reentrancy", "price-manipulation", "access-control"]
    common = dict(
        request_cap=100, max_iters=1, client_factory=factory, grader=_grade, render_fn=_render,
    )
    serial = run_arena(contestants, mothers, [1], out_path=tmp_path / "s.json", concurrency=1, **common)
    parallel = run_arena(
        contestants, mothers, [1], out_path=tmp_path / "p.json", concurrency=3, resume=False, **common,
    )

    def slim(doc):
        return [(r["runId"], r["pass"], r["attempts"], r["tokens"]) for r in doc["runs"]]

    assert slim(serial) == slim(parallel)
    assert [r["runId"] for r in serial["runs"]] == [
        "pass|reentrancy|1",
        "pass|price-manipulation|1",
        "pass|access-control|1",
        "fail|reentrancy|1",
        "fail|price-manipulation|1",
        "fail|access-control|1",
    ]

    capped = run_arena(
        contestants, mothers, [1, 2],
        out_path=tmp_path / "c.json",
        request_cap=5,
        max_iters=2,
        concurrency=4,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
    )
    assert capped["budget"]["requestsUsed"] <= 5
    assert sum(r["requests"] for r in capped["runs"]) <= 5


def test_errors_redact_the_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "super-secret-key-zz")
    events: list[str] = []

    def factory(_model):
        class Boom:
            last_usage = {"prompt": 0, "completion": 0}

            def complete(self, system, user):
                raise RuntimeError("upstream rejected super-secret-key-zz")

        return Boom()

    out = tmp_path / "arena_results.json"
    result = run_arena(
        [parse_contestant_spec("muse-spark-1.1")],
        ["reentrancy"],
        [1],
        out_path=out,
        request_cap=4,
        max_iters=1,
        client_factory=factory,
        grader=_grade,
        render_fn=_render,
        on_event=events.append,
    )
    blob = out.read_text() + "\n" + (tmp_path / "arena_results.md").read_text() + "\n" + "\n".join(events)
    assert "super-secret-key-zz" not in blob
    assert result["runs"][0]["status"] == "error"
    assert "redacted" in result["runs"][0]["error"]


def test_render_mother_is_deterministic(tmp_path):
    first = render_mother("reentrancy", 3, tmp_path / "a")
    second = render_mother("reentrancy", 3, tmp_path / "b")
    src_a = next((first / "src").glob("*.sol")).read_text()
    src_b = next((second / "src").glob("*.sol")).read_text()
    assert src_a == src_b
    meta = json.loads((first / "challenge.json").read_text())
    assert meta["challengeId"] == "reentrancy-3"
    assert meta["motherId"] == "reentrancy"


def test_cli_arena_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "cli-test-key-not-logged")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    seen: list[dict] = []

    class Stub:
        def __init__(self, **kwargs):
            self.last_usage = {"prompt": 2, "completion": 1}
            seen.append(kwargs)

        def complete(self, system, user):
            return _submission(FIXED)

    monkeypatch.setattr("axvigil_agent.__main__.MetaModelClient", Stub)
    monkeypatch.setattr("axvigil_agent.solver._grade", _grade)
    out = tmp_path / "arena_results.json"
    code = main([
        "arena",
        "--contestant", "muse-spark-1.1",
        "--contestant", "muse-spark-1.2:self-critique",
        "--ensemble", "muse-spark-1.1,muse-spark-1.3",
        "--mothers", "reentrancy",
        "--seeds", "1",
        "--max-iters", "1",
        "--request-cap", "8",
        "--out", str(out),
    ])
    assert code == 0
    data = json.loads(out.read_text())
    assert {r["contestantId"] for r in data["runs"]} == {
        "muse-spark-1.1", "muse-spark-1.2:self-critique", "ensemble:muse-spark-1.1+muse-spark-1.3",
    }
    assert all(r["pass"] for r in data["runs"])
    assert seen[0]["model"] == "muse-spark-1.1"
    assert seen[0]["temperature"] == 0
    assert seen[0]["timeout_s"] == 300
    assert "cli-test-key-not-logged" not in out.read_text()
    assert out.with_suffix(".md").is_file()
    assert main(["arena", "--out", str(tmp_path / "missing.json")]) == 2
    assert main(["arena", "--contestant", "muse:not-a-strategy", "--out", str(out)]) == 2


def test_readme_and_leaderboard_are_wired():
    readme = (ROOT / "README.md").read_text()
    assert "python -m axvigil_agent arena" in readme
    assert "--request-cap 60" in readme
    assert "self-critique" in readme
    assert "arena_results.json" in readme
    page = (ROOT / "web" / "leaderboard.html").read_text()
    assert "Powered by Meta Muse Spark" in page
    assert "PLACEHOLDER" in page
    assert "passRate" in page
    index = (ROOT / "web" / "index.html").read_text()
    assert 'href="leaderboard.html"' in index


def test_usage_from_response_and_client_records_it(monkeypatch):
    assert usage_from_response({"usage": {"prompt_tokens": 11, "completion_tokens": 5}}) == {
        "prompt": 11, "completion": 5,
    }
    assert usage_from_response({}) == {"prompt": 0, "completion": 0}
    monkeypatch.setenv("META_API_KEY", "super-secret-key-zz")
    monkeypatch.delenv("META_MAX_TOKENS", raising=False)

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 5},
            }).encode()

    def fake_urlopen(req, timeout):
        body = json.loads(req.data.decode())
        assert body["temperature"] == 0
        assert "max_tokens" not in body
        assert timeout == 300
        return Resp()

    monkeypatch.setattr("axvigil_agent.model.urllib.request.urlopen", fake_urlopen)
    client = MetaModelClient(temperature=0)
    assert client.complete("sys", "user") == "hello"
    assert client.last_usage == {"prompt": 11, "completion": 5}
    assert "super-secret-key-zz" not in repr(client)


def test_fake_model_client_is_local():
    client = FakeModelClient(["one", "two"], usage=(9, 8))
    assert client.complete("s", "u") == "one"
    assert client.complete("s", "u") == "two"
    assert client.complete("s", "u") == "two"
    assert client.last_usage == {"prompt": 9, "completion": 8}
    assert client.calls == 3
