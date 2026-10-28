// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {AxVigilCollectible} from "../../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../../src/AxVigilSkill.sol";
import {MockAgentID} from "../../src/MockAgentID.sol";
import {IAgentRegistry} from "../../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../../src/interfaces/IAxVigilSkill.sol";

/// @dev Shared deployment + signing helpers.
abstract contract AxVigilBase is Test {
    MockAgentID internal registry;
    AxVigilSkill internal skill;
    AxVigilCollectible internal nft;

    address internal owner = makeAddr("owner");
    uint256 internal signerPk = 0xA11CE;
    address internal signerAddr;
    address internal alice = makeAddr("alice");
    address internal bob = makeAddr("bob");

    bytes32 internal constant SEED = keccak256("seed-1");
    uint256 internal nonceCounter = 1;

    function _deploy(uint256[5] memory tiers, uint256 hourlyCap) internal {
        signerAddr = vm.addr(signerPk);
        registry = new MockAgentID();
        skill = new AxVigilSkill(IAgentRegistry(address(registry)), owner);
        nft = new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), signerAddr, owner, tiers, hourlyCap
        );
        vm.startPrank(owner);
        skill.grantRole(skill.MINTER_ROLE(), address(nft));
        nft.setBaseURI("ipfs://art/", "ipfs://unrevealed");
        nft.commitSeed(keccak256(abi.encodePacked(SEED)));
        vm.stopPrank();
    }

    function _production() internal pure returns (uint256[5] memory t) {
        t = [uint256(5444), 1555, 622, 152, 4];
    }

    function _auth(uint256 agentId, address to, uint8 vc, uint8 diff, uint8 pool)
        internal
        returns (AxVigilCollectible.MintAuth memory a)
    {
        a = AxVigilCollectible.MintAuth({
            agentId: agentId,
            to: to,
            vulnClass: vc,
            difficulty: diff,
            pool: pool,
            submissionHash: keccak256(abi.encode("submission", nonceCounter)),
            nonce: nonceCounter++,
            deadline: block.timestamp + 1 hours
        });
    }

    function _sign(AxVigilCollectible.MintAuth memory a, uint256 pk) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, nft.hashMintAuth(a));
        return abi.encodePacked(r, s, v);
    }

    /// @dev Mint as `caller` with a valid signature.
    function _mint(address caller, uint256 agentId, uint8 vc, uint8 diff, uint8 pool) internal returns (uint256) {
        AxVigilCollectible.MintAuth memory a = _auth(agentId, caller, vc, diff, pool);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(caller);
        return nft.mint(a, sig);
    }
}
