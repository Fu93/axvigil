"""End-to-end grader tests, including adversarial submissions that must be rejected.

Requires `forge` and a Solidity compiler on PATH (or FORGE/SOLC env vars). Skips
cleanly if they are absent, so `pytest` is safe to run anywhere.
"""

from __future__ import annotations

import shutil
import os
from pathlib import Path

import pytest

from axvigil_verifier.grader import HIDDEN_FAIL_HINT, check_patch_cheatcodes, check_poc_decoy_probes, grade
from axvigil_verifier.keccak import submission_hash
from axvigil_verifier.toolchain import discover_solc, forge_executable

CHALLENGES = Path(__file__).resolve().parents[2] / "challenges"
CH = CHALLENGES / "reentrancy-vault"

_forge = forge_executable()
_solc = discover_solc()


@pytest.fixture(scope="session", autouse=True)
def _require_forge():
    if not _forge:
        pytest.fail(
            "forge is required. Install foundry. These tests no longer skip when "
            "solc is only available via Foundry's svm cache."
        )


def _grade(submission: Path):
    return grade(CH, submission, forge_bin=_forge, solc=_solc, timeout_s=120)


def _write_submission(tmp: Path, patched_vault: str, poc: str) -> Path:
    (tmp / "patched").mkdir(parents=True)
    (tmp / "poc").mkdir(parents=True)
    (tmp / "patched" / "Vault.sol").write_text(patched_vault)
    (tmp / "poc" / "Poc.t.sol").write_text(poc)
    return tmp


VULN = (CH / "src" / "Vault.sol").read_text()
FIX = (CH / "solution" / "patched" / "Vault.sol").read_text()
GOOD_POC = (CH / "solution" / "poc" / "Poc.t.sol").read_text()

NOOP_POC = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;
import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";
contract PocTest is Test {
    function test_noop() public pure { assertTrue(true); }
}
"""

GUTTED = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;
contract Vault {
    mapping(address => uint256) public balanceOf;
    function deposit() external payable { balanceOf[msg.sender] += msg.value; }
    function totalAssets() external view returns (uint256) { return address(this).balance; }
}
"""


def test_reference_solution_passes():
    res = _grade(CH / "solution")
    assert res.passed, res.log
    assert res.pocProvesBug and res.pocFailsAfterPatch and res.hiddenTestsPass and res.patchWithinLimits
    # The static vault has no invariant suite. The fifth check is recorded and
    # does not change the verdict.
    assert res.invariantsHold is True
    assert res.invariantApplied is False
    assert "invariantsHold: not configured" in res.log
    hidden = (CH / "test" / "Hidden.t.sol").read_text()
    # Names of the hidden tests must not be echoed into the log the agent retries on.
    for line in hidden.splitlines():
        line = line.strip()
        if line.startswith("function test_"):
            name = line.split("(")[0].removeprefix("function ")
            assert name not in res.log
            assert name + "()" not in res.log
    # Hash is reproducible and matches a standalone computation.
    expected = "0x" + submission_hash("reentrancy-vault", 0, FIX, GOOD_POC).hex()
    assert res.submissionHash == expected


def test_fake_fix_rejected(tmp_path):
    # "Patch" is identical to the vulnerable contract: the PoC still drains it.
    sub = _write_submission(tmp_path, VULN, GOOD_POC)
    res = _grade(sub)
    assert not res.passed
    assert res.pocProvesBug is True
    assert res.pocFailsAfterPatch is False, res.log


def test_gutted_contract_rejected(tmp_path):
    # Deleting withdraw() trivially stops the PoC but destroys the interface.
    sub = _write_submission(tmp_path, GUTTED, GOOD_POC)
    res = _grade(sub)
    assert not res.passed
    assert res.patchWithinLimits is False, res.log


def test_noop_poc_rejected(tmp_path):
    # A real fix but a PoC that never demonstrates the bug. A trivial always-pass
    # test passes on the original too (pocProvesBug=True), so the differential is
    # what rejects it: it also passes on the patched contract, hence it never
    # "fails after patch". Credit requires pass-on-vulnerable AND fail-on-patched.
    sub = _write_submission(tmp_path, FIX, NOOP_POC)
    res = _grade(sub)
    assert not res.passed
    assert res.pocFailsAfterPatch is False, res.log


DECOY_POC = r"""// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;
import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

contract Attacker {
    Vault public vault;
    constructor(Vault v) { vault = v; }
    function attack() external payable {
        vault.deposit{value: msg.value}();
        vault.withdraw();
    }
    receive() external payable {
        if (address(vault).balance >= 1 ether) {
            (bool ignored,) = address(vault).call(abi.encodeWithSignature("withdraw()"));
            ignored;
        }
    }
}

contract PocTest is Test {
    function test_exploitStillWorks() public {
        Vault vault = new Vault();
        address victim = makeAddr("victim");
        vm.deal(victim, 5 ether);
        vm.prank(victim);
        vault.deposit{value: 5 ether}();
        Attacker attacker = new Attacker(vault);
        vm.deal(address(this), 1 ether);
        attacker.attack{value: 1 ether}();
        assertEq(vault.totalAssets(), 0, "drained");
    }
    function test_decoyBeefCanWithdraw() public {
        Vault vault = new Vault();
        address beef = address(0xBEEF);
        vm.deal(beef, 1 ether);
        vm.prank(beef);
        vault.deposit{value: 1 ether}();
        vm.prank(beef);
        vault.withdraw();
        assertEq(vault.balanceOf(beef), 0);
    }
}
"""

