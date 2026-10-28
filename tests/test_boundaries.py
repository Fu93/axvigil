import json
import subprocess
from pathlib import Path
import pytest
from verifier.runner import SandboxUnavailable, run
from agent.solve import model_solve


def test_docker_boundary_and_unavailable_fail_closed(monkeypatch):
    commands = []

    def execute(command, **kwargs):
        commands.append(command)
        if command[1] == "run":
            mount = command[command.index("--mount") + 1]
            folder = Path(mount.split("src=")[1].split(",")[0])
            assert folder.stat().st_mode & 0o005 == 0o005
            assert json.loads((folder / "submission.json").read_text()) == {
                "patch": "untrusted"
            }
            raise FileNotFoundError("No docker")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(SandboxUnavailable):
        run({"patch": "untrusted"})
    cmd = commands[0]
    for flag in [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65532:65532",
    ]:
        assert flag in cmd
    assert "--env" not in cmd and "-e" not in cmd
    assert commands[-1][1:3] == ["rm", "-f"]


def test_model_adapter_schema_and_no_endpoint_guessing(monkeypatch):
    monkeypatch.setenv("MUSE_CHAT_COMPLETIONS_URL", "https://example.invalid/chat")
    monkeypatch.setenv("MUSE_MODEL", "operator-configured-model")
    monkeypatch.setenv("MUSE_API_KEY", "not-a-real-key")

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {"message": {"content": '{"patch":"source","poc":"attack"}'}}
                ]
            }

    def post(url, **kwargs):
        assert url == "https://example.invalid/chat"
        assert kwargs["json"]["model"] == "operator-configured-model"
        return Response()

    monkeypatch.setattr("agent.solve.httpx.post", post)
    assert model_solve("contract", "repair") == {"patch": "source", "poc": "attack"}
    monkeypatch.setenv("MUSE_CHAT_COMPLETIONS_URL", "http://example.invalid/chat")
    with pytest.raises(ValueError):
        model_solve("contract", "repair")
