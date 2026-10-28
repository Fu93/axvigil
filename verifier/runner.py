"""Host boundary: production never executes participant code without Docker."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


class SandboxUnavailable(RuntimeError):
    pass


def run(payload):
    name = "axvigil-grade-" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="axvigil-input-") as temp:
        os.chmod(temp, 0o755)
        path = Path(temp) / "submission.json"
        path.write_text(json.dumps(payload))
        path.chmod(0o644)
        # No host environment, docker socket, secrets, RPC credentials, or writable host mount.
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network=none",
            "--read-only",
            "--cpus=1",
            "--memory=768m",
            "--memory-swap=768m",
            "--pids-limit=96",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=65532:65532",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=384m,mode=1777",
            "--mount",
            f"type=bind,src={temp},dst=/input,readonly",
            os.getenv("GRADER_IMAGE", "axvigil-grader:local"),
            "/input/submission.json",
        ]
        try:
            p = subprocess.run(
                command, capture_output=True, text=True, timeout=150, check=True
            )
            result = json.loads(p.stdout)
            if not isinstance(result, dict):
                raise ValueError("Invalid worker result")
            return result
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise SandboxUnavailable(
                "Isolated grader unavailable or timed out"
            ) from exc
        finally:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", name], capture_output=True, timeout=5
                )
            except (OSError, subprocess.SubprocessError):
                pass
