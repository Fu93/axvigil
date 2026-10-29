// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @notice Verifies the handoff represented by the first two vertical slices:
/// verifier submissionHash -> EIP-712 MintAuth -> collectible + skill record.
contract VerifierMintIntegrationTest is AxVigilBase {
    uint256 internal agentA;
    event Minted(
        uint256 indexed tokenId,
        uint256 indexed agentId,
        address indexed to,
        uint8 vulnClass,
        uint8 difficulty,
        uint8 pool,
        uint32 batchId,
        bytes32 submissionHash,
        uint256 nonce
    );
    bytes32 internal constant VERIFIED_REENTRANCY_SUBMISSION =
        0x2222222222222222222222222222222222222222222222222222222222222222;

    function setUp() public {
        _deploy(_production(), 100);
        agentA = registry.mint(alice);
    }

    function testPassedVerifierHashMintsCollectibleAndSkill() public {
        AxVigilCollectible.MintAuth memory auth = AxVigilCollectible.MintAuth({
            agentId: agentA,
            to: alice,
            vulnClass: 0, // REENTRANCY, from verifier challenge reentrancy-001
            difficulty: 1,
            pool: 1,
            submissionHash: VERIFIED_REENTRANCY_SUBMISSION,
            nonce: 9001,
            deadline: block.timestamp + 1 hours
        });
        bytes memory signature = _sign(auth, signerPk);

        vm.expectEmit(true, true, true, true, address(nft));
        emit Minted(1, agentA, alice, 0, 1, 1, 1, VERIFIED_REENTRANCY_SUBMISSION, 9001);
        vm.prank(alice);
        uint256 tokenId = nft.mint(auth, signature);

        assertEq(tokenId, 1);
        assertEq(nft.ownerOf(tokenId), alice);
        assertEq(nft.agentOfToken(tokenId), agentA);
        assertEq(skill.solvesOf(agentA, 0), 1);
        assertEq(skill.maxDifficulty(agentA), 1);
        assertEq(skill.totalSolves(agentA), 1);
    }

    function testTamperingVerifiedHashInvalidatesSignature() public {
        AxVigilCollectible.MintAuth memory auth = AxVigilCollectible.MintAuth({
            agentId: agentA,
            to: alice,
            vulnClass: 0,
            difficulty: 1,
            pool: 1,
            submissionHash: VERIFIED_REENTRANCY_SUBMISSION,
            nonce: 9002,
            deadline: block.timestamp + 1 hours
        });
        bytes memory signature = _sign(auth, signerPk);
        auth.submissionHash = keccak256("tampered patch");

        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.mint(auth, signature);
    }

    function testMintAtGenesisBlockDoesNotUnderflow() public {
        AxVigilCollectible.MintAuth memory auth = AxVigilCollectible.MintAuth({
            agentId: agentA,
            to: alice,
            vulnClass: 0,
            difficulty: 0,
            pool: 0,
            submissionHash: VERIFIED_REENTRANCY_SUBMISSION,
            nonce: 9003,
            deadline: block.timestamp + 1 hours
        });
        bytes memory signature = _sign(auth, signerPk);
        vm.roll(0);
        vm.prank(alice);
        assertEq(nft.mint(auth, signature), 1);
    }
}
