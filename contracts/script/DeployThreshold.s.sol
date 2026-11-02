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

    struct Cfg {
        uint256 pk;
        address deployer;
        address signer;
        address owner;
        address registryAddr;
        uint256 hourlyCap;
        string baseURI;
        string unrevealedURI;
        bytes32 seedHash;
        address validator2;
        address validator3;
        uint256 k;
    }

    function run() external {
        require(block.chainid == BSC_TESTNET, "DeployThreshold: BSC testnet (97) only");
        Cfg memory c = _cfg();

        vm.startBroadcast(c.pk);

        if (c.registryAddr == address(0)) {
            c.registryAddr = address(new MockAgentID());
            console2.log("MockAgentID:", c.registryAddr);
        }

        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(c.registryAddr), c.deployer);
        AxVigilCollectible nft = _deployCollectible(c, address(skill));
        skill.grantRole(skill.MINTER_ROLE(), address(nft));

        if (c.validator2 != address(0)) nft.addValidator(c.validator2);
        if (c.validator3 != address(0)) nft.addValidator(c.validator3);
        if (c.validator2 != address(0) && c.validator3 != address(0)) nft.setThreshold(c.k);

        if (bytes(c.baseURI).length > 0 || bytes(c.unrevealedURI).length > 0) nft.setBaseURI(c.baseURI, c.unrevealedURI);
        if (c.seedHash != bytes32(0)) nft.commitSeed(c.seedHash);

        if (c.owner != c.deployer) {
            skill.grantRole(skill.DEFAULT_ADMIN_ROLE(), c.owner);
            skill.renounceRole(skill.DEFAULT_ADMIN_ROLE(), c.deployer);
            nft.transferOwnership(c.owner);
        }

        vm.stopBroadcast();

        console2.log("AxVigilSkill:", address(skill));
        console2.log("AxVigilCollectible:", address(nft));
        console2.log("Agent registry:", c.registryAddr);
        console2.log("Validator 1 / legacy signer:", c.signer);
        console2.log("Threshold:", nft.threshold());
        console2.log("PENDING: write these addresses into deployments/bsc-testnet-97.json thresholdRedeploy");
    }

    /// @dev Env is read into a struct so run() stays under the legacy-codegen stack limit (via_ir = false).
    function _cfg() internal view returns (Cfg memory c) {
        c.pk = vm.envUint("PRIVATE_KEY");
        c.deployer = vm.addr(c.pk);
        c.signer = vm.envAddress("SIGNER");
        c.owner = vm.envOr("OWNER", c.deployer);
        c.registryAddr = vm.envOr("AGENT_REGISTRY", address(0));
        c.hourlyCap = vm.envOr("HOURLY_CAP", uint256(50));
        c.baseURI = vm.envOr("BASE_URI", string(""));
        c.unrevealedURI = vm.envOr("UNREVEALED_URI", string("ipfs://unrevealed.json"));
        c.seedHash = vm.envOr("SEED_HASH", bytes32(0));
        c.validator2 = vm.envOr("VALIDATOR_2", address(0));
        c.validator3 = vm.envOr("VALIDATOR_3", address(0));
        c.k = vm.envOr("THRESHOLD", uint256(2));
    }

    function _deployCollectible(Cfg memory c, address skill) internal returns (AxVigilCollectible) {
        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4];
        return new AxVigilCollectible(
            IAgentRegistry(c.registryAddr), IAxVigilSkill(skill), c.signer, c.deployer, tiers, c.hourlyCap
        );
    }
}
