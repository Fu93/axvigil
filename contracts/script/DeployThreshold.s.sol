// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice Fresh BSC testnet deploy of the threshold collectible. Does not touch
///         the already-live PR #8 contracts. The operator fills the addresses
///         into deployments/bsc-testnet-97.json under `thresholdRedeploy` after broadcast.
///
/// Required env:
///   PRIVATE_KEY   deployer (also the initial owner, so it can register validators)
///   SIGNER        validator 1, also the legacy single signer (threshold starts at 1)
/// Optional:
///   VALIDATOR_2, VALIDATOR_3   extra graders. If both are set, threshold becomes THRESHOLD (default 2).
///   THRESHOLD     default 2, only applied when VALIDATOR_2 and VALIDATOR_3 are set
///   OWNER, AGENT_REGISTRY, HOURLY_CAP, BASE_URI, UNREVEALED_URI, SEED_HASH
///     same meaning as script/Deploy.s.sol
///
///   forge script script/DeployThreshold.s.sol --rpc-url bsc_testnet --broadcast
contract DeployThreshold is Script {
    uint256 internal constant BSC_TESTNET = 97;

    function run() external {
        require(block.chainid == BSC_TESTNET, "DeployThreshold: BSC testnet (97) only");

        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);
        address signer = vm.envAddress("SIGNER");
        address owner = vm.envOr("OWNER", deployer);
        address registryAddr = vm.envOr("AGENT_REGISTRY", address(0));
        uint256 hourlyCap = vm.envOr("HOURLY_CAP", uint256(50));
        string memory baseURI = vm.envOr("BASE_URI", string(""));
        string memory unrevealedURI = vm.envOr("UNREVEALED_URI", string("ipfs://unrevealed.json"));
        bytes32 seedHash = vm.envOr("SEED_HASH", bytes32(0));
        address validator2 = vm.envOr("VALIDATOR_2", address(0));
        address validator3 = vm.envOr("VALIDATOR_3", address(0));
        uint256 k = vm.envOr("THRESHOLD", uint256(2));

        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4];

        vm.startBroadcast(pk);

        if (registryAddr == address(0)) {
            registryAddr = address(new MockAgentID());
            console2.log("MockAgentID:", registryAddr);
        }

        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(registryAddr), deployer);
        AxVigilCollectible nft = new AxVigilCollectible(
            IAgentRegistry(registryAddr), IAxVigilSkill(address(skill)), signer, deployer, tiers, hourlyCap
        );
        skill.grantRole(skill.MINTER_ROLE(), address(nft));

        if (validator2 != address(0)) nft.addValidator(validator2);
        if (validator3 != address(0)) nft.addValidator(validator3);
        if (validator2 != address(0) && validator3 != address(0)) nft.setThreshold(k);

        if (bytes(baseURI).length > 0 || bytes(unrevealedURI).length > 0) nft.setBaseURI(baseURI, unrevealedURI);
        if (seedHash != bytes32(0)) nft.commitSeed(seedHash);

        if (owner != deployer) {
            skill.grantRole(skill.DEFAULT_ADMIN_ROLE(), owner);
            skill.renounceRole(skill.DEFAULT_ADMIN_ROLE(), deployer);
            nft.transferOwnership(owner);
        }

        vm.stopBroadcast();

        console2.log("AxVigilSkill:", address(skill));
        console2.log("AxVigilCollectible:", address(nft));
        console2.log("Agent registry:", registryAddr);
        console2.log("Validator 1 / legacy signer:", signer);
        console2.log("Threshold:", nft.threshold());
        console2.log("PENDING: write these addresses into deployments/bsc-testnet-97.json thresholdRedeploy");
    }
}
