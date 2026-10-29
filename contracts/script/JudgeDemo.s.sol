// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice Local judge demo. Production quotas, no collectible minted yet.
///         The platform signs the mint after a reward solve. Any chain id is fine;
///         this script does not broadcast to BSC.
///
/// Required env: PRIVATE_KEY (deployer and Agent ID owner), SIGNER (backend address).
contract JudgeDemo is Script {
    bytes32 internal constant SEED = keccak256("axvigil-judge-demo");

    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(pk);
        address signer = vm.envAddress("SIGNER");
        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4];

        vm.startBroadcast(pk);
        MockAgentID registry = new MockAgentID();
        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(address(registry)), deployer);
        AxVigilCollectible nft = new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), signer, deployer, tiers, 50
        );
        skill.grantRole(skill.MINTER_ROLE(), address(nft));
        nft.setBaseURI("https://metadata.axvigil.local/art/", "https://metadata.axvigil.local/unrevealed.json");
        nft.commitSeed(keccak256(abi.encodePacked(SEED)));
        uint256 agentId = registry.mint(deployer);
        vm.stopBroadcast();

        console2.log("REGISTRY", address(registry));
        console2.log("SKILL", address(skill));
        console2.log("COLLECTIBLE", address(nft));
        console2.log("AGENT_ID", agentId);
        console2.log("DEPLOYER", deployer);
        console2.log("SIGNER", signer);
        console2.log("MAX_SUPPLY", nft.maxSupply());
        console2.log("DRAWABLE", nft.drawableSupply());
    }
}
