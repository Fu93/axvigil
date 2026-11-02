// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice The hook AxVigilCollectible uses to update an agent's skill record.
///         `confirmSolve` / `revokeSolve` are called by the collectible (immediate finality)
///         or by the challenge book (after the optimistic window).
interface IAxVigilSkill {
    function recordSolve(uint256 agentId, uint8 vulnClass, uint8 difficulty) external;

    function confirmSolve(uint256 agentId, uint8 vulnClass) external;

    function revokeSolve(uint256 agentId, uint8 vulnClass) external;
}
