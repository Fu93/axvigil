"""The grader runs untrusted submitted Solidity, so prove the sandbox actually
denies the dangerous cheatcodes. Skips if forge/solc are unavailable."""

from __future__ import annotations

import os
import shutil

import pytest

from axvigil_verifier.forge_runner import run_test
from axvigil_verifier.toolchain import discover_solc, forge_executable

_forge = forge_executable()
_solc = discover_solc()


@pytest.fixture(scope="session", autouse=True)
def _require_forge():
    if not _forge:
        pytest.fail("forge is required. Install foundry; solc is discovered from svm if needed.")

_HEADER = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;
import {Test} from "forge-std/Test.sol";
"""


def _run(test_body: str):
    return run_test(
        sources={}, tests={"S.t.sol": _HEADER + test_body},
        match_path="test/S.t.sol", forge_bin=_forge, solc=_solc, timeout_s=60,
    )


def test_ffi_is_disabled():
    # vm.ffi must be refused (ffi = false), so the test cannot pass.
    r = _run("""contract S is Test {
        function test_ffi() public {
            string[] memory cmd = new string[](2);
            cmd[0] = "echo"; cmd[1] = "pwned";
            vm.ffi(cmd);
        }
    }""")
    assert not r.all_passed, "ffi must be disabled in the sandbox"


def test_filesystem_read_is_blocked():
    # fs_permissions is empty, so reading host files must be refused.
    r = _run("""contract S is Test {
        function test_fs() public view {
            vm.readFile("/etc/hostname");
        }
    }""")
    assert not r.all_passed, "filesystem reads must be blocked in the sandbox"


def test_a_plain_passing_test_still_runs():
    # Control: a harmless test still passes, so the limits don't block normal use.
    r = _run("""contract S is Test {
        function test_ok() public pure { assertEq(uint256(2 + 2), 4); }
    }""")
    assert r.all_passed