# Does not fix reentrancy. Breaks only the decoy (0xBEEF). Hidden tests use other addresses.
PARTIAL = VULN.replace(
    'require(amount > 0, "nothing to withdraw");',
    'require(amount > 0, "nothing to withdraw");\n        require(msg.sender != address(0xBEEF), "blocked");',
)


def test_hidden_failure_hints_without_naming_tests(tmp_path):
    # Credits only half the deposit. The contract still compiles and the public
    # functions remain, but honest accounting in the hidden tests no longer holds.
    patched = VULN.replace(
        "balanceOf[msg.sender] += msg.value;",
        "balanceOf[msg.sender] += msg.value / 2;",
    )
    sub = _write_submission(tmp_path, patched, GOOD_POC)
    res = _grade(sub)
    assert res.hiddenTestsPass is False, res.log
    assert HIDDEN_FAIL_HINT in res.log
    assert "keep the fix minimal" not in res.log
    assert "code.length" not in HIDDEN_FAIL_HINT
    assert "address(0)" not in HIDDEN_FAIL_HINT
    hidden = (CH / "test" / "Hidden.t.sol").read_text()
    for line in hidden.splitlines():
        stripped = line.strip()
        if stripped.startswith("function test_"):
            name = stripped.split("(")[0].removeprefix("function ")
            assert name not in res.log
            assert name + "()" not in res.log


def test_decoy_test_cannot_hide_a_live_exploit(tmp_path):
    sub = _write_submission(tmp_path, PARTIAL, DECOY_POC)
    res = _grade(sub)
    assert res.pocProvesBug is True, res.log
    assert res.pocFailsAfterPatch is False, res.log
    assert res.passed is False


def test_hash_is_whitespace_canonical():
    a = submission_hash("c", 1, "contract C{}\n", "contract T{}\n")
    b = submission_hash("c", 1, "contract C{}  \n\n", "contract T{}\r\n")
    assert a == b  # trailing whitespace / CRLF / blank tail don't change the hash
    c = submission_hash("c", 1, "contract D{}\n", "contract T{}\n")
    assert a != c  # real content change does


def test_decoy_poc_bytecode_introspection_rejected(tmp_path):
    decoy_code_length_poc = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;
import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";
contract PocTest is Test {
    function test_probeBytecode() public {
        Vault vault = new Vault();
        assertTrue(address(vault).code.length > 0);
    }
}
"""
    sub = _write_submission(tmp_path, FIX, decoy_code_length_poc)
    res = _grade(sub)
    assert res.pocProvesBug is False
    assert "Decoy PoC rejected" in res.log
    assert res.passed is False


def test_dynamic_storage_layout_shift_rejected(tmp_path):
    # Shift storage layout by inserting a state variable before balanceOf
    corrupted_vault = VULN.replace(
        "contract Vault {",
        "contract Vault {\n    uint256 public insertedSlot0;",
    )
    sub = _write_submission(tmp_path, corrupted_vault, GOOD_POC)
    res = _grade(sub)
    assert res.patchWithinLimits is False
    assert "storage=CORRUPTED" in res.log
    assert res.passed is False


def test_check_poc_decoy_probes_patterns():
    ok, _ = check_poc_decoy_probes("contract T { function test_ok() public {} }")
    assert ok is True

    # Valid code with string containing slashes or struct field .code should NOT be rejected
    valid_with_strings, _ = check_poc_decoy_probes('contract T { string s = "// not a comment"; uint256 c = err.code; }')
    assert valid_with_strings is True

    bad_samples = [
        "address(target).code.length",
        "assembly { let sz := extcodesize(target) }",
        "bytes32 h = address(target).codehash;",
        "assembly { let h := extcodehash(target) }",
        "bytes memory b = type(Vault).runtimeCode;",
        "bytes memory b = type(Vault).creationCode;",
        "assembly { extcodecopy(target, 0, 0, 32) }",
        "bytes memory c = vm.getCode('Vault.sol:Vault');",
        "bytes memory d = vm.getDeployedCode('Vault.sol:Vault');",
    ]
    for sample in bad_samples:
        detected, reason = check_poc_decoy_probes(sample)
        assert detected is False, f"Failed to detect: {sample}"
        assert "Decoy PoC rejected" in reason


def test_check_patch_cheatcodes_patterns():
    ok, _ = check_patch_cheatcodes({"Vault.sol": "contract Vault { uint256 a; }"})
    assert ok is True

    bad = [
        'import "forge-std/Vm.sol";',
        'address constant V = 0x7109709ECfa91a80626fF3989D68f67F5b1DD12D;',
        'vm.warp(100);',
        'vm.prank(msg.sender);',
    ]
    for sample in bad:
        detected, reason = check_patch_cheatcodes({"Vault.sol": f"contract Vault {{ {sample} }}"})
        assert detected is False, f"Failed to reject cheatcode: {sample}"
        assert "Illegal patch rejected" in reason
