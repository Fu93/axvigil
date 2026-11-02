"""Toolchain discovery and the UID-wide nproc cap. These do not need forge."""

from __future__ import annotations

from axvigil_verifier.forge_runner import forge_test_command
from axvigil_verifier.toolchain import (
    discover_solc,
    effective_nproc_limit,
    forge_executable,
)


def test_nproc_cap_stays_above_the_users_live_threads():
    # The old default of 256 sits under a busy uid and forge cannot spawn.
    assert effective_nproc_limit(256, live_threads=5000) == 5000 + 512
    assert effective_nproc_limit(4096, live_threads=10) == 4096
    assert effective_nproc_limit(0, live_threads=5000) is None
    assert effective_nproc_limit(-1, live_threads=10) is None


def test_missing_solc_path_lets_forge_choose_its_compiler():
    cmd = forge_test_command("forge", "test/Poc.t.sol", None, 7)
    assert "--use" not in cmd
    pinned = forge_test_command("forge", "test/Poc.t.sol", "/tmp/solc-0.8.28", 7)
    assert pinned[-2:] == ["--use", "/tmp/solc-0.8.28"]


def test_a_missing_solc_pin_is_not_forced(monkeypatch, tmp_path):
    monkeypatch.setenv("SOLC", str(tmp_path / "missing-solc"))
    # Discovery may still find svm or PATH. It must not return the missing pin.
    found = discover_solc()
    assert found != str(tmp_path / "missing-solc")


def test_discover_solc_finds_a_compiler_or_forge_can_run_without_path():
    # Either an explicit binary, or forge itself (which uses svm). Never a silent skip.
    solc = discover_solc()
    forge = forge_executable()
    assert forge or solc
    if solc:
        assert "solc" in solc
