// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice End-to-end lifecycle on a live chain (local anvil --chain-id 97):
///         deploy -> two mints (the lifetime cap, each writing one skill solve) ->
///         commit-reveal -> reveal tiers. There is no mint-free third class.
///
///   anvil --chain-id 97 &
///   forge script script/LiveFlow.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
contract LiveFlow is Script {
    // anvil default keys
    uint256 constant OWNER_PK = 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80;
    uint256 constant SIGNER_PK = 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d;
    uint256 constant ALICE_PK = 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a;

    bytes32 constant SEED = keccak256("axvigil-live");

    function run() external {
        require(block.chainid == 97, "run against chainId 97");
        address owner = vm.addr(OWNER_PK);
        address signer = vm.addr(SIGNER_PK);
        address alice = vm.addr(ALICE_PK);

        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4];

        // --- deploy as owner ---
        vm.startBroadcast(OWNER_PK);
        MockAgentID registry = new MockAgentID();
        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(address(registry)), owner);
        AxVigilCollectible nft = new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), signer, owner, tiers, 50
        );
        skill.grantRole(skill.MINTER_ROLE(), address(nft));
        nft.setBaseURI("ipfs://axvigil-art/", "ipfs://axvigil-unrevealed");
        nft.commitSeed(keccak256(abi.encodePacked(SEED)));
        registry.mintId(alice, 1); // Agent ID #1 -> alice
        vm.stopBroadcast();

        // --- two collectible mints for agent 1. Pool must equal difficulty.
        //     basic reentrancy (pool 0) and advanced price (pool 1). A third mint would revert.
        _mint(nft, alice, 1, 0, 0, 0, keccak256("solve-reentrancy"), 1);
        _mint(nft, alice, 1, 1, 1, 1, keccak256("solve-price"), 2);

        // --- reveal the batch and draw tiers ---
        vm.startBroadcast(OWNER_PK);
        nft.revealSeed(1, SEED);
        nft.revealTokens(10);
        vm.stopBroadcast();

        // --- report ---
        console2.log("MockAgentID   ", address(registry));
        console2.log("AxVigilSkill  ", address(skill));
        console2.log("Collectible   ", address(nft));
        console2.log("owner         ", owner);
        console2.log("signer        ", signer);
        console2.log("alice (agent1)", alice);
        console2.log("totalMinted   ", nft.totalMinted());
        console2.log("tier token#1  ", nft.tierOf(1));
        console2.log("tier token#2  ", nft.tierOf(2));
        uint32[3] memory counts = skill.classCounts(1);
        console2.log("skill classes solved (reentrancy/price/access), 1:1 with mints:");
        console2.log(counts[0], counts[1], counts[2]);
        console2.log("skill maxDifficulty", skill.maxDifficulty(1));
        console2.log("skill totalSolves  ", skill.totalSolves(1));
    }

    function _mint(
        AxVigilCollectible nft, address alice, uint256 agentId,
        uint8 vc, uint8 diff, uint8 pool, bytes32 sub, uint256 nonce
    ) internal {
        AxVigilCollectible.MintAuth memory a = AxVigilCollectible.MintAuth({
            agentId: agentId, to: alice, vulnClass: vc, difficulty: diff, pool: pool,
            submissionHash: sub, nonce: nonce, deadline: 4102444800
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(SIGNER_PK, nft.hashMintAuth(a));
        vm.broadcast(ALICE_PK);
        nft.mint(a, abi.encodePacked(r, s, v));
    }
}
