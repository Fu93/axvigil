// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @notice 2-of-3 validator signatures over one MintAuth. The owner is not a validator.
contract ThresholdTest is AxVigilBase {
    uint256 internal agentA;
    uint256 internal pk2 = 0xB0B;
    uint256 internal pk3 = 0xC0C;
    address internal v2;
    address internal v3;

    function setUp() public {
        _deploy(_production(), 100);
        agentA = registry.mint(alice);
        v2 = vm.addr(pk2);
        v3 = vm.addr(pk3);
        vm.startPrank(owner);
        nft.addValidator(v2);
        nft.addValidator(v3);
        nft.setThreshold(2);
        vm.stopPrank();
        assertFalse(nft.isValidator(owner));
        assertEq(nft.validatorCount(), 3);
        assertEq(nft.threshold(), 2);
    }

    function _sigs(AxVigilCollectible.MintAuth memory a, uint256 pkA, uint256 pkB) internal view returns (bytes[] memory) {
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _sign(a, pkA);
        sigs[1] = _sign(a, pkB);
        return sigs;
    }

    function test_twoOfThreeMints() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 2, 2, 2);
        bytes[] memory sigs = _sigs(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint(a, sigs);
        assertEq(id, 1);
        assertEq(nft.mintedPerAgent(agentA), 1);
        assertTrue(nft.submissionUsed(a.submissionHash));
        assertEq(skill.totalSolves(agentA), 1);
    }

    function test_revert_singleSigWhenThresholdIsTwo() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.ThresholdRequired.selector);
        nft.mint(a, sig);
    }

    function test_revert_insufficientSignatures() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes[] memory one = new bytes[](1);
        one[0] = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilCollectible.InsufficientSignatures.selector, 1, 2));
        nft.mint(a, one);
    }

    function test_revert_duplicateSigner() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = _sign(a, signerPk);
        sigs[1] = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilCollectible.DuplicateSigner.selector, signerAddr));
        nft.mint(a, sigs);
    }

    function test_revert_nonValidator() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        uint256 stranger = 0xBADBAD;
        bytes[] memory sigs = _sigs(a, signerPk, stranger);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilCollectible.NotValidator.selector, vm.addr(stranger)));
        nft.mint(a, sigs);
    }

    function test_revert_removedValidator() public {
        vm.prank(owner);
        nft.removeValidator(v3);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes[] memory removed = _sigs(a, signerPk, pk3);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilCollectible.NotValidator.selector, v3));
        nft.mint(a, removed);
        bytes[] memory live = _sigs(a, signerPk, pk2);
        vm.prank(alice);
        nft.mint(a, live);
    }

    function test_revert_replayedSubmission() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes[] memory sigs = _sigs(a, signerPk, pk2);
        vm.prank(alice);
        nft.mint(a, sigs);
        // A later auth that reuses the hash, with a fresh nonce, is still rejected.
        AxVigilCollectible.MintAuth memory again = _auth(agentA, alice, 0, 0, 0);
        again.submissionHash = a.submissionHash;
        bytes[] memory againSigs = _sigs(again, pk2, pk3);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.SubmissionUsed.selector);
        nft.mint(again, againSigs);
    }

    function test_revert_cannotRemoveBelowThreshold() public {
        vm.prank(owner);
        nft.removeValidator(v3);
        assertEq(nft.validatorCount(), 2);
        vm.prank(owner);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.removeValidator(v2);
    }

    function test_revert_addValidatorOnlyOwner() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice));
        nft.addValidator(alice);
    }
}
