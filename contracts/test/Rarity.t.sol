// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @dev Fuzz tests on the rarity engine: exact tier counts, no oversupply, staged release.
contract RarityTest is AxVigilBase {
    uint256 internal constant BIG_CAP = 1_000_000;

    /// @dev Mint the drawable supply (2 per fresh agent), rotating seed batches every `batchSize`,
    ///      then reveal everything. Pool is the difficulty and comes from `poolBits`.
    function _mintAndRevealAll(uint256 fuzzSeed, uint256 poolBits, uint256 batchSize) internal {
        uint256 supply = nft.drawableSupply();
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
            uint8 pool = uint8(uint256(keccak256(abi.encode(poolBits, i))) % 3);
            vm.roll(block.number + 1); // vary block entropy
            vm.prevrandao(keccak256(abi.encode(fuzzSeed, "rand", i)));
            _mint(alice, agent, uint8(i % 3), pool, pool);
        }
        vm.startPrank(owner);
        for (uint32 b = 1; b <= nft.batchCount(); ++b) {
            nft.revealSeed(b, seeds[b - 1]);
        }
        vm.stopPrank();
        nft.revealTokens(type(uint256).max);
        assertEq(nft.nextToReveal(), supply + 1, "all revealed");
    }

    /// @dev Full mint of the public supply. Quotas are ceilings. Hidden may appear only on
    ///      pool 2, and only within its quota. A Hidden hit leaves one public piece unminted.
    function _checkDistribution() internal view {
        uint256 supply = nft.drawableSupply();
        uint256[5] memory seen;
        uint256 pool2;
        uint256 hiddenOnPool2;
        for (uint256 id = 1; id <= supply; ++id) {
            AxVigilCollectible.TokenData memory td = nft.tokenData(id);
            assertTrue(td.revealed, "mint cap keeps every token revealable");
            seen[td.tier] += 1;
            if (td.pool != nft.POOL_LEGENDARY()) {
                assertLt(td.tier, 4, "pools 0 and 1 never draw hidden");
            } else {
                pool2 += 1;
                if (td.tier == 4) hiddenOnPool2 += 1;
            }
            uint256 stage = ((id - 1) * 4) / supply;
            assertLe(seen[3], (nft.tierTotal(3) * (stage + 1)) / 4, "legendary released too early");
        }
        uint256 sum;
        for (uint256 t; t < 5; ++t) {
            assertLe(seen[t], nft.tierTotal(t), "quota exceeded");
            assertEq(nft.drawnOf(t), seen[t], "drawn counter");
            sum += seen[t];
        }
        assertEq(sum, supply);
        assertEq(nft.totalMinted(), supply);
        assertEq(hiddenOnPool2, seen[4]);
        // When the pool-2 sample is large enough that even all 4 Hidden pieces are under 0.30%,
        // the realized rate must be too. The per-draw probability is checked separately and does not drift.
        if (pool2 > 0 && nft.tierTotal(4) * 10_000 < pool2 * nft.MAX_HIDDEN_CHANCE_BPS()) {
            assertLt(hiddenOnPool2 * 10_000, pool2 * nft.MAX_HIDDEN_CHANCE_BPS(), "pool 2 hidden rate");
        }
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

    /// Commons plus staged legendary. Hidden may be rolled only when the token's pool is 2.
    function testFuzz_stagedReleaseUnderLegendaryPressure(uint256 fuzzSeed) public {
        _deploy([uint256(10), 0, 0, 4, 4], BIG_CAP);
        _mintAndRevealAll(fuzzSeed, type(uint256).max, 5);
        _checkDistribution();
    }

    /// @dev Pool 0 cannot roll Hidden, so a legendary-only public supply reveals as legendary.
    function test_pool0NeverDrawsHidden() public {
        _deploy([uint256(0), 0, 0, 8, 4], BIG_CAP);
        assertEq(nft.drawableSupply(), 8);
        assertEq(nft.maxSupply(), 12);
        uint256[5] memory av = nft.availableNow();
        assertEq(av[3], 2, "first legendary stage");
        assertEq(av[4], 0, "hidden is not in the weighted ladder");
        uint256 agent;
        for (uint256 i; i < 8; ++i) {
            if (i % 2 == 0) agent = registry.mint(alice);
            vm.roll(block.number + 1);
            _mint(alice, agent, 0, 0, 0);
        }
        vm.prank(owner);
        nft.revealSeed(1, SEED);
        nft.revealTokens(8);
        assertEq(nft.drawnOf(4), 0);
        assertEq(nft.drawnOf(3), 8);
        assertEq(nft.tierOf(1), 3);
        assertEq(nft.tierOf(8), 3);
        assertEq(nft.hiddenRemaining(), 4, "unrolled hidden stays unminted");
    }

    /// Same entropy, three pools. Higher pools pull more non-common tiers, and none is certain.
    function test_poolLadderImprovesOdds() public {
        uint256[3] memory rare;
        for (uint256 run; run < 3; ++run) {
            _deploy([uint256(140), 40, 16, 4, 4], BIG_CAP); // 200 drawable, 4 hidden reserved
            uint256 agent;
            for (uint256 i; i < 100; ++i) {
                if (i % 2 == 0) agent = registry.mint(alice);
                vm.roll(1_000 + run * 10_000 + i + 1);
                vm.prevrandao(keccak256(abi.encode("odds", i)));
                _mint(alice, agent, 0, uint8(run), uint8(run));
            }
            vm.prank(owner);
            nft.revealSeed(1, SEED);
            nft.revealTokens(100);
            uint256 n;
            for (uint256 id = 1; id <= 100; ++id) {
                uint8 tier = nft.tierOf(id);
                if (run < 2) assertLt(tier, 4, "basic and advanced never draw hidden");
                if (tier > 0 && tier < 4) n++;
            }
            rare[run] = n;
            assertLt(n, 100, "a higher pool is not a guarantee");
            if (run < 2) assertEq(nft.drawnOf(4), 0);
            else assertLe(nft.drawnOf(4), 4);
        }
        assertGe(rare[1], rare[0], "advanced beats basic");
        assertGt(rare[2], rare[1], "legendary beats advanced");
    }

    /// Exact stage-0 weights for the production quotas. Documents the ladder and that hidden is 0.
    function test_productionInitialWeights() public {
        _deploy(_production(), BIG_CAP);
        // Stage 0 releases legendaryTotal/4 = 38. Hidden is not released.
        uint256[4] memory released = [uint256(5444), 1555, 622, 38];
        uint8[3] memory pools = [nft.POOL_BASIC(), nft.POOL_ADVANCED(), nft.POOL_LEGENDARY()];
        // BASIC [1,1,1,1], ADVANCED [1,2,4,8], LEGENDARY [1,3,8,16]
        uint256[3] memory expectedSum = [uint256(7659), 11346, 15693];
        uint256[3] memory expectedLegendary = [uint256(38), 304, 608];
        uint256[3] memory legBps;
        uint256[3] memory commonBps;
        for (uint256 p; p < 3; ++p) {
            uint256 total;
            uint256 legendaryW;
            uint256 commonW;
            for (uint256 t; t < 4; ++t) {
                uint256 w = released[t] * nft.weightMultiplier(pools[p], t);
                total += w;
                if (t == 0) commonW = w;
                if (t == 3) legendaryW = w;
            }
            assertEq(nft.weightMultiplier(pools[p], 4), 0, "hidden multiplier");
            assertEq(total, expectedSum[p], "weight sum");
            assertEq(legendaryW, expectedLegendary[p], "legendary weight");
            assertLt(legendaryW, total, "legendary is not guaranteed");
            assertLt(commonW, total, "common is not guaranteed");
            legBps[p] = legendaryW * 1_000_000 / total;
            commonBps[p] = commonW * 1_000_000 / total;
        }
        assertGt(legBps[1], legBps[0]);
        assertGt(legBps[2], legBps[1]);
        assertLt(commonBps[2], commonBps[1]);
        assertLt(commonBps[1], commonBps[0]);
        // ~0.50% / 2.68% / 3.87% of the stage-0 draw is legendary.
        assertEq(legBps[0], 4_961);
        assertEq(legBps[1], 26_793);
        assertEq(legBps[2], 38_743);
    }

    /// The Hidden roll is a fixed residue check. It does not look at remaining counts.
    function test_hiddenChanceIsFixedAndBelowPointThreePercent() public {
        _deploy(_production(), BIG_CAP);
        assertEq(nft.HIDDEN_CHANCE_BPS(), 25);
        assertLt(nft.HIDDEN_CHANCE_BPS(), nft.MAX_HIDDEN_CHANCE_BPS());
        assertEq(nft.MAX_HIDDEN_CHANCE_BPS(), 30);
        uint256 hits2;
        uint256 hitsOther;
        for (uint256 i; i < nft.HIDDEN_CHANCE_DENOM(); ++i) {
            if (nft.hiddenRollHits(i, nft.POOL_LEGENDARY())) hits2 += 1;
            if (nft.hiddenRollHits(i, nft.POOL_BASIC())) hitsOther += 1;
            if (nft.hiddenRollHits(i, nft.POOL_ADVANCED())) hitsOther += 1;
        }
        assertEq(hits2, 25, "exactly 0.25% of residues");
        assertEq(hitsOther, 0, "pools 0 and 1 never hit");
        // Same predicate at the top of the uint256 range: still only the low residue matters.
        assertEq(nft.hiddenRollHits(type(uint256).max, 2), (type(uint256).max % 10_000) < 25);
    }

    /// Full production config: 7,773 public mints. Hidden may replace a few of them. Heavy.
    function test_productionFullSupply() public {
        _deploy(_production(), BIG_CAP);
        _mintAndRevealAll(42, uint256(keccak256("pools")), 500);
        _checkDistribution();
        _assertSoldOut();
    }
}
