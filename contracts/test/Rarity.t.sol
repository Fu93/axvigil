// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @dev Fuzz tests on the rarity engine: exact tier counts, no oversupply, staged release.
contract RarityTest is AxVigilBase {
    uint256 internal constant BIG_CAP = 1_000_000;

    /// @dev Mint the whole supply (2 per fresh agent), rotating seed batches every `batchSize`,
    ///      then reveal everything. Pool per token comes from `poolBits`.
    function _mintAndRevealAll(uint256 fuzzSeed, uint256 poolBits, uint256 batchSize) internal {
        uint256 supply = nft.maxSupply();
        bytes32[] memory seeds = new bytes32[](supply / batchSize + 2);
        seeds[0] = SEED; // batch 1 committed in _deploy
        uint256 agent;
        for (uint256 i; i < supply; ++i) {
            if (i > 0 && i % batchSize == 0) {
                bytes32 s = keccak256(abi.encode(fuzzSeed, i));
                seeds[nft.batchCount()] = s;
                vm.prank(owner);
                nft.commitSeed(keccak256(abi.encodePacked(s)));
            }
            if (i % 2 == 0) agent = registry.mint(alice);
            uint8 pool = uint8((poolBits >> (i % 256)) & 1);
            vm.roll(block.number + 1); // vary block entropy
            vm.prevrandao(keccak256(abi.encode(fuzzSeed, "rand", i)));
            _mint(alice, agent, uint8(i % 3), 0, pool);
        }
        vm.startPrank(owner);
        for (uint32 b = 1; b <= nft.batchCount(); ++b) {
            nft.revealSeed(b, seeds[b - 1]);
        }
        vm.stopPrank();
        nft.revealTokens(type(uint256).max);
        assertEq(nft.nextToReveal(), supply + 1, "all revealed");
    }

    /// @dev Walk tokens in draw order and check counts + staged release bounds.
    function _checkDistribution() internal view {
        uint256 supply = nft.maxSupply();
        uint256[5] memory seen;
        for (uint256 id = 1; id <= supply; ++id) {
            uint8 tier = nft.tierOf(id);
            seen[tier] += 1;
            uint256 stage = ((id - 1) * 4) / supply;
            assertLe(seen[3], (nft.tierTotal(3) * (stage + 1)) / 4, "legendary released too early");
            assertLe(seen[4], (nft.tierTotal(4) * (stage + 1)) / 4, "hidden released too early");
        }
        uint256 sum;
        for (uint256 t; t < 5; ++t) {
            assertEq(seen[t], nft.tierTotal(t), "tier count exact");
            assertEq(nft.drawnOf(t), nft.tierTotal(t), "drawn counter exact");
            sum += seen[t];
        }
        assertEq(sum, supply);
        assertEq(nft.totalMinted(), supply);
    }

    function _assertSoldOut() internal {
        uint256 agent = registry.mint(bob);
        vm.prank(owner);
        nft.commitSeed(keccak256("late"));
        AxVigilCollectible.MintAuth memory a = _auth(agent, bob, 0, 0, 0);
        bytes memory sig = _sign(a, signerPk);
        vm.prank(bob);
        vm.expectRevert(AxVigilCollectible.SoldOut.selector);
        nft.mint(a, sig);
    }

    /// Small config: supply 53. Fuzz seeds, pool mix and batch size.
    function testFuzz_smallConfigExactCountsAndStages(uint256 fuzzSeed, uint256 poolBits, uint8 batchRaw) public {
        _deploy([uint256(30), 10, 5, 4, 4], BIG_CAP);
        uint256 batchSize = bound(batchRaw, 1, 60);
        _mintAndRevealAll(fuzzSeed, poolBits, batchSize);
        _checkDistribution();
        _assertSoldOut();
    }

    /// Only LEGENDARY/HIDDEN plus a few commons, all PREMIUM: the strongest pull toward high tiers.
    /// Staged release must still hold.
    function testFuzz_stagedReleaseUnderPremiumPressure(uint256 fuzzSeed) public {
        _deploy([uint256(10), 0, 0, 4, 4], BIG_CAP);
        _mintAndRevealAll(fuzzSeed, type(uint256).max, 5);
        _checkDistribution();
    }

    /// @dev Concrete staged release with only hidden/legendary in the pool: draw order is forced.
    function test_stagedReleaseExactBoundaries() public {
        // supply 8, stages of 2. Stage k releases (k+1) hidden and (k+1) legendary.
        _deploy([uint256(0), 0, 0, 4, 4], BIG_CAP);
        uint256[5] memory av = nft.availableNow();
        assertEq(av[3], 1);
        assertEq(av[4], 1);
        _mintAndRevealAll(1, 0, 8);
        _checkDistribution();
        // each stage of two draws must have taken exactly one of each
        for (uint256 s; s < 4; ++s) {
            uint8 a = nft.tierOf(2 * s + 1);
            uint8 b = nft.tierOf(2 * s + 2);
            assertTrue(a != b, "one legendary + one hidden per stage");
        }
    }

    /// PREMIUM should beat NORMAL on rare tiers on average (statistical, deterministic seeds).
    function test_premiumImprovesOdds() public {
        uint256 rareNormal;
        uint256 rarePremium;
        for (uint256 run; run < 2; ++run) {
            _deploy([uint256(140), 40, 16, 4, 0], BIG_CAP); // 200 supply
            // first 100 tokens: pool = run (0 NORMAL, 1 PREMIUM)
            uint256 agent;
            for (uint256 i; i < 100; ++i) {
                if (i % 2 == 0) agent = registry.mint(alice);
                vm.roll(block.number + 1);
                _mint(alice, agent, 0, 0, uint8(run));
            }
            vm.prank(owner);
            nft.revealSeed(1, SEED);
            nft.revealTokens(100);
            uint256 rare;
            for (uint256 id = 1; id <= 100; ++id) {
                if (nft.tierOf(id) > 0) rare++;
            }
            if (run == 0) rareNormal = rare;
            else rarePremium = rare;
        }
        assertGt(rarePremium, rareNormal, "premium pulls more non-common tiers");
    }

    /// Full production config (7,777): exact tier counts end to end. Heavy; ~minutes on slow machines.
    function test_productionFullSupply() public {
        _deploy(_production(), BIG_CAP);
        _mintAndRevealAll(42, uint256(keccak256("pools")), 500);
        _checkDistribution();
        _assertSoldOut();
    }
}
