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

    /// @dev Walk tokens in draw order and check counts + staged legendary release.
    ///      HIDDEN is reserved: none of it is drawn, and the other tiers fill exactly.
    function _checkDistribution() internal view {
        uint256 supply = nft.drawableSupply();
        uint256[5] memory seen;
        for (uint256 id = 1; id <= supply; ++id) {
            uint8 tier = nft.tierOf(id);
            seen[tier] += 1;
            assertLt(tier, 4, "hidden must not be drawn");
            uint256 stage = ((id - 1) * 4) / supply;
            assertLe(seen[3], (nft.tierTotal(3) * (stage + 1)) / 4, "legendary released too early");
        }
        uint256 sum;
        for (uint256 t; t < 4; ++t) {
            assertEq(seen[t], nft.tierTotal(t), "tier count exact");
            assertEq(nft.drawnOf(t), nft.tierTotal(t), "drawn counter exact");
            sum += seen[t];
        }
        assertEq(seen[4], 0);
        assertEq(nft.drawnOf(4), 0, "hidden quota is not consumed by the draw");
        assertEq(sum, supply);
        assertEq(nft.totalMinted(), supply);
        assertLt(nft.totalMinted(), nft.maxSupply());
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

    /// Commons plus staged legendary, with hidden reserved: the draw still fills the public quotas
    /// and never touches hidden, including when every token uses the strongest pool.
    function testFuzz_stagedReleaseUnderLegendaryPressure(uint256 fuzzSeed) public {
        _deploy([uint256(10), 0, 0, 4, 4], BIG_CAP);
        _mintAndRevealAll(fuzzSeed, type(uint256).max, 5);
        _checkDistribution();
    }

    /// @dev Legendary is staged across the drawable supply. Hidden is configured but never drawn.
    function test_stagedReleaseLeavesHiddenUndrawn() public {
        // 8 legendary drawable, 4 hidden reserved. Stage 0 releases 8/4 = 2 legendary.
        _deploy([uint256(0), 0, 0, 8, 4], BIG_CAP);
        assertEq(nft.drawableSupply(), 8);
        assertEq(nft.maxSupply(), 12);
        uint256[5] memory av = nft.availableNow();
        assertEq(av[3], 2, "first legendary stage");
        assertEq(av[4], 0, "hidden weight is zero");
        _mintAndRevealAll(1, 0, 8);
        _checkDistribution();
        assertEq(nft.tierOf(1), 3);
        assertEq(nft.tierOf(8), 3);
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
                assertLt(tier, 4, "hidden stays out");
                if (tier > 0) n++;
            }
            rare[run] = n;
            assertLt(n, 100, "a higher pool is not a guarantee");
            assertEq(nft.drawnOf(4), 0);
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

    /// Full production config: 7,773 drawable tokens, 4 hidden reserved. Heavy.
    function test_productionFullSupply() public {
        _deploy(_production(), BIG_CAP);
        _mintAndRevealAll(42, uint256(keccak256("pools")), 500);
        _checkDistribution();
        _assertSoldOut();
    }
}
