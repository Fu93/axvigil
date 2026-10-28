// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";

/// @title MockAgentID
/// @notice Stand-in for the SPACE ID .ai Agent ID registry on testnet and in tests.
///         Exposes the same `ownerOf(uint256)` interface. Anyone can mint (test-only!).
contract MockAgentID is ERC721 {
    uint256 public nextId = 1;

    constructor() ERC721("Mock Agent ID", "mAGENT") {}

    /// @notice Mint the next Agent ID to `to`. Open to anyone; never deploy to mainnet.
    function mint(address to) external returns (uint256 id) {
        id = nextId++;
        _mint(to, id);
    }

    /// @notice Mint a specific Agent ID (handy for mirroring real IDs in demos).
    function mintId(address to, uint256 id) external {
        _mint(to, id);
    }
}
