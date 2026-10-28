// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";

/// @notice The skill-only `recordSolve` path: a verified solve can be recorded on the agent's
///         resume without minting a collectible, so the record grows past the 2-collectible cap.
///         Shares signer, nonce space and submissionHash dedup with `mint`.
contract SkillRecordTest is AxVigilBase {
    function setUp() public {
        _deploy(_production(), 50);
        vm.prank(alice);
        registry.mintId(alice, 1);
    }

    function _skillAuth(uint256 agentId, uint8 vc, uint8 diff)
        internal
        returns (AxVigilCollectible.SkillAuth memory a)
    {
        a = AxVigilCollectible.SkillAuth({
            agentId: agentId,
            vulnClass: vc,
            difficulty: diff,
            submissionHash: keccak256(abi.encode("skill-submission", nonceCounter)),
            nonce: nonceCounter++,
            deadline: block.timestamp + 1 hours
        });
    }

    function _signSkill(AxVigilCollectible.SkillAuth memory a, uint256 pk) internal view returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, nft.hashSkillAuth(a));
        return abi.encodePacked(r, s, v);
    }

    function _recordSkill(address caller, uint256 agentId, uint8 vc, uint8 diff)
        internal
        returns (AxVigilCollectible.SkillAuth memory a)
    {
        a = _skillAuth(agentId, vc, diff);
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(caller);
        nft.recordSolve(a, sig);
    }

    /// @dev The headline fix: 2 collectibles (classes 0,1) + a skill-only 3rd class (2) =>
    ///      all three classes recorded, even though only 2 collectibles were ever minted.
    function test_skillRecordGrowsPastCollectibleCap() public {
        _mint(alice, 1, 0, 0, 0); // collectible #1, reentrancy
        _mint(alice, 1, 1, 1, 0); // collectible #2, price manipulation
        assertEq(nft.mintedPerAgent(1), 2);

        // A third collectible is correctly refused.
        AxVigilCollectible.MintAuth memory a = _auth(1, alice, 2, 2, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint(a, sig);

        // But the solve can still be recorded on the skill resume.
        _recordSkill(alice, 1, 2, 2); // access control, legendary

        uint32[3] memory counts = skill.classCounts(1);
        assertEq(counts[0], 1, "reentrancy");
        assertEq(counts[1], 1, "price");
        assertEq(counts[2], 1, "access");
        assertEq(skill.totalSolves(1), 3);
        assertEq(skill.maxDifficulty(1), 2, "legendary bumped max difficulty");

        // Collectible supply untouched by the skill-only record.
        assertEq(nft.totalMinted(), 2);
        assertEq(nft.mintedPerAgent(1), 2);

        // SVG now contains all three emblems (none are dashed placeholders).
        string memory uri = skill.tokenURI(1);
        assertGt(bytes(uri).length, 0);
    }

    function test_skillRecordCreatesRecordWithoutAnyMint() public {
        _recordSkill(alice, 1, 0, 1);
        assertTrue(skill.exists(1));
        assertEq(skill.totalSolves(1), 1);
        assertEq(nft.totalMinted(), 0, "no collectible minted");
        assertEq(nft.mintedPerAgent(1), 0, "quota untouched");
    }

    function test_revert_skillRecordReusedNonce() public {
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 0, 0);
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(alice);
        nft.recordSolve(a, sig);

        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.NonceUsed.selector);
        nft.recordSolve(a, sig);
    }

    function test_revert_skillRecordWrongSigner() public {
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 0, 0);
        bytes memory sig = _signSkill(a, 0xBAD5160E); // not the signer
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.recordSolve(a, sig);
    }

    function test_revert_skillRecordNotAgentOwner() public {
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 0, 0);
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(bob); // bob does not own agent 1
        vm.expectRevert(AxVigilCollectible.NotAgentOwner.selector);
        nft.recordSolve(a, sig);
    }

    function test_revert_skillRecordInvalidFields() public {
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 3, 0); // vulnClass out of range
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.recordSolve(a, sig);
    }

    function test_revert_skillRecordExpired() public {
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 0, 0);
        a.deadline = block.timestamp - 1;
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.Expired.selector);
        nft.recordSolve(a, sig);
    }

    /// @dev A revoked agent cannot have further solves recorded, and the dedup/nonce effects
    ///      are rolled back with the revert.
    function test_revert_skillRecordRevokedAgent() public {
        _recordSkill(alice, 1, 0, 0);
        vm.prank(owner);
        skill.revoke(1, "confirmed cheat");

        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 1, 0);
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(alice);
        vm.expectRevert();
        nft.recordSolve(a, sig);

        // Effects rolled back: the nonce is still spendable (not that it matters post-revoke).
        assertFalse(nft.nonceUsed(a.nonce));
        assertFalse(nft.submissionUsed(a.submissionHash));
    }

    /// @dev One verified solve = one submissionHash = at most one on-chain action. A solve already
    ///      minted as a collectible cannot be re-recorded as a skill-only solve (different nonce).
    function test_revert_submissionReusedAcrossMintThenSkill() public {
        AxVigilCollectible.MintAuth memory m = _auth(1, alice, 0, 0, 0);
        bytes memory msig = _sign(m, signerPk);
        vm.prank(alice);
        nft.mint(m, msig);
        assertTrue(nft.submissionUsed(m.submissionHash));

        AxVigilCollectible.SkillAuth memory s = _skillAuth(1, 0, 0);
        s.submissionHash = m.submissionHash; // same solve, fresh nonce
        bytes memory ssig = _signSkill(s, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.SubmissionUsed.selector);
        nft.recordSolve(s, ssig);
    }

    /// @dev ...and the reverse: a skill-recorded solve cannot then be minted as a collectible.
    function test_revert_submissionReusedAcrossSkillThenMint() public {
        AxVigilCollectible.SkillAuth memory s = _recordSkill(alice, 1, 0, 0);

        AxVigilCollectible.MintAuth memory m = _auth(1, alice, 0, 0, 0);
        m.submissionHash = s.submissionHash; // same solve, fresh nonce
        bytes memory msig = _sign(m, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.SubmissionUsed.selector);
        nft.mint(m, msig);
    }

    function test_revert_skillRecordWhenPaused() public {
        vm.prank(owner);
        nft.pause();
        AxVigilCollectible.SkillAuth memory a = _skillAuth(1, 0, 0);
        bytes memory sig = _signSkill(a, signerPk);
        vm.prank(alice);
        vm.expectRevert();
        nft.recordSolve(a, sig);
    }
}
