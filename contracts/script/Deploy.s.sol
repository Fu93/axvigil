// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice Deploy AxVigil to BSC testnet (chainId 97). NOT run by the build; see README.
///
/// Required env:
///   PRIVATE_KEY      deployer key (testnet only, tBNB for gas)
///   SIGNER           address of the backend MintAuth signer
/// Optional env:
///   OWNER            owner/admin of both contracts (default: deployer)
///   AGENT_REGISTRY   Agent ID registry; if unset a MockAgentID is deployed
///   HOURLY_CAP       default 50
///   BASE_URI         art metadata base, tokenURI = BASE_URI + artId
///   UNREVEALED_URI   URI shown before reveal
///   SEED_HASH        keccak256(abi.encodePacked(bytes32 seed)) to open batch 1 (only if OWNER == deployer)
///
///   forge script script/Deploy.s.sol --rpc-url bsc_testnet --broadcast
contract Deploy is Script {
    uint256 internal constant BSC_TESTNET = 97;

    function run() external {
        require(block.chainid == BSC_TESTNET, "Deploy: BSC testnet (97) only");

        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);
        address signer = vm.envAddress("SIGNER");
        address owner = vm.envOr("OWNER", deployer);
        address registryAddr = vm.envOr("AGENT_REGISTRY", address(0));
        uint256 hourlyCap = vm.envOr("HOURLY_CAP", uint256(50));
        string memory baseURI = vm.envOr("BASE_URI", string(""));
        string memory unrevealedURI = vm.envOr("UNREVEALED_URI", string(""));
        bytes32 seedHash = vm.envOr("SEED_HASH", bytes32(0));

        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4]; // 7,777

        vm.startBroadcast(pk);

        if (registryAddr == address(0)) {
            registryAddr = address(new MockAgentID());
            console2.log("MockAgentID:", registryAddr);
        }

        // Skill admin = deployer first so we can grant MINTER_ROLE, then hand over if OWNER differs.
        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(registryAddr), deployer);
        AxVigilCollectible nft = new AxVigilCollectible(
            IAgentRegistry(registryAddr), IAxVigilSkill(address(skill)), signer, deployer, tiers, hourlyCap
        );
        skill.grantRole(skill.MINTER_ROLE(), address(nft));

        if (bytes(baseURI).length > 0 || bytes(unrevealedURI).length > 0) nft.setBaseURI(baseURI, unrevealedURI);
        if (seedHash != bytes32(0)) nft.commitSeed(seedHash);

        if (owner != deployer) {
            skill.grantRole(skill.DEFAULT_ADMIN_ROLE(), owner);
            skill.renounceRole(skill.DEFAULT_ADMIN_ROLE(), deployer);
            nft.transferOwnership(owner); // Ownable2Step: OWNER must call acceptOwnership()
        }

        vm.stopBroadcast();

        console2.log("AxVigilSkill:", address(skill));
        console2.log("AxVigilCollectible:", address(nft));
        console2.log("Agent registry:", registryAddr);
        console2.log("Signer:", signer);
    }
}
