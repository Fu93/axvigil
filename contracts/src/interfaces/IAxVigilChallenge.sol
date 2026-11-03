// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Optimistic challenge book called by AxVigilCollectible at the end of `mint`.
///         `status` values: 0 None, 1 Pending, 2 Challenged, 3 Final, 4 Revoked.
interface IAxVigilChallenge {
    function onMint(uint256 tokenId, uint256 agentId, uint8 vulnClass, bytes32 submissionHash, address operator)
        external
        payable;

    function status(uint256 tokenId) external view returns (uint8);

    function flagged(uint256 tokenId) external view returns (bool);
}
