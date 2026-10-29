// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @dev Random sequences of mints, seed commits/reveals, token reveals and time jumps.
contract Handler is Test {
    AxVigilCollectible public nft;
    MockAgentID public registry;
    address public owner;
    uint256 public signerPk;

    uint256 public nonce = 1;
    bytes32[] public seeds; // index = batchId - 1
    uint256[] public agents;

    constructor(AxVigilCollectible nft_, MockAgentID registry_, address owner_, uint256 pk, bytes32 firstSeed) {
        nft = nft_;
        registry = registry_;
        owner = owner_;
        signerPk = pk;
        seeds.push(firstSeed);
    }

    function mint(uint256 agentSeed, uint8 vc, uint8 diff, bool premium) external {
        // reuse an existing agent sometimes, so the per-agent quota is exercised
        uint256 agentId;
        if (agents.length > 0 && agentSeed % 3 == 0) {
            agentId = agents[agentSeed % agents.length];
        } else {
            agentId = registry.mint(address(this));
            agents.push(agentId);
        }
        // Pool is the difficulty. `premium` selects the best pool; otherwise the fuzzed difficulty.
        uint8 difficulty = premium ? 2 : uint8(diff % 3);
        AxVigilCollectible.MintAuth memory a = AxVigilCollectible.MintAuth({
            agentId: agentId,
            to: address(this),
            vulnClass: vc % 3,
            difficulty: difficulty,
            pool: difficulty,
            submissionHash: bytes32(nonce),
            nonce: nonce++,
            deadline: block.timestamp + 1 days
        });
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPk, nft.hashMintAuth(a));
        vm.roll(block.number + 1);
        try nft.mint(a, abi.encodePacked(r, s, v)) {} catch {}
    }

    function rotateBatch(bytes32 seed) external {
        // reveal the open batch (if any), then commit a fresh one
        uint32 cur = nft.currentBatch();
        vm.startPrank(owner);
        if (cur != 0) nft.revealSeed(cur, seeds[cur - 1]);
        if (seed == bytes32(0)) seed = bytes32(uint256(1));
        nft.commitSeed(keccak256(abi.encodePacked(seed)));
        vm.stopPrank();
        seeds.push(seed);
    }

    function reveal(uint8 n) external {
        nft.revealTokens(n);
    }

    function warp(uint16 secs) external {
        vm.warp(block.timestamp + secs);
    }

    function onERC721Received(address, address, uint256, bytes calldata) external pure returns (bytes4) {
        return this.onERC721Received.selector;
    }
}

contract AxVigilInvariantTest is Test {
    AxVigilCollectible internal nft;
    Handler internal handler;
    uint256[5] internal tiers = [uint256(30), 10, 5, 4, 4];

    function setUp() public {
        address owner = makeAddr("owner");
        uint256 pk = 0xA11CE;
        MockAgentID registry = new MockAgentID();
        AxVigilSkill skill = new AxVigilSkill(IAgentRegistry(address(registry)), owner);
        nft = new AxVigilCollectible(
            IAgentRegistry(address(registry)), IAxVigilSkill(address(skill)), vm.addr(pk), owner, tiers, 5
        );
        bytes32 seed = keccak256("inv");
        vm.startPrank(owner);
        skill.grantRole(skill.MINTER_ROLE(), address(nft));
        nft.commitSeed(keccak256(abi.encodePacked(seed)));
        vm.stopPrank();
        handler = new Handler(nft, registry, owner, pk, seed);
        targetContract(address(handler));
    }

    function invariant_supplyNeverExceedsMax() public view {
        assertLe(nft.totalMinted(), nft.maxSupply());
        assertLe(nft.totalMinted() - nft.drawnOf(4), nft.drawableSupply());
        assertEq(nft.maxSupply(), 53);
        assertEq(nft.drawableSupply(), 49, "public quota, hidden not included");
        assertLe(nft.drawnOf(4), tiers[4], "hidden quota");
    }

    function invariant_drawnMatchesRevealedAndWithinPools() public view {
        uint256 revealed = nft.nextToReveal() - 1;
        uint256 sum;
        uint256 denom = nft.drawableSupply();
        uint256 stage = revealed == 0 ? 0 : ((revealed - 1) * 4) / denom;
        for (uint256 t; t < 5; ++t) {
            uint256 d = nft.drawnOf(t);
            assertLe(d, tiers[t], "tier pool never exceeded");
            if (t == 3) assertLe(d, (tiers[t] * (stage + 1)) / 4, "staged release");
            sum += d;
        }
        for (uint256 id = 1; id <= revealed; ++id) {
            AxVigilCollectible.TokenData memory td = nft.tokenData(id);
            if (td.pool != 2) assertLt(td.tier, 4, "only pool 2 can draw hidden");
        }
        assertEq(sum, revealed);
        assertLe(revealed, nft.totalMinted());
    }
}
