// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {AxVigilZKVerifier, ISP1Verifier} from "../src/AxVigilZKVerifier.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";

contract MockSP1Verifier is ISP1Verifier {
    bytes32 public expectedVKey;

    constructor(bytes32 _vKey) {
        expectedVKey = _vKey;
    }

    function verifyProof(
        bytes32 programVKey,
        bytes calldata publicValues,
        bytes calldata proofBytes
    ) external view override {
        require(programVKey == expectedVKey, "WRONG_VKEY");
        require(publicValues.length > 0, "EMPTY_PUBLIC_VALUES");
        if (keccak256(proofBytes) == keccak256("INVALID_PROOF")) {
            revert("SP1_VERIFY_FAILURE");
        }
    }
}

contract AxVigilZKVerifierTest is Test {
    MockAgentID internal agentRegistry;
    AxVigilSkill internal skill;
    MockSP1Verifier internal mockSP1;
    AxVigilZKVerifier internal zkVerifier;

    address internal admin = address(0xAA);
    address internal alice = address(0x11);
    address internal bob = address(0x22);

    uint256 internal constant ALICE_AGENT_ID = 42;
    bytes32 internal constant CRUCIBLE_VKEY = keccak256("AxVigil-Crucible-zkVM-v1");

    function setUp() public {
        vm.startPrank(admin);

        // 1. Deploy Space ID Mock Registry & mint Agent ID 42 to Alice
        agentRegistry = new MockAgentID();
        agentRegistry.mintId(alice, ALICE_AGENT_ID);

        // 2. Deploy AxVigilSkill ERC-5192 SBT
        skill = new AxVigilSkill(IAgentRegistry(address(agentRegistry)), admin);

        // 3. Deploy Mock SP1 Verifier & AxVigilZKVerifier
        mockSP1 = new MockSP1Verifier(CRUCIBLE_VKEY);
        zkVerifier = new AxVigilZKVerifier(
            address(mockSP1),
            CRUCIBLE_VKEY,
            address(agentRegistry),
            address(skill)
        );

        // 4. Authorize zkVerifier as MINTER_ROLE on the Skill contract
        skill.grantRole(skill.MINTER_ROLE(), address(zkVerifier));

        vm.stopPrank();
    }

    function _encodePublicValues(
        uint256 agentId,
        bytes32 challengeId,
        bytes32 patchCommitment,
        uint8 vulnClass,
        uint8 difficulty,
        uint8 checksBitmap,
        bool passed
    ) internal view returns (bytes memory) {
        AxVigilZKVerifier.ZKPublicValues memory pv = AxVigilZKVerifier.ZKPublicValues({
            agentId: agentId,
            challengeId: challengeId,
            patchCommitment: patchCommitment,
            originalCodeHash: keccak256("original_code"),
            vulnClass: vulnClass,
            difficulty: difficulty,
            checksBitmap: checksBitmap,
            timestamp: uint64(block.timestamp),
            passed: passed
        });
        return abi.encode(pv);
    }

    function test_validZkProofTrustlesslyMintsSkillRecord() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID,
            challengeId,
            patchCommitment,
            1, // vulnClass
            2, // difficulty: Legendary
            31,
            true
        );
        bytes memory validProof = bytes("valid_groth16_snark_proof");

        // Alice trustlessly verifies proof and records capability without revealing patch code
        vm.prank(alice);
        zkVerifier.verifyAndRecord(publicValues, validProof);

        // Verify Skill SBT on-chain state
        uint32 solves = skill.solvesOf(ALICE_AGENT_ID, 1);
        uint8 maxDiff = skill.maxDifficulty(ALICE_AGENT_ID);
        assertTrue(skill.exists(ALICE_AGENT_ID), "Skill record must exist");
        assertEq(solves, 1, "Solve count mismatch");
        assertEq(maxDiff, 2, "Difficulty mismatch");

        // Verify anti-replay nullifier marked
        bytes32 nullifier = zkVerifier.computeNullifier(ALICE_AGENT_ID, challengeId);
        assertTrue(zkVerifier.nullifiers(nullifier), "Nullifier not set");
    }

    function test_revert_invalidZkProof() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment, 1, 1, 31, true
        );
        bytes memory badProof = bytes("INVALID_PROOF");

        vm.prank(alice);
        vm.expectRevert("SP1_VERIFY_FAILURE");
        zkVerifier.verifyAndRecord(publicValues, badProof);
    }

    function test_revert_incompleteChecks() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        // checksBitmap = 7 (0x07) -> only first 3 checks passed, missing patch limits!
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment, 1, 1, 7, true
        );
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilZKVerifier.IncompleteChecks.selector, 7));
        zkVerifier.verifyAndRecord(publicValues, validProof);
    }

    function test_verifyAndRecord_success_coreChecksBitmap15() public {
        bytes32 challengeId = keccak256("reentrancy-vault-core-only");
        bytes32 patchCommitment = keccak256("diff: +reentrancyGuard;");
        // checksBitmap = 15 (0x0F) -> 4 core differential checks satisfied (no invariant suite)
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment, 0, 1, 15, true
        );
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        zkVerifier.verifyAndRecord(publicValues, validProof);

        assertTrue(zkVerifier.nullifiers(zkVerifier.computeNullifier(ALICE_AGENT_ID, challengeId)));
        uint32 solves = skill.solvesOf(ALICE_AGENT_ID, 0);
        assertEq(solves, 1);
        assertEq(skill.totalSolves(ALICE_AGENT_ID), 1);
    }

    function test_revert_solveFailed() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: bad_patch;");
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment, 1, 1, 31, false
        );
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        vm.expectRevert(AxVigilZKVerifier.SolveFailed.selector);
        zkVerifier.verifyAndRecord(publicValues, validProof);
    }

    function test_revert_notAgentOwner() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment, 1, 1, 31, true
        );
        bytes memory validProof = bytes("valid_proof");

        // Bob tries to claim Alice's Agent ID solve
        vm.prank(bob);
        vm.expectRevert(AxVigilZKVerifier.NotAgentOwner.selector);
        zkVerifier.verifyAndRecord(publicValues, validProof);
    }

    function test_revert_replayProof_sameChallengeDifferentPatch() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment1 = keccak256("diff: +nonReentrant;");
        bytes memory publicValues1 = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment1, 1, 1, 31, true
        );
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        zkVerifier.verifyAndRecord(publicValues1, validProof);

        // Attacker changes patch whitespace or comment -> patchCommitment2
        bytes32 patchCommitment2 = keccak256("diff: +nonReentrant; // extra comment");
        bytes memory publicValues2 = _encodePublicValues(
            ALICE_AGENT_ID, challengeId, patchCommitment2, 1, 1, 31, true
        );

        // Must still revert because nullifier binds (agentId, challengeId)
        vm.prank(alice);
        vm.expectRevert(AxVigilZKVerifier.AlreadySubmitted.selector);
        zkVerifier.verifyAndRecord(publicValues2, validProof);
    }

    function test_revert_maxSolvesReached() public {
        bytes memory validProof = bytes("valid_proof");

        // Solve 1: Reentrancy (class 0)
        bytes memory pv1 = _encodePublicValues(
            ALICE_AGENT_ID, keccak256("ch1"), keccak256("p1"), 0, 1, 31, true
        );
        vm.prank(alice);
        zkVerifier.verifyAndRecord(pv1, validProof);

        // Solve 2: Price Manipulation (class 1)
        bytes memory pv2 = _encodePublicValues(
            ALICE_AGENT_ID, keccak256("ch2"), keccak256("p2"), 1, 1, 31, true
        );
        vm.prank(alice);
        zkVerifier.verifyAndRecord(pv2, validProof);

        // Alice currently has 2 solves (max lifetime limit)
        assertEq(skill.totalSolves(ALICE_AGENT_ID), 2);

        // Solve 3: Access Control (class 2) -> must revert with MaxSolvesReached!
        bytes memory pv3 = _encodePublicValues(
            ALICE_AGENT_ID, keccak256("ch3"), keccak256("p3"), 2, 1, 31, true
        );
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilZKVerifier.MaxSolvesReached.selector, ALICE_AGENT_ID, 2));
        zkVerifier.verifyAndRecord(pv3, validProof);
    }
}
