// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @notice Mints and skill solves are 1:1. Each mint writes exactly one solve, a submission
///         hash can be minted only once, and the third mint is refused. There is no mint-free
///         record path: the collectible no longer exposes `recordSolve`.
contract SkillRecordTest is AxVigilBase {
    function setUp() public {
        _deploy(_production(), 50);
        vm.prank(alice);
        registry.mintId(alice, 1);
    }

    function test_twoMintsWriteTwoSolves() public {
        _mint(alice, 1, 0, 0, 0); // basic reentrancy -> pool 0
        _mint(alice, 1, 1, 1, 1); // advanced price -> pool 1

        assertEq(nft.mintedPerAgent(1), 2);
        assertEq(nft.totalMinted(), 2);
        assertEq(skill.totalSolves(1), 2, "one solve per mint");
        uint32[3] memory counts = skill.classCounts(1);
        assertEq(counts[0], 1);
        assertEq(counts[1], 1);
        assertEq(counts[2], 0, "no third class without a third mint");
        assertEq(skill.maxDifficulty(1), 1);

        AxVigilCollectible.MintAuth memory a = _auth(1, alice, 2, 2, 2);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint(a, sig);

        assertEq(skill.totalSolves(1), 2, "failed mint does not record a solve");
        assertEq(nft.mintedPerAgent(1), 2);
        assertEq(nft.totalMinted(), 2);
    }

    function test_sameSubmissionCannotMintTwice() public {
        AxVigilCollectible.MintAuth memory first = _auth(1, alice, 0, 0, 0);
        bytes memory sig = _sign(first, signerPk);
        vm.prank(alice);
        nft.mint(first, sig);
        assertEq(skill.totalSolves(1), 1);
        assertTrue(nft.submissionUsed(first.submissionHash));

        // Fresh nonce, same solve. Must not mint a second collectible or a second skill solve.
        AxVigilCollectible.MintAuth memory again = _auth(1, alice, 0, 2, 2);
        again.submissionHash = first.submissionHash;
        bytes memory againSig = _sign(again, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.SubmissionUsed.selector);
        nft.mint(again, againSig);

        assertEq(nft.mintedPerAgent(1), 1);
        assertEq(skill.totalSolves(1), 1);
        assertEq(nft.totalMinted(), 1);
    }

    function test_replayedSignatureDoesNotDoubleTheSolve() public {
        AxVigilCollectible.MintAuth memory a = _auth(1, alice, 2, 2, 2);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        nft.mint(a, sig);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.NonceUsed.selector);
        nft.mint(a, sig);
        assertEq(skill.totalSolves(1), 1);
        assertEq(nft.mintedPerAgent(1), 1);
    }

    /// @dev The quota follows the Agent ID, so a second wallet cannot mint a third collectible
    ///      or write a third solve for the same id.
    function test_secondWalletCannotExceedThePair() public {
        _mint(alice, 1, 0, 0, 0);
        _mint(alice, 1, 1, 1, 1);
        vm.prank(alice);
        registry.transferFrom(alice, bob, 1);

        AxVigilCollectible.MintAuth memory a = _auth(1, bob, 2, 2, 2);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(bob);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint(a, sig);
        assertEq(skill.totalSolves(1), 2);
        assertEq(skill.ownerOf(1), bob, "the record followed the Agent ID");
    }
}
