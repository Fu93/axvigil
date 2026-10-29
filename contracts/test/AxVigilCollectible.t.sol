// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

contract AxVigilCollectibleTest is AxVigilBase {
    uint256 internal agentA; // owned by alice

    function setUp() public {
        _deploy(_production(), 100);
        agentA = registry.mint(alice);
    }

    // ------------------------------------------------------------------ mint

    /// @dev Regression: `blockhash(block.number - 1)` must not underflow when
    ///      block.number == 0 (genesis / forge-script simulation / a fresh chain).
    function test_mintAtGenesisBlock() public {
        vm.roll(0);
        uint256 id = _mint(alice, agentA, 0, 0, 0);
        assertEq(id, 1);
        assertEq(nft.ownerOf(1), alice);
    }

    function test_validMint() public {
        uint256 id = _mint(alice, agentA, 1, 1, 1);
        assertEq(id, 1);
        assertEq(nft.ownerOf(1), alice);
        assertEq(nft.totalMinted(), 1);
        assertEq(nft.mintedPerAgent(agentA), 1);
        assertEq(nft.agentOfToken(1), agentA);
        assertEq(nft.vulnClassOf(1), 1);
        AxVigilCollectible.TokenData memory t = nft.tokenData(1);
        assertEq(t.difficulty, 1);
        assertEq(t.pool, 1);
        assertFalse(t.revealed);
        assertEq(t.batchId, 1);
        // same signature also wrote the skill record
        assertTrue(skill.exists(agentA));
        assertEq(skill.solvesOf(agentA, 1), 1);
        assertEq(skill.maxDifficulty(agentA), 1);
        assertTrue(skill.locked(agentA));
        // unrevealed URI until the batch seed is revealed
        assertEq(nft.tokenURI(1), "ipfs://unrevealed");
    }

    function test_mintToDifferentRecipient() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, bob, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice); // alice owns the agent, NFT goes to `to`
        nft.mint(a, sig);
        assertEq(nft.ownerOf(1), bob);
    }

    /// @dev Our digest matches an independent EIP-712 encoding of the SPEC struct.
    function test_eip712DigestMatchesSpec() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 2, 2, 2);
        bytes32 typehash = keccak256(
            "MintAuth(uint256 agentId,address to,uint8 vulnClass,uint8 difficulty,uint8 pool,bytes32 submissionHash,uint256 nonce,uint256 deadline)"
        );
        bytes32 domain = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256("AxVigil"),
                keccak256("1"),
                block.chainid,
                address(nft)
            )
        );
        bytes32 structHash = keccak256(
            abi.encode(
                typehash, a.agentId, a.to, a.vulnClass, a.difficulty, a.pool, a.submissionHash, a.nonce, a.deadline
            )
        );
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domain, structHash));
        assertEq(nft.hashMintAuth(a), digest);
        assertEq(nft.domainSeparator(), domain);
    }

    function test_revert_replayedNonce() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.startPrank(alice);
        nft.mint(a, sig);
        vm.expectRevert(AxVigilCollectible.NonceUsed.selector);
        nft.mint(a, sig);
        vm.stopPrank();
    }

    function test_revert_nonceSharedAcrossAgents() public {
        uint256 agentB = registry.mint(bob);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sigA = _sign(a, signerPk);
        vm.prank(alice);
        nft.mint(a, sigA);
        // a fresh signature for another agent but reusing the nonce is rejected
        AxVigilCollectible.MintAuth memory b = _auth(agentB, bob, 0, 0, 0);
        b.nonce = a.nonce;
        bytes memory sigB = _sign(b, signerPk);
        vm.prank(bob);
        vm.expectRevert(AxVigilCollectible.NonceUsed.selector);
        nft.mint(b, sigB);
    }

    function test_revert_expiredDeadline() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.warp(a.deadline + 1);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.Expired.selector);
        nft.mint(a, sig);
    }

    function test_deadlineInclusive() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.warp(a.deadline);
        vm.prank(alice);
        nft.mint(a, sig);
    }

    function test_revert_wrongSigner() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, 0xBADBAD);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.mint(a, sig);
    }

    function test_revert_tamperedField() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        a.pool = 2; // try to upgrade a basic solve into the legendary pool
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.mint(a, sig);
    }

    function test_revert_malformedSignature() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.mint(a, hex"1234");
    }

    function test_revert_notAgentOwner() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, bob, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(bob);
        vm.expectRevert(AxVigilCollectible.NotAgentOwner.selector);
        nft.mint(a, sig);
    }

    function test_revert_nonexistentAgent() public {
        AxVigilCollectible.MintAuth memory a = _auth(999, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(); // registry ownerOf reverts
        nft.mint(a, sig);
    }

    function test_revert_invalidFields() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 3, 0, 0); // vulnClass out of range
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        nft.mint(a, sig);
    }

    /// @dev The signed pool has to be the difficulty. A basic solve cannot enter the advanced pool.
    function test_revert_poolMustMatchDifficulty() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 1);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilCollectible.PoolDifficultyMismatch.selector, uint8(0), uint8(1)));
        nft.mint(a, sig);
        assertEq(skill.totalSolves(agentA), 0);
        assertEq(nft.mintedPerAgent(agentA), 0);
    }

    function test_legendaryPoolFollowsLegendaryDifficulty() public {
        uint256 id = _mint(alice, agentA, 2, 2, 2);
        assertEq(nft.poolForDifficulty(2), 2);
        assertEq(nft.tokenData(id).pool, 2);
        assertEq(nft.tokenData(id).difficulty, 2);
        assertEq(skill.totalSolves(agentA), 1);
        assertEq(nft.mintedPerAgent(agentA), 1);
    }

    function test_revert_thirdMintPerAgent() public {
        _mint(alice, agentA, 0, 0, 0);
        _mint(alice, agentA, 1, 0, 0);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 2, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint(a, sig);
    }

    /// @dev Quota is bound to the Agent ID tokenId, not the wallet.
    function test_quotaFollowsAgentNotWallet() public {
        _mint(alice, agentA, 0, 0, 0);
        _mint(alice, agentA, 1, 0, 0);
        vm.prank(alice);
        registry.transferFrom(alice, bob, agentA);
        AxVigilCollectible.MintAuth memory a = _auth(agentA, bob, 2, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(bob);
        vm.expectRevert(AxVigilCollectible.AgentQuotaReached.selector);
        nft.mint(a, sig);
    }

    function test_hourlyCap() public {
        vm.prank(owner);
        nft.setHourlyCap(3);
        vm.warp(10 hours); // start of an hour window
        uint256[4] memory agents;
        for (uint256 i; i < 4; ++i) {
            agents[i] = registry.mint(alice);
        }
        for (uint256 i; i < 3; ++i) {
            _mint(alice, agents[i], 0, 0, 0);
        }
        AxVigilCollectible.MintAuth memory a = _auth(agents[3], alice, 0, 0, 0);
        a.deadline = block.timestamp + 2 hours;
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.HourlyCapReached.selector);
        nft.mint(a, sig);

        vm.warp(11 hours); // next window
        vm.prank(alice);
        nft.mint(a, sig);
        assertEq(nft.totalMinted(), 4);
    }

    function test_pause() public {
        vm.prank(owner);
        nft.pause();
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(Pausable.EnforcedPause.selector);
        nft.mint(a, sig);

        vm.prank(owner);
        nft.unpause();
        vm.prank(alice);
        nft.mint(a, sig);
    }

    function test_revert_pauseOnlyOwner() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice));
        nft.pause();
    }

    function test_setSignerRotates() public {
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory oldSig = _sign(a, signerPk);
        uint256 newPk = 0xB0B;
        vm.prank(owner);
        nft.setSigner(vm.addr(newPk));
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.InvalidSignature.selector);
        nft.mint(a, oldSig);

        bytes memory newSig = _sign(a, newPk);
        vm.prank(alice);
        nft.mint(a, newSig);
    }

    function test_revert_setSignerOnlyOwner() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice));
        nft.setSigner(alice);
    }

    // ------------------------------------------------------------------ commit-reveal

    function test_revealFlow() public {
        _mint(alice, agentA, 2, 0, 0);
        vm.prank(owner);
        nft.revealSeed(1, SEED);
        assertEq(nft.currentBatch(), 0, "revealing the open batch closes it");

        assertEq(nft.revealTokens(10), 1);
        AxVigilCollectible.TokenData memory t = nft.tokenData(1);
        assertTrue(t.revealed);
        assertEq(nft.tierOf(1), t.tier);
        assertEq(uint256(t.artId), uint256(t.tier) * 100_000 + 2 * 10_000 + 0);
        assertEq(nft.tokenURI(1), string.concat("ipfs://art/", vm.toString(uint256(t.artId))));
        assertEq(nft.nextToReveal(), 2);
    }

    function test_revert_mintWithoutOpenBatch() public {
        vm.prank(owner);
        nft.revealSeed(1, SEED); // closes batch 1
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(AxVigilCollectible.NoOpenBatch.selector);
        nft.mint(a, sig);
    }

    function test_revert_badSeed() public {
        vm.prank(owner);
        vm.expectRevert(AxVigilCollectible.BadSeed.selector);
        nft.revealSeed(1, keccak256("wrong"));
    }

    function test_revert_doubleReveal() public {
        vm.startPrank(owner);
        nft.revealSeed(1, SEED);
        vm.expectRevert(AxVigilCollectible.AlreadyRevealed.selector);
        nft.revealSeed(1, SEED);
        vm.stopPrank();
    }

    function test_revealStopsAtUnrevealedBatch() public {
        uint256 agentB = registry.mint(alice);
        _mint(alice, agentA, 0, 0, 0); // batch 1
        bytes32 seed2 = keccak256("seed-2");
        vm.prank(owner);
        nft.commitSeed(keccak256(abi.encodePacked(seed2))); // batch 2, closes batch 1 for minting
        _mint(alice, agentB, 0, 0, 0); // batch 2

        vm.prank(owner);
        nft.revealSeed(1, SEED);
        assertEq(nft.revealTokens(10), 1, "token 2 waits for batch 2 seed");
        assertFalse(nft.tokenData(2).revealed);

        vm.prank(owner);
        nft.revealSeed(2, seed2);
        assertEq(nft.revealTokens(10), 1);
        assertTrue(nft.tokenData(2).revealed);
    }

    function test_revert_tierOfUnrevealed() public {
        _mint(alice, agentA, 0, 0, 0);
        vm.expectRevert(bytes("not revealed"));
        nft.tierOf(1);
    }

    function test_provenanceSetOnce() public {
        vm.startPrank(owner);
        nft.setProvenanceHash(keccak256("art-set"));
        assertEq(nft.provenanceHash(), keccak256("art-set"));
        vm.expectRevert(AxVigilCollectible.ProvenanceAlreadySet.selector);
        nft.setProvenanceHash(keccak256("other"));
        vm.stopPrank();
    }

    function test_revert_commitOnlyOwner() public {
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, alice));
        nft.commitSeed(keccak256("x"));
    }

    // ------------------------------------------------------------------ config

    function test_productionConfig() public view {
        assertEq(nft.maxSupply(), 7777);
        assertEq(nft.drawableSupply(), 7773, "hidden is reserved, not minted");
        assertEq(nft.tierTotal(0), 5444);
        assertEq(nft.tierTotal(1), 1555);
        assertEq(nft.tierTotal(2), 622);
        assertEq(nft.tierTotal(3), 152);
        assertEq(nft.tierTotal(4), 4);
        uint256[5] memory av = nft.availableNow();
        assertEq(av[3], 38, "legendary stage 1");
        assertEq(av[4], 0, "hidden is not in the random draw");
    }

    function test_revert_unsafeStagedConfig() public {
        // Drawable supply is 1 (the single legendary). Four stages cannot open on one token.
        uint256[5] memory bad = [uint256(0), 0, 0, 1, 3];
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), signerAddr, owner, bad, 10
        );
    }

    function test_revert_tinySupply() public {
        uint256[5] memory bad = [uint256(3), 0, 0, 0, 0];
        vm.expectRevert(AxVigilCollectible.InvalidParams.selector);
        new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), signerAddr, owner, bad, 10
        );
    }

    function test_revertedMintRollsBackSkillAndQuota() public {
        // If the skill record is revoked, the whole mint reverts (nothing half-applied).
        _mint(alice, agentA, 0, 0, 0);
        vm.prank(owner);
        skill.revoke(agentA, "cheating");
        AxVigilCollectible.MintAuth memory a = _auth(agentA, alice, 1, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(AxVigilSkill.AgentRevoked.selector, agentA));
        nft.mint(a, sig);
        assertEq(nft.mintedPerAgent(agentA), 1);
        assertFalse(nft.nonceUsed(a.nonce));
    }
}
