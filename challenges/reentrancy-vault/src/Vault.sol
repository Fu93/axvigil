// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title Vault
/// @notice A minimal ether vault: anyone can deposit and later withdraw their own balance.
/// @dev AxVigil challenge target (sandbox, BSC testnet only). The reference version is
///      deliberately vulnerable for an AI agent to find and fix. Do not deploy to mainnet.
contract Vault {
    mapping(address => uint256) public balanceOf;

    event Deposit(address indexed who, uint256 amount);
    event Withdraw(address indexed who, uint256 amount);

    /// @notice Deposit ether into your vault balance.
    function deposit() external payable {
        balanceOf[msg.sender] += msg.value;
        emit Deposit(msg.sender, msg.value);
    }

    /// @notice Withdraw your entire vault balance.
    function withdraw() external {
        uint256 amount = balanceOf[msg.sender];
        require(amount > 0, "nothing to withdraw");

        // VULNERABLE: external call happens before the balance is cleared, so a
        // contract recipient can re-enter withdraw() and be paid again.
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "transfer failed");

        balanceOf[msg.sender] = 0;
        emit Withdraw(msg.sender, amount);
    }

    /// @notice Total ether held by the vault.
    function totalAssets() external view returns (uint256) {
        return address(this).balance;
    }
}
