"""Docker sandbox argv is locked down. The image run is skipped when Docker is absent."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from axvigil_verifier.forge_runner import (
    DEFAULT_FORGE_STD,
    DEFAULT_OZ,
    _sandbox_mode,
    docker_run_command,
)


def test_default_sandbox_is_the_subprocess_runner(monkeypatch):
    monkeypatch.delenv("AXVIGIL_SANDBOX", raising=False)
    assert _sandbox_mode() == "subprocess"


def test_docker_command_has_no_network_and_a_read_only_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AXVIGIL_DOCKER_IMAGE", "axvigil-sandbox:1.8.7")
    cmd = docker_run_command(tmp_path, "test/Poc.t.sol", 7)
    assert cmd[0] == "docker"
    assert cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd
    assert cmd[cmd.index("--user") + 1] == "1000:1000"
    assert any(part.startswith("/work:rw") for part in cmd)
    assert f"{tmp_path}:/inputs:ro" in cmd
    assert f"{DEFAULT_FORGE_STD}:{DEFAULT_FORGE_STD}:ro" in cmd
    assert f"{DEFAULT_OZ}:{DEFAULT_OZ}:ro" in cmd
    assert "FOUNDRY_OFFLINE=true" in cmd


def test_unknown_sandbox_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("AXVIGIL_SANDBOX", "kvm")
    with pytest.raises(ValueError):
        _sandbox_mode()


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not installed")
def test_pinned_image_is_present_or_documented():
    """CI builds the image; local runs verify it when it is available."""
    import subprocess
    probe = subprocess.run(
        ["docker", "image", "inspect", "axvigil-sandbox:1.8.7"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        pytest.skip("image axvigil-sandbox:1.8.7 is not built; see verifier/docker/Dockerfile")
    assert (Path(__file__).resolve().parents[1] / "docker" / "Dockerfile").is_file()
