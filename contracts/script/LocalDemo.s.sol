// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice Local-only end-to-end demo: deploy, create Agent ID, sign and mint.
contract LocalDemo is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        bytes32 submissionHash = vm.envBytes32("SUBMISSION_HASH");
        address deployer = vm.addr(pk);
        uint256[5] memory tiers = [uint256(30), 10, 5, 4, 4];
        bytes32 seed = keccak256("axvigil-local-demo-seed");

        vm.startBroadcast(pk);
        MockAgentID registry = new MockAgentID();
        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(address(registry)), deployer);
        AxVigilCollectible nft = new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), deployer, deployer, tiers, 50
        );
        skill.grantRole(skill.MINTER_ROLE(), address(nft));
        nft.setBaseURI("ipfs://local-art/", "ipfs://local-unrevealed");
        nft.commitSeed(keccak256(abi.encodePacked(seed)));
        uint256 agentId = registry.mint(deployer);

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
        uint256 tokenId = nft.mint(auth, abi.encodePacked(r, s, v));
        vm.stopBroadcast();

        console2.log("AxVigilSkill:", address(skill));
        console2.log("AxVigilCollectible:", address(nft));
        console2.log("MockAgentID:", address(registry));
        console2.log("Agent ID:", agentId);
        console2.log("Collectible token ID:", tokenId);
        console2.log("Skill solves:", skill.totalSolves(agentId));
        console2.logBytes32(submissionHash);
    }
}
