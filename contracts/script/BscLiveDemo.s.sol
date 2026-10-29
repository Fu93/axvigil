// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {MockAgentID} from "../src/MockAgentID.sol";

/// @notice Testnet-only live demo against already deployed AxVigil contracts.
/// @dev Commits a local seed, mints MockAgentID #1, signs MintAuth and mints one collectible.
///      Never use this script with a production Agent ID registry or production funds.
contract BscLiveDemo is Script {
    uint256 internal constant BSC_TESTNET = 97;

    function run() external {
        require(block.chainid == BSC_TESTNET, "BscLiveDemo: BSC testnet (97) only");

        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);
        address registryAddress = vm.envAddress("AGENT_REGISTRY");
        address collectibleAddress = vm.envAddress("AXVIGIL_COLLECTIBLE");
        bytes32 seed = vm.envBytes32("DEMO_SEED");
        bytes32 submissionHash = vm.envBytes32("SUBMISSION_HASH");

        MockAgentID registry = MockAgentID(registryAddress);
        AxVigilCollectible nft = AxVigilCollectible(collectibleAddress);

        vm.startBroadcast(pk);
        nft.commitSeed(keccak256(abi.encodePacked(seed)));
        (uint256 agentId, uint256 tokenId) = _mint(nft, registry, deployer, pk, submissionHash);
        vm.stopBroadcast();

        console2.log("Agent ID:", agentId);
        console2.log("Collectible token ID:", tokenId);
        console2.log("AxVigilCollectible:", collectibleAddress);
        console2.log("Submission hash:");
        console2.logBytes32(submissionHash);
    }

    function _mint(AxVigilCollectible nft, MockAgentID registry, address deployer, uint256 pk, bytes32 submissionHash)
        internal
        returns (uint256 agentId, uint256 tokenId)
    {
        agentId = registry.mint(deployer);
        AxVigilCollectible.MintAuth memory auth = AxVigilCollectible.MintAuth({
            agentId: agentId,
            to: deployer,
            vulnClass: 0,
            difficulty: 1,
            pool: 1,
            submissionHash: submissionHash,
            nonce: 1,
            deadline: block.timestamp + 1 hours
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, nft.hashMintAuth(auth));
        tokenId = nft.mint(auth, abi.encodePacked(r, s, v));
    }
}
