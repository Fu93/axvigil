// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

/// @notice Hidden functional tests. A valid patch must keep ALL of these passing:
///         the fix may not break honest deposit/withdraw behaviour or accounting.
contract HiddenTest is Test {
    Vault internal vault;
    address internal alice = makeAddr("alice");
    address internal bob = makeAddr("bob");

    function setUp() public {
        vault = new Vault();
        vm.deal(alice, 10 ether);
        vm.deal(bob, 10 ether);
    }

    function test_depositCreditsBalance() public {
        vm.prank(alice);
        vault.deposit{value: 3 ether}();
        assertEq(vault.balanceOf(alice), 3 ether);
        assertEq(vault.totalAssets(), 3 ether);
    }

    function test_withdrawReturnsFundsAndZeroes() public {
        vm.prank(alice);
        vault.deposit{value: 4 ether}();

        uint256 before = alice.balance;
        vm.prank(alice);
        vault.withdraw();

        assertEq(alice.balance, before + 4 ether, "funds returned");
        assertEq(vault.balanceOf(alice), 0, "balance zeroed");
        assertEq(vault.totalAssets(), 0);
    }

    function test_withdrawRevertsWithNothing() public {
        vm.prank(bob);
        vm.expectRevert(bytes("nothing to withdraw"));
        vault.withdraw();
    }

    function test_balancesAreIndependent() public {
        vm.prank(alice);
        vault.deposit{value: 2 ether}();
        vm.prank(bob);
        vault.deposit{value: 5 ether}();

        assertEq(vault.balanceOf(alice), 2 ether);
        assertEq(vault.balanceOf(bob), 5 ether);

        vm.prank(alice);
        vault.withdraw();

        // Bob's funds are untouched by Alice's withdrawal.
        assertEq(vault.balanceOf(bob), 5 ether);
        assertEq(vault.totalAssets(), 5 ether);
    }

    function test_redepositAfterWithdraw() public {
        vm.startPrank(alice);
        vault.deposit{value: 1 ether}();
        vault.withdraw();
        vault.deposit{value: 2 ether}();
        vm.stopPrank();
        assertEq(vault.balanceOf(alice), 2 ether);
    }
}
