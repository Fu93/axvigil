// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilChallenge} from "../src/AxVigilChallenge.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @notice Optimistic challenge window: state machine, EIP-712 verdicts, bond accounting.
contract ChallengeTest is AxVigilBase {
    AxVigilChallenge internal book;

    uint256 internal agentA;
    uint256 internal pk2 = 0xB0B;
    uint256 internal pk3 = 0xC0C;
    address internal v2;
    address internal v3;
    address internal challenger = makeAddr("challenger");
    address internal treasury = makeAddr("treasury");

    uint256 internal constant WINDOW = 1 hours;
    uint256 internal constant RESPONSE = 1 hours;
    uint256 internal constant CHALLENGE_BOND = 0.01 ether;
    uint256 internal constant OPERATOR_BOND = 0.02 ether;
    uint256 internal constant REWARD = 0.005 ether;

    bytes internal constant EVIDENCE = "cidv1-bafy-counterexample";
    bytes32 internal constant REASON = keccak256("regrade-failed");

    function setUp() public {
        _deploy([uint256(30), 10, 5, 4, 4], 1000);
        agentA = registry.mint(alice);
        v2 = vm.addr(pk2);
        v3 = vm.addr(pk3);
        vm.startPrank(owner);
        nft.addValidator(v2);
        nft.addValidator(v3);
        nft.setThreshold(2);
        book = new AxVigilChallenge(
            address(nft), IAxVigilSkill(address(skill)), owner, WINDOW, RESPONSE, CHALLENGE_BOND, OPERATOR_BOND, REWARD
        );
        nft.setChallengeBook(address(book));
        skill.grantRole(skill.MINTER_ROLE(), address(book));
        book.setTreasury(treasury);
        vm.stopPrank();
        vm.deal(alice, 100 ether);
        vm.deal(challenger, 100 ether);
        vm.deal(owner, 100 ether);
        vm.deal(treasury, 1 ether);
    }

    function _pair(AxVigilCollectible.MintAuth memory a, uint256 pkA, uint256 pkB)
        internal
        view
        returns (bytes[] memory sigs)
    {
        sigs = new bytes[](2);
        sigs[0] = _sign(a, pkA);
        sigs[1] = _sign(a, pkB);
    }

    function _raw(bytes32 digest, uint256 pk) internal pure returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, digest);
        return abi.encodePacked(r, s, v);
    }

    function _verdict(uint256 tokenId, bool upheld, bytes32 reason, uint256 pkA, uint256 pkB)
        internal
        view
        returns (bytes[] memory sigs)
    {
        bytes32 digest = book.hashChallengeVerdict(tokenId, upheld, reason);
        sigs = new bytes[](2);
        sigs[0] = _raw(digest, pkA);
        sigs[1] = _raw(digest, pkB);
    }

    function _mint(uint256 agentId, address caller) internal returns (uint256 id) {
        AxVigilCollectible.MintAuth memory a = _auth(agentId, caller, 0, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        uint256 bond = book.operatorBond();
        vm.prank(caller);
        id = nft.mint{value: bond}(a, sigs);
    }

    function _challenge(uint256 tokenId, address who) internal {
        uint256 bond = book.challengeBond();
        vm.prank(who);
        book.challenge{value: bond}(tokenId, EVIDENCE);
    }

    function _books() internal view {
        assertEq(
            book.escrowed() + book.bondsHeld() + book.poolBalance() + book.claimable(),
            address(book).balance,
            "bond accounting"
        );
    }

    function _drain(address account) internal {
        uint256 amount = book.withdrawable(account);
        if (amount == 0) return;
        uint256 before = account.balance;
        vm.prank(account);
        book.withdraw();
        assertEq(account.balance, before + amount);
    }

    function test_pendingUntilWindow_thenLazyFinal_thenFinalize() public {
        uint256 id = _mint(agentA, alice);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
        assertEq(nft.status(id), uint8(AxVigilChallenge.RecordStatus.Pending));
        assertFalse(skill.isValid(agentA));
        assertEq(book.submissionHashOf(id), nft.submissionUsed(book.submissionHashOf(id)) ? book.submissionHashOf(id) : bytes32(0));
        assertEq(book.tokenBySubmission(book.submissionHashOf(id)), id);
        assertEq(book.record(id).evidenceHash, bytes32(0));
        assertEq(book.escrowed(), OPERATOR_BOND);
        _books();

        vm.warp(block.timestamp + WINDOW - 1);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
        vm.expectRevert(AxVigilChallenge.ChallengeWindowOpen.selector);
        book.finalize(id);

        vm.warp(block.timestamp + 1);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Final));
        assertFalse(book.record(id).finalized, "lazy view is not yet written");
        assertFalse(skill.isValid(agentA));

        vm.expectEmit(true, false, false, true, address(book));
        emit AxVigilChallenge.Finalized(id);
        book.finalize(id);
        assertTrue(book.record(id).finalized);
        assertTrue(skill.isValid(agentA));
        assertEq(skill.totalSolves(agentA), 1);
        assertEq(book.withdrawable(alice), OPERATOR_BOND);
        assertEq(book.escrowed(), 0);
        _books();
        _drain(alice);
        assertEq(address(book).balance, 0);
        _books();

        vm.expectRevert(AxVigilChallenge.AlreadyFinal.selector);
        book.finalize(id);
        vm.expectRevert(AxVigilChallenge.AlreadyFinal.selector);
        book.challenge{value: CHALLENGE_BOND}(id, EVIDENCE);
    }

    function test_upheldChallengeRevokesAndPays() public {
        uint256 id = _mint(agentA, alice);
        uint256 start = challenger.balance;

        vm.expectEmit(true, true, false, true, address(book));
        emit AxVigilChallenge.Challenged(id, challenger, keccak256(EVIDENCE), CHALLENGE_BOND);
        _challenge(id, challenger);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Challenged));
        assertEq(book.record(id).evidenceHash, keccak256(EVIDENCE));
        assertTrue(nft.flagged(id) == false);
        _books();

        vm.expectEmit(true, false, false, true, address(book));
        emit AxVigilChallenge.ChallengeResolved(id, true, REASON);
        vm.expectEmit(true, false, false, true, address(book));
        emit AxVigilChallenge.Revoked(id, REASON);
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk3));

        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Revoked));
        assertTrue(book.flagged(id));
        assertTrue(nft.flagged(id));
        assertFalse(skill.isValid(agentA));
        assertEq(skill.totalSolves(agentA), 0);
        assertEq(skill.solvesOf(agentA, 0), 0);
        assertTrue(skill.locked(agentA), "soulbound record stays locked");
        assertTrue(skill.exists(agentA));
        assertEq(nft.mintedPerAgent(agentA), 1, "quota is not refunded");
        assertEq(book.withdrawable(challenger), CHALLENGE_BOND + OPERATOR_BOND);
        assertEq(book.escrowed(), 0);
        assertEq(book.poolBalance(), 0, "escrow pays before the pool");
        _books();

        vm.expectRevert(AxVigilChallenge.AlreadyRevoked.selector);
        book.finalize(id);
        bytes[] memory replay = _verdict(id, true, REASON, signerPk, pk2);
        vm.expectRevert(AxVigilChallenge.NoChallenge.selector);
        book.resolveChallenge(id, true, REASON, replay);

        _drain(challenger);
        assertEq(challenger.balance, start + OPERATOR_BOND);
        _books();
        assertEq(address(book).balance, 0);
    }

    function test_rejectedChallengePaysTreasury_thenFinalize() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        book.resolveChallenge(id, false, keccak256("regrade-passed"), _verdict(id, false, keccak256("regrade-passed"), pk2, pk3));
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
        assertEq(book.withdrawable(treasury), CHALLENGE_BOND);
        assertEq(book.withdrawable(challenger), 0);
        assertEq(book.escrowed(), OPERATOR_BOND);
        _books();

        vm.warp(block.timestamp + WINDOW);
        book.finalize(id);
        assertTrue(skill.isValid(agentA));
        assertEq(book.withdrawable(alice), OPERATOR_BOND);
        _drain(treasury);
        _drain(alice);
        _books();
        assertEq(address(book).balance, 0);
    }

    function test_rechallengeAfterRejection_insideWindow() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        book.resolveChallenge(id, false, REASON, _verdict(id, false, REASON, signerPk, pk2));
        _challenge(id, challenger);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Challenged));
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk3));
        assertTrue(book.flagged(id));
        _books();
    }

    function test_revert_doubleChallengeWhileOpen() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        vm.deal(bob, 1 ether);
        vm.prank(bob);
        vm.expectRevert(AxVigilChallenge.DoubleChallenge.selector);
        book.challenge{value: CHALLENGE_BOND}(id, "other");
    }

    function test_revert_finalizeWhileChallengeOpen() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        vm.warp(block.timestamp + WINDOW + 1);
        vm.expectRevert(AxVigilChallenge.ChallengeStillOpen.selector);
        book.finalize(id);
    }

    function test_resolveAfterWindow_challengeBefore() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        uint256 otherAgent = registry.mint(alice);
        uint256 late = _mint(otherAgent, alice);
        vm.warp(book.record(id).readyAt + 10);
        vm.expectRevert(AxVigilChallenge.ChallengeWindowClosed.selector);
        book.challenge{value: CHALLENGE_BOND}(late, EVIDENCE);
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk2));
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Revoked));
        _books();
    }

    function test_expireReturnsBond_andCanChallengeAgain() public {
        vm.prank(owner);
        book.setResponseWindow(10 minutes);
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        uint64 respondBy = book.record(id).respondBy;
        vm.warp(respondBy - 1);
        vm.expectRevert(AxVigilChallenge.ChallengeWindowOpen.selector);
        book.expireChallenge(id);
        vm.warp(respondBy);
        vm.expectEmit(true, false, false, true, address(book));
        emit AxVigilChallenge.ChallengeExpired(id);
        book.expireChallenge(id);
        assertEq(book.withdrawable(challenger), CHALLENGE_BOND);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
        _books();
        _challenge(id, challenger);
        assertEq(book.bondsHeld(), CHALLENGE_BOND);
        _books();
    }

    function test_expireAfterWindowAllowsFinalize() public {
        uint256 id = _mint(agentA, alice);
        vm.warp(book.record(id).readyAt - 1);
        _challenge(id, challenger);
        vm.warp(book.record(id).respondBy);
        book.expireChallenge(id);
        vm.expectRevert(AxVigilChallenge.ChallengeWindowClosed.selector);
        book.challenge{value: CHALLENGE_BOND}(id, EVIDENCE);
        book.finalize(id);
        assertTrue(skill.isValid(agentA));
        _books();
    }

    function test_responseWindowIsSnapshotted() public {
        uint256 id = _mint(agentA, alice);
        vm.prank(owner);
        book.setResponseWindow(10);
        _challenge(id, challenger);
        vm.prank(owner);
        book.setResponseWindow(30 days);
        vm.warp(block.timestamp + 10);
        book.expireChallenge(id);
        _books();
    }

    function test_challengeWindowIsSnapshotted() public {
        uint256 id = _mint(agentA, alice);
        vm.prank(owner);
        book.setChallengeWindow(1);
        vm.warp(block.timestamp + 2);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
        vm.warp(book.record(id).readyAt);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Final));
        vm.expectRevert(AxVigilChallenge.ChallengeWindowClosed.selector);
        book.challenge{value: CHALLENGE_BOND}(id, EVIDENCE);
    }

    function test_verdictRejectsWrongDomainChainAndReplay() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        bytes[] memory good = _verdict(id, true, REASON, signerPk, pk2);

        bytes32 foreign = book.hashChallengeVerdict(id + 1, true, REASON);
        bytes[] memory otherToken = new bytes[](2);
        otherToken[0] = _raw(foreign, signerPk);
        otherToken[1] = _raw(foreign, pk2);
        vm.expectRevert();
        book.resolveChallenge(id, true, REASON, otherToken);

        bytes[] memory flipped = _verdict(id, false, REASON, signerPk, pk2);
        vm.expectRevert();
        book.resolveChallenge(id, true, REASON, flipped);

        bytes[] memory otherReason = _verdict(id, true, keccak256("other"), signerPk, pk2);
        vm.expectRevert();
        book.resolveChallenge(id, true, REASON, otherReason);

        uint256 snapshot = vm.snapshotState();
        vm.chainId(1);
        vm.expectRevert();
        book.resolveChallenge(id, true, REASON, good);
        vm.revertToState(snapshot);

        AxVigilChallenge other = new AxVigilChallenge(
            address(nft), IAxVigilSkill(address(skill)), owner, WINDOW, RESPONSE, CHALLENGE_BOND, OPERATOR_BOND, REWARD
        );
        bytes32 digest = other.hashChallengeVerdict(id, true, REASON);
        bytes[] memory wrongContract = new bytes[](2);
        wrongContract[0] = _raw(digest, signerPk);
        wrongContract[1] = _raw(digest, pk2);
        vm.expectRevert();
        book.resolveChallenge(id, true, REASON, wrongContract);

        book.resolveChallenge(id, true, REASON, good);
        vm.expectRevert(AxVigilChallenge.NoChallenge.selector);
        book.resolveChallenge(id, true, REASON, good);
        _books();
    }

    function test_verdictRejectsDuplicateAndNonValidator() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);

        bytes[] memory dup = _verdict(id, true, REASON, signerPk, signerPk);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.DuplicateSigner.selector, signerAddr));
        book.resolveChallenge(id, true, REASON, dup);

        uint256 stranger = 0xBADBAD;
        bytes[] memory outsider = _verdict(id, true, REASON, signerPk, stranger);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.NotValidator.selector, vm.addr(stranger)));
        book.resolveChallenge(id, true, REASON, outsider);

        bytes[] memory one = new bytes[](1);
        one[0] = _verdict(id, true, REASON, signerPk, pk2)[0];
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.InsufficientSignatures.selector, 1, 2));
        book.resolveChallenge(id, true, REASON, one);

        vm.prank(owner);
        nft.removeValidator(v3);
        bytes[] memory removed = _verdict(id, true, REASON, signerPk, pk3);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.NotValidator.selector, v3));
        book.resolveChallenge(id, true, REASON, removed);

        bytes[] memory three = new bytes[](3);
        bytes[] memory two = _verdict(id, true, REASON, signerPk, pk2);
        three[0] = two[0];
        three[1] = two[1];
        three[2] = _raw(book.hashChallengeVerdict(id, true, REASON), pk2);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.DuplicateSigner.selector, v2));
        book.resolveChallenge(id, true, REASON, three);

        // v3 was removed; signer + v2 still meet the threshold. A third distinct live signer
        // is not required. pk2 is already included, so rebuild with only the two live keys.
        book.resolveChallenge(id, true, REASON, two);
        _books();
    }

    function test_threeDistinctValidators() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        bytes32 digest = book.hashChallengeVerdict(id, true, REASON);
        bytes[] memory sigs = new bytes[](3);
        sigs[0] = _raw(digest, pk3);
        sigs[1] = _raw(digest, signerPk);
        sigs[2] = _raw(digest, pk2);
        book.resolveChallenge(id, true, REASON, sigs);
        assertTrue(book.flagged(id));
    }

    function test_protocolPoolPaysWhenEscrowIsZero() public {
        vm.prank(owner);
        book.setBonds(CHALLENGE_BOND, 0, REWARD);
        vm.prank(owner);
        book.fundPool{value: REWARD}();
        uint256 agent = registry.mint(alice);
        AxVigilCollectible.MintAuth memory a = _auth(agent, alice, 1, 1, 1);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint(a, sigs);
        assertEq(book.escrowed(), 0);
        _challenge(id, challenger);
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk2));
        assertEq(book.poolBalance(), 0);
        assertEq(book.withdrawable(challenger), CHALLENGE_BOND + REWARD);
        assertTrue(book.flagged(id));
        _books();
    }

    function test_shortPoolDoesNotBlockRevocation() public {
        vm.prank(owner);
        book.setBonds(CHALLENGE_BOND, 0, 1 ether);
        vm.prank(owner);
        book.fundPool{value: 0.1 ether}();
        uint256 agent = registry.mint(alice);
        AxVigilCollectible.MintAuth memory a = _auth(agent, alice, 2, 2, 2);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint(a, sigs);
        _challenge(id, challenger);
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, pk2, pk3));
        assertEq(book.poolBalance(), 0.1 ether);
        assertEq(book.withdrawable(challenger), CHALLENGE_BOND);
        assertTrue(book.flagged(id));
        assertFalse(skill.isValid(agent));
        _books();
    }

    function test_zeroChallengeBondStillResolves() public {
        vm.prank(owner);
        book.setBonds(0, OPERATOR_BOND, 0);
        uint256 id = _mint(agentA, alice);
        vm.prank(challenger);
        book.challenge(id, EVIDENCE);
        book.resolveChallenge(id, false, REASON, _verdict(id, false, REASON, signerPk, pk2));
        assertEq(book.withdrawable(treasury), 0);
        _books();
    }

    function test_revert_badBondsAndEmptyEvidence() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.BadBond.selector, 0, OPERATOR_BOND));
        nft.mint(a, sigs);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.BadBond.selector, OPERATOR_BOND - 1, OPERATOR_BOND));
        nft.mint{value: OPERATOR_BOND - 1}(a, sigs);

        uint256 id = _mint(agentA, alice);
        vm.prank(challenger);
        vm.expectRevert(AxVigilChallenge.EmptyEvidence.selector);
        book.challenge{value: CHALLENGE_BOND}(id, "");
        vm.prank(challenger);
        vm.expectRevert(abi.encodeWithSelector(AxVigilChallenge.BadBond.selector, 1, CHALLENGE_BOND));
        book.challenge{value: 1}(id, EVIDENCE);
    }

    function test_windowZeroFinalizesInsideMint() public {
        vm.prank(owner);
        book.setChallengeWindow(0);
        vm.prank(owner);
        book.setBonds(CHALLENGE_BOND, OPERATOR_BOND, REWARD);
        uint256 agent = registry.mint(alice);
        AxVigilCollectible.MintAuth memory a = _auth(agent, alice, 0, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint(a, sigs);
        assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Final));
        assertTrue(book.record(id).finalized);
        assertTrue(skill.isValid(agent));
        assertEq(address(book).balance, 0);
        vm.expectRevert(AxVigilChallenge.AlreadyFinal.selector);
        book.challenge{value: CHALLENGE_BOND}(id, EVIDENCE);
        vm.expectRevert(AxVigilChallenge.AlreadyFinal.selector);
        book.finalize(id);
    }

    function test_secondSolveStaysValidWhenFirstIsSlashed() public {
        uint256 first = _mint(agentA, alice);
        uint256 second = _mint(agentA, alice);
        _challenge(first, challenger);
        book.resolveChallenge(first, true, REASON, _verdict(first, true, REASON, signerPk, pk2));
        assertFalse(skill.isValid(agentA));
        assertEq(skill.totalSolves(agentA), 1);
        vm.warp(block.timestamp + WINDOW);
        book.finalize(second);
        assertTrue(skill.isValid(agentA));
        assertEq(skill.solvesOf(agentA, 0), 1);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 1, 1, 1);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint{value: OPERATOR_BOND}(a, sigs);
        _books();
    }

    function test_adminRevokeDoesNotStickTheBond() public {
        uint256 id = _mint(agentA, alice);
        _challenge(id, challenger);
        vm.prank(owner);
        skill.revoke(agentA, "admin");
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk2));
        assertEq(book.withdrawable(challenger), CHALLENGE_BOND + OPERATOR_BOND);
        assertFalse(skill.isValid(agentA));
        _books();
    }

    function test_reentrancyOnWithdrawDoesNotDoublePay() public {
        uint256 id = _mint(agentA, alice);
        BondThief thief = new BondThief(book);
        vm.deal(address(thief), 5 ether);
        uint256 start = address(thief).balance;
        thief.attack{value: CHALLENGE_BOND}(id, EVIDENCE);
        book.resolveChallenge(id, true, REASON, _verdict(id, true, REASON, signerPk, pk2));
        thief.pull();
        assertEq(thief.calls(), 1);
        // The test contract funded the bond; the thief is paid that bond back plus the escrow, once.
        assertEq(address(thief).balance, start + CHALLENGE_BOND + OPERATOR_BOND);
        assertEq(address(book).balance, 0);
        _books();
    }

    function test_pauseBlocksMintNotChallenge() public {
        uint256 id = _mint(agentA, alice);
        vm.prank(owner);
        nft.pause();
        _challenge(id, challenger);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 1, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        vm.expectRevert();
        nft.mint{value: OPERATOR_BOND}(a, sigs);
        vm.prank(owner);
        nft.unpause();
    }

    function test_submissionStillSingleUseAndThreshold() public {
        uint256 id = _mint(agentA, alice);
        bytes32 sub = book.submissionHashOf(id);
        assertTrue(nft.submissionUsed(sub));
        AxVigilCollectible.MintAuth memory again = _auth(agentA, alice, 0, 0, 0);
        again.submissionHash = sub;
        bytes[] memory againSigs = _pair(again, pk2, pk3);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.SubmissionUsed.selector);
        nft.mint{value: OPERATOR_BOND}(again, againSigs);

        AxVigilCollectible.MintAuth memory solo = _auth(agentA, alice, 1, 1, 1);
        bytes memory one = _sign(solo, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.ThresholdRequired.selector);
        nft.mint{value: OPERATOR_BOND}(solo, one);
    }

    function test_onMintOnlyCollectible_andBookSetOnce() public {
        vm.expectRevert(AxVigilChallenge.NotCollectible.selector);
        book.onMint(1, agentA, 0, bytes32("x"), alice);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice));
        nft.setChallengeBook(address(book));

        vm.prank(owner);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.setChallengeBook(address(0xBEEF));

        uint256 id = _mint(agentA, alice);
        vm.prank(owner);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.setChallengeBook(address(0xBEEF));
        assertGt(id, 0);
    }

    function test_reclaimPoolCannotTouchEscrow() public {
        vm.prank(owner);
        book.fundPool{value: 1 ether}();
        uint256 id = _mint(agentA, alice);
        assertEq(book.escrowed(), OPERATOR_BOND);
        uint256 pool = book.poolBalance();
        vm.prank(owner);
        vm.expectRevert(AxVigilChallenge.InvalidParams.selector);
        book.reclaimPool(owner, pool + 1);
        uint256 before = owner.balance;
        vm.prank(owner);
        book.reclaimPool(owner, pool);
        assertEq(owner.balance, before + pool);
        assertEq(book.escrowed(), OPERATOR_BOND);
        assertEq(book.poolBalance(), 0);
        _books();
        id;
    }

    function test_windowCaps() public {
        vm.prank(owner);
        vm.expectRevert(AxVigilChallenge.InvalidParams.selector);
        book.setChallengeWindow(30 days + 1);
        vm.prank(owner);
        vm.expectRevert(AxVigilChallenge.InvalidParams.selector);
        book.setResponseWindow(0);
        vm.prank(owner);
        book.setChallengeWindow(120);
        assertEq(book.challengeWindow(), 120);
    }

    function test_shortDemoWindow() public {
        vm.prank(owner);
        book.setChallengeWindow(120);
        uint256 agent = registry.mint(alice);
        AxVigilCollectible.MintAuth memory a = _auth(agent, alice, 0, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint{value: OPERATOR_BOND}(a, sigs);
        assertEq(book.record(id).readyAt, uint64(block.timestamp + 120));
        vm.warp(block.timestamp + 120);
        book.finalize(id);
        assertTrue(skill.isValid(agent));
    }

    function testFuzz_statusFollowsClock(uint32 window, uint32 elapsed) public {
        window = uint32(bound(window, 1, 7 days));
        elapsed = uint32(bound(elapsed, 0, 14 days));
        vm.prank(owner);
        book.setChallengeWindow(window);
        uint256 agent = registry.mint(alice);
        uint256 id = _mint(agent, alice);
        vm.warp(block.timestamp + elapsed);
        if (elapsed < window) {
            assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
            vm.expectRevert(AxVigilChallenge.ChallengeWindowOpen.selector);
            book.finalize(id);
        } else {
            assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Final));
            book.finalize(id);
            assertTrue(skill.isValid(agent));
        }
        _books();
    }

    function testFuzz_verdictSet(uint8 mask, bytes32 reason, bool upheld) public {
        mask &= 7;
        vm.assume(reason != bytes32(0));
        uint256 agent = registry.mint(alice);
        uint256 id = _mint(agent, alice);
        _challenge(id, challenger);

        uint256[3] memory pks = [signerPk, pk2, pk3];
        uint256 n;
        for (uint256 i; i < 3; ++i) {
            if ((mask & uint8(1 << i)) != 0) n++;
        }
        bytes[] memory sigs = new bytes[](n);
        bytes32 digest = book.hashChallengeVerdict(id, upheld, reason);
        uint256 w;
        for (uint256 i; i < 3; ++i) {
            if ((mask & uint8(1 << i)) == 0) continue;
            sigs[w] = _raw(digest, pks[i]);
            w++;
        }
        if (n >= 2) {
            book.resolveChallenge(id, upheld, reason, sigs);
            if (upheld) {
                assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Revoked));
                assertFalse(skill.isValid(agent));
            } else {
                assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Pending));
            }
        } else {
            vm.expectRevert();
            book.resolveChallenge(id, upheld, reason, sigs);
            assertEq(uint8(book.status(id)), uint8(AxVigilChallenge.RecordStatus.Challenged));
        }
        _books();
    }

    function testFuzz_garbageSignaturesRevert(bytes calldata junk, bool upheld, bytes32 reason) public {
        uint256 agent = registry.mint(alice);
        uint256 id = _mint(agent, alice);
        _challenge(id, challenger);
        bytes[] memory sigs = new bytes[](2);
        sigs[0] = junk;
        sigs[1] = junk.length == 0 ? bytes("x") : junk;
        vm.expectRevert();
        book.resolveChallenge(id, upheld, reason, sigs);
        assertEq(book.bondsHeld(), CHALLENGE_BOND, "failed verdict does not move the bond");
        _books();
    }

    function testFuzz_bondConservation(uint96 opBond, uint96 chBond, uint96 reward, bool uphold, bytes1 salt) public {
        opBond = uint96(bound(opBond, 0, 2 ether));
        chBond = uint96(bound(chBond, 0, 2 ether));
        reward = uint96(bound(reward, 0, 2 ether));
        vm.startPrank(owner);
        book.setBonds(chBond, opBond, reward);
        if (reward != 0) book.fundPool{value: reward}();
        vm.stopPrank();

        uint256 agent = registry.mint(alice);
        AxVigilCollectible.MintAuth memory a = _auth(agent, alice, uint8(salt) % 3, 0, 0);
        bytes[] memory sigs = _pair(a, signerPk, pk2);
        vm.prank(alice);
        uint256 id = nft.mint{value: opBond}(a, sigs);
        _books();

        vm.prank(challenger);
        book.challenge{value: chBond}(id, abi.encodePacked("evidence", salt));
        _books();

        bytes32 reason = keccak256(abi.encodePacked("reason", salt, uphold));
        book.resolveChallenge(id, uphold, reason, _verdict(id, uphold, reason, pk2, pk3));
        _books();

        if (!uphold) {
            vm.warp(book.record(id).readyAt);
            book.finalize(id);
            assertTrue(skill.isValid(agent));
        } else {
            assertFalse(skill.isValid(agent));
            assertTrue(book.flagged(id));
        }
        _books();
        _drain(alice);
        _drain(challenger);
        _drain(treasury);
        _books();
    }
}

