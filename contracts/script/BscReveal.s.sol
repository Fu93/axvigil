// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @notice Testnet-only: reveal a committed batch's seed and draw tiers for the
///         pending tokens, against an already deployed AxVigilCollectible.
/// @dev    Completes the commit-reveal lifecycle for a batch that was committed and
///         minted into by BscLiveDemo (or the production backend) but never revealed.
///         The seed must be the ORIGINAL secret whose keccak256 equals the committed
///         seedHash — it is retained locally by whoever ran the commit, never on-chain.
///
///   PRIVATE_KEY=<owner key> \
///   AXVIGIL_COLLECTIBLE=0x0658...4658 \
///   BATCH_ID=1 \
///   DEMO_SEED=0x<the original 32-byte seed from the mint run> \
///   REVEAL_MAX=16 \
///   forge script script/BscReveal.s.sol --rpc-url "$BSC_TESTNET_RPC" --broadcast
contract BscReveal is Script {
    uint256 internal constant BSC_TESTNET = 97;

    function run() external {
        require(block.chainid == BSC_TESTNET, "BscReveal: BSC testnet (97) only");

        uint256 pk = vm.envUint("PRIVATE_KEY");
        address collectibleAddress = vm.envAddress("AXVIGIL_COLLECTIBLE");
        uint32 batchId = uint32(vm.envUint("BATCH_ID"));
        bytes32 seed = vm.envBytes32("DEMO_SEED");
        uint256 revealMax = vm.envOr("REVEAL_MAX", uint256(16));

        AxVigilCollectible nft = AxVigilCollectible(collectibleAddress);

        // Sanity: the seed must match the committed hash, or revealSeed would revert.
        (bytes32 committedHash,,) = nft.batches(batchId);
        require(
            committedHash == keccak256(abi.encodePacked(seed)),
            "BscReveal: seed does not match the committed hash for this batch"
        );

        vm.startBroadcast(pk);
        nft.revealSeed(batchId, seed);
        uint256 count = nft.revealTokens(revealMax);
        vm.stopBroadcast();

        console2.log("AxVigilCollectible:", collectibleAddress);
        console2.log("Revealed batch:", batchId);
        console2.log("Tokens revealed this call:", count);
        console2.log("Total minted:", nft.totalMinted());
        for (uint256 id = 1; id <= nft.totalMinted() && id <= 8; id++) {
            console2.log("  token", id, "tier", nft.tierOf(id));
        }
    }
}
