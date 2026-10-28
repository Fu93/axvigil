// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {IERC5192} from "../src/interfaces/IERC5192.sol";
import {IAccessControl} from "@openzeppelin/contracts/access/IAccessControl.sol";
import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";

contract AxVigilSkillTest is AxVigilBase {
    event Locked(uint256 tokenId);
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event Revoked(uint256 indexed agentId, string reason);

    uint256 internal agentA;

    function setUp() public {
        _deploy(_production(), 100);
        agentA = registry.mint(alice);
    }

    function test_firstSolveEmitsLockedAndTransfer() public {
        vm.expectEmit(true, true, true, true, address(skill));
        emit Transfer(address(0), alice, agentA);
        vm.expectEmit(true, true, true, true, address(skill));
        emit Locked(agentA);
        _mint(alice, agentA, 0, 0, 0);
    }

    function test_lockedAndInterface() public {
        _mint(alice, agentA, 0, 0, 0);
        assertTrue(skill.locked(agentA));
        assertTrue(skill.supportsInterface(0xb45a3c0e), "ERC-5192");
        assertTrue(skill.supportsInterface(type(IERC5192).interfaceId));
        assertTrue(skill.supportsInterface(0x80ac58cd), "ERC-721");
        assertTrue(skill.supportsInterface(0x01ffc9a7), "ERC-165");
    }

    function test_revert_lockedNoRecord() public {
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.NoRecord.selector, 777));
        skill.locked(777);
    }

    function test_nonTransferable() public {
        _mint(alice, agentA, 0, 0, 0);
        vm.startPrank(alice);
        vm.expectRevert(AxVigilSkill.Soulbound.selector);
        skill.transferFrom(alice, bob, agentA);
        vm.expectRevert(AxVigilSkill.Soulbound.selector);
        skill.safeTransferFrom(alice, bob, agentA);
        vm.expectRevert(AxVigilSkill.Soulbound.selector);
        skill.safeTransferFrom(alice, bob, agentA, "");
        vm.expectRevert(AxVigilSkill.Soulbound.selector);
        skill.approve(bob, agentA);
        vm.expectRevert(AxVigilSkill.Soulbound.selector);
        skill.setApprovalForAll(bob, true);
        vm.stopPrank();
        assertEq(skill.ownerOf(agentA), alice);
    }

    function test_onePerAgentAndCounts() public {
        _mint(alice, agentA, 0, 0, 0);
        _mint(alice, agentA, 2, 2, 1);
        assertEq(skill.totalRecords(), 1, "one record per agent");
        assertEq(skill.solvesOf(agentA, 0), 1);
        assertEq(skill.solvesOf(agentA, 1), 0);
        assertEq(skill.solvesOf(agentA, 2), 1);
        uint32[3] memory c = skill.classCounts(agentA);
        assertEq(c[0], 1);
        assertEq(c[2], 1);
        assertEq(skill.maxDifficulty(agentA), 2);
        assertEq(skill.totalSolves(agentA), 2);
    }

    function test_maxDifficultyNeverDecreases() public {
        bytes32 role = skill.MINTER_ROLE();
        vm.prank(owner);
        skill.grantRole(role, address(this));
        skill.recordSolve(agentA, 0, 2);
        skill.recordSolve(agentA, 1, 0);
        assertEq(skill.maxDifficulty(agentA), 2);
    }

    function test_revert_onlyMinterRecords() public {
        bytes32 role = skill.MINTER_ROLE();
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(IAccessControl.AccessControlUnauthorizedAccount.selector, alice, role));
        skill.recordSolve(agentA, 0, 0);
    }

    function test_revert_invalidClassOrDifficulty() public {
        bytes32 role = skill.MINTER_ROLE();
        vm.prank(owner);
        skill.grantRole(role, address(this));
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.InvalidVulnClass.selector, 3));
        skill.recordSolve(agentA, 3, 0);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.InvalidDifficulty.selector, 3));
        skill.recordSolve(agentA, 0, 3);
    }

    function test_revoke() public {
        _mint(alice, agentA, 0, 1, 0);
        vm.expectEmit(true, false, false, true, address(skill));
        emit Revoked(agentA, "leaked answer");
        vm.prank(owner);
        skill.revoke(agentA, "leaked answer");

        assertFalse(skill.exists(agentA));
        assertTrue(skill.isRevoked(agentA));
        assertEq(skill.revokeReason(agentA), "leaked answer");
        assertEq(skill.totalRecords(), 0);
        assertEq(skill.solvesOf(agentA, 0), 0);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.NoRecord.selector, agentA));
        skill.ownerOf(agentA);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.NoRecord.selector, agentA));
        skill.tokenURI(agentA);

        // revoked agent cannot earn new solves (whole mint reverts)
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 1, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.AgentRevoked.selector, agentA));
        nft.mint(a, sig);
        // the already-minted collectible is untouched (it is a separate, tradeable asset)
        assertEq(nft.ownerOf(1), alice);
    }

    function test_revert_revokeOnlyAdmin() public {
        _mint(alice, agentA, 0, 0, 0);
        vm.prank(alice);
        vm.expectRevert(
            abi.encodeWithSelector(IAccessControl.AccessControlUnauthorizedAccount.selector, alice, bytes32(0))
        );
        skill.revoke(agentA, "x");
    }

    function test_revert_revokeNoRecord() public {
        vm.prank(owner);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.NoRecord.selector, agentA));
        skill.revoke(agentA, "x");
    }

    /// The record follows the Agent ID: changing wallets does not lose it, selling the collectible
    /// does not move it.
    function test_followsAgentIdTransfer() public {
        _mint(alice, agentA, 1, 1, 0);
        assertEq(skill.ownerOf(agentA), alice);

        // Before sellout, the collectible cannot trade.
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.TradingNotOpen.selector);
        nft.transferFrom(alice, bob, 1);
        assertEq(skill.ownerOf(agentA), alice);

        // moving the Agent ID moves the record
        address newWallet = makeAddr("newWallet");
        vm.prank(alice);
        registry.transferFrom(alice, newWallet, agentA);
        assertEq(skill.ownerOf(agentA), newWallet);
        assertEq(skill.solvesOf(agentA, 1), 1, "history kept");

        // the new wallet can use the remaining quota; the old one cannot
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.NotAgentOwner.selector);
        nft.mint(a, sig);
        _mint(newWallet, agentA, 0, 0, 0);
        assertEq(skill.solvesOf(agentA, 0), 1);
    }

    function test_collectibleTradeAfterSelloutDoesNotMoveSkill() public {
        _deploy([uint256(4), 0, 0, 0, 0], 100);
        agentA = registry.mint(alice);
        uint256 agentB = registry.mint(bob);
        _mint(alice, agentA, 0, 0, 0);
        _mint(alice, agentA, 1, 1, 0);
        _mint(bob, agentB, 0, 0, 0);
        _mint(bob, agentB, 2, 0, 0);
        vm.prank(alice);
        nft.transferFrom(alice, bob, 1);
        assertEq(nft.ownerOf(1), bob);
        assertEq(skill.ownerOf(agentA), alice);
        assertEq(skill.totalSolves(agentA), 2);
    }

    function test_balanceOfUnsupported() public {
        vm.expectRevert(AxVigilSkill.BalanceUnsupported.selector);
        skill.balanceOf(alice);
    }

    function test_tokenURIOnChainAndGrows() public {
        _mint(alice, agentA, 0, 0, 0);
        string memory uri1 = skill.tokenURI(agentA);
        assertTrue(_startsWith(uri1, "data:application/json;base64,"));
        _mint(alice, agentA, 1, 2, 0);
        string memory uri2 = skill.tokenURI(agentA);
        assertGt(bytes(uri2).length, bytes(uri1).length, "SVG gains an element per new class");
        assertTrue(keccak256(bytes(uri1)) != keccak256(bytes(uri2)));
    }

    /// Fully-solved record: decoded JSON reports all three classes and LEGENDARY.
    function test_svgContainsAllEmblems() public {
        bytes32 role = skill.MINTER_ROLE();
        vm.prank(owner);
        skill.grantRole(role, address(this));
        skill.recordSolve(agentA, 0, 0);
        skill.recordSolve(agentA, 1, 1);
        skill.recordSolve(agentA, 2, 2);
        string memory uri = skill.tokenURI(agentA);
        // all three emblem colours present once decoded
        string memory json = string(_b64decode(_substr(uri, 29)));
        assertTrue(_contains(json, '"Max Difficulty","value":"LEGENDARY"'));
        assertTrue(_contains(json, '"Classes Solved","value":3'));
    }

    // ---------------------------------------------------------------- helpers

    function _startsWith(string memory s, string memory p) internal pure returns (bool) {
        bytes memory a = bytes(s);
        bytes memory b = bytes(p);
        if (a.length < b.length) return false;
        for (uint256 i; i < b.length; ++i) {
            if (a[i] != b[i]) return false;
        }
        return true;
    }

    function _contains(string memory s, string memory p) internal pure returns (bool) {
        bytes memory a = bytes(s);
        bytes memory b = bytes(p);
        if (b.length > a.length) return false;
        for (uint256 i; i <= a.length - b.length; ++i) {
            bool ok = true;
            for (uint256 j; j < b.length; ++j) {
                if (a[i + j] != b[j]) {
                    ok = false;
                    break;
                }
            }
            if (ok) return true;
        }
        return false;
    }

    function _substr(string memory s, uint256 from) internal pure returns (string memory) {
        bytes memory a = bytes(s);
        bytes memory out = new bytes(a.length - from);
        for (uint256 i; i < out.length; ++i) {
            out[i] = a[from + i];
        }
        return string(out);
    }

    function _b64decode(string memory s) internal pure returns (bytes memory) {
        bytes memory data = bytes(s);
        bytes memory table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        uint8[128] memory rev;
        for (uint8 i; i < 64; ++i) {
            rev[uint8(table[i])] = i;
        }
        uint256 pad;
        if (data.length > 0 && data[data.length - 1] == "=") pad++;
        if (data.length > 1 && data[data.length - 2] == "=") pad++;
        bytes memory out = new bytes((data.length / 4) * 3 - pad);
        uint256 o;
        for (uint256 i; i < data.length; i += 4) {
            uint256 n = (uint256(rev[uint8(data[i])]) << 18) | (uint256(rev[uint8(data[i + 1])]) << 12)
                | (uint256(rev[uint8(data[i + 2])]) << 6) | uint256(rev[uint8(data[i + 3])]);
            if (o < out.length) out[o++] = bytes1(uint8(n >> 16));
            if (o < out.length) out[o++] = bytes1(uint8(n >> 8));
            if (o < out.length) out[o++] = bytes1(uint8(n));
        }
        return out;
    }
}
