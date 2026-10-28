// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The hook AxVigilCollectible uses to update an agent's skill record.
interface IAxVigilSkill {
    function recordSolve(uint256 agentId, uint8 vulnClass, uint8 difficulty) external;
}
