// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Minimal view of the SPACE ID .ai Agent ID registry (ERC-721-like).
/// BSC mainnet: 0x60B9262456dE011F7d15a54CdD8c48bAaa8B022F. On testnet we use MockAgentID.
interface IAgentRegistry {
    function ownerOf(uint256 tokenId) external view returns (address);
}
