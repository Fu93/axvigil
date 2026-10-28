// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

contract VaultHiddenTest is Test {
    Vault internal vault;
    address internal user = address(0xBEEF);

    function setUp() public {
        vault = new Vault();
        vm.deal(user, 10 ether);
    }

    function testWithdrawAllClearsBalance() public {
        vm.prank(user);
        vault.deposit{value: 1 ether}();

        vm.prank(user);
        vault.withdrawAll();

        assertEq(vault.balances(user), 0);
    }

    function testCannotWithdrawWithoutBalance() public {
        vm.prank(user);
        vm.expectRevert("no balance");
        vault.withdrawAll();
    }
}
