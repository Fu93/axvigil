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
        uint8 checksBitmap,
        bool passed
    ) internal view returns (bytes memory) {
        AxVigilZKVerifier.ZKPublicValues memory pv = AxVigilZKVerifier.ZKPublicValues({
            agentId: agentId,
            challengeId: challengeId,
            patchCommitment: patchCommitment,
            originalCodeHash: keccak256("original_code"),
            checksBitmap: checksBitmap,
            timestamp: uint64(block.timestamp),
            passed: passed
        });
        return abi.encode(pv);
    }

    function test_validZkProofTrustlesslyMintsSkillRecord() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 31, true);
        bytes memory validProof = bytes("valid_groth16_snark_proof");

        // Alice trustlessly verifies proof and records capability without revealing patch code
        vm.prank(alice);
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);

        // Verify Skill SBT on-chain state
        uint32 solves = skill.solvesOf(ALICE_AGENT_ID, 1);
        uint8 maxDiff = skill.maxDifficulty(ALICE_AGENT_ID);
        assertTrue(skill.exists(ALICE_AGENT_ID), "Skill record must exist");
        assertEq(solves, 1, "Solve count mismatch");
        assertEq(maxDiff, 1, "Difficulty mismatch");

        // Verify anti-replay nullifier marked
        bytes32 nullifier = keccak256(abi.encodePacked(challengeId, patchCommitment));
        assertTrue(zkVerifier.nullifiers(nullifier), "Nullifier not set");
    }

    function test_revert_invalidZkProof() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 31, true);
        bytes memory badProof = bytes("INVALID_PROOF");

        vm.prank(alice);
        vm.expectRevert("SP1_VERIFY_FAILURE");
        zkVerifier.verifyAndRecord(publicValues, badProof, 1, 1);
    }

    function test_revert_incompleteChecks() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        // checksBitmap = 15 (0x0F) -> 4 checks passed, 1 check missing!
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 15, true);
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilZKVerifier.IncompleteChecks.selector, 15));
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);
    }

    function test_revert_solveFailed() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: bad_patch;");
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 31, false);
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        vm.expectRevert(AxVigilZKVerifier.SolveFailed.selector);
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);
    }

    function test_revert_notAgentOwner() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 31, true);
        bytes memory validProof = bytes("valid_proof");

        // Bob tries to claim Alice's Agent ID solve
        vm.prank(bob);
        vm.expectRevert(AxVigilZKVerifier.NotAgentOwner.selector);
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);
    }

    function test_revert_replayProof() public {
        bytes32 challengeId = keccak256("reentrancy-vault-001");
        bytes32 patchCommitment = keccak256("diff: +nonReentrant;");
        bytes memory publicValues = _encodePublicValues(ALICE_AGENT_ID, challengeId, patchCommitment, 31, true);
        bytes memory validProof = bytes("valid_proof");

        vm.prank(alice);
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);

        // Replaying same proof / commitment
        vm.prank(alice);
        vm.expectRevert(AxVigilZKVerifier.AlreadySubmitted.selector);
        zkVerifier.verifyAndRecord(publicValues, validProof, 1, 1);
    }
}
