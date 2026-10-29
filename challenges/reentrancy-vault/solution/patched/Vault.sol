// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title Vault
/// @notice A minimal ether vault: anyone can deposit and later withdraw their own balance.
/// @dev Reference fix: checks-effects-interactions. The balance is cleared BEFORE the
///      external call, so a reentrant withdraw() sees a zero balance and reverts.
contract Vault {
    mapping(address => uint256) public balanceOf;

    event Deposit(address indexed who, uint256 amount);
    event Withdraw(address indexed who, uint256 amount);

    function deposit() external payable {
        balanceOf[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    function withdraw() external {
        uint256 amount = balanceOf[msg.sender];
        require(amount > 0, "nothing to withdraw");

        // Effects before interactions: clear the balance first.
        balanceOf[msg.sender] = 0;

        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");

        emit Withdraw(msg.sender, amount);
    }

    function totalAssets() external view returns (uint256) {
        return address(this).balance;
    }
}