/// @dev A recipient that tries to reenter withdraw, finalize, and challenge from the payout.
contract BondThief {
    AxVigilChallenge public book;
    uint256 public calls;

    constructor(AxVigilChallenge book_) {
        book = book_;
    }

    function attack(uint256 tokenId, bytes calldata evidence) external payable {
        book.challenge{value: msg.value}(tokenId, evidence);
    }

    function pull() external {
        book.withdraw();
    }

    receive() external payable {
        calls += 1;
        if (calls == 1) {
            try book.withdraw() {} catch {}
            try book.finalize(1) {} catch {}
            try book.challenge{value: 0}(1, hex"abcd") {} catch {}
        }
    }
}

/// @notice With no challenge book, mint still confirms the skill immediately and rejects ETH.
contract ImmediateFinalityTest is AxVigilBase {
    function setUp() public {
        _deploy([uint256(30), 10, 5, 4, 4], 50);
        registry.mintId(alice, 7);
    }

    function test_mintConfirmsSkillAndStatusIsFinal() public {
        uint256 id = _mint(alice, 7, 0, 0, 0);
        assertEq(nft.status(id), 3);
        assertFalse(nft.flagged(id));
        assertTrue(skill.isValid(7));
        assertEq(skill.totalSolves(7), 1);
        assertTrue(skill.locked(7));
    }

    function test_revert_valueWithoutBook() public {
        AxVigilCollectible.MintAuth memory a = _auth(7, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.deal(alice, 1 ether);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.mint{value: 1}(a, sig);
    }
}
