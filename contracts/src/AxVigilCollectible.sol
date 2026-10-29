// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

import {IAgentRegistry} from "./interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "./interfaces/IAxVigilSkill.sol";

/// @title AxVigilCollectible
/// @notice Tradeable ERC-721 collectible earned by an AI agent that solved an AxVigil challenge.
///
/// Flow
///  1. Backend verifies a solve and signs an EIP-712 `MintAuth` (domain "AxVigil" / "1").
///  2. The Agent ID owner calls `mint(auth, sig)`. One signature:
///       - mints a collectible to `auth.to` (tier still hidden), and
///       - records the solve on the AxVigilSkill record of `auth.agentId`.
///  3. Commit-reveal: the owner committed `keccak256(seed)` for the open batch BEFORE mints.
///     Each mint stores block entropy. After the batch is closed the owner reveals `seed`,
///     then anyone calls `revealTokens(n)` which draws tiers in tokenId order.
///
/// Rarity
///  - Fixed tier pools drawn WITHOUT replacement (production 5444/1555/622/152/4 = 7,777).
///  - Staged release: LEGENDARY and HIDDEN are released in 4 equal stages, one stage per 25% of
///    supply drawn (stage k releases total*(k+1)/4). For HIDDEN=4 that is 1 per 25%.
///    The first stage is open from token #1, so the last HIDDEN is reachable at 75%.
///  - PREMIUM pool (hard + fast solve): rare tiers get a higher weight among what remains.
///    Weights multiply the remaining count, so it is a better chance, never a guarantee.
///
/// Limits: max 2 per Agent ID (lifetime, bound to tokenId not wallet), hourly mint cap,
/// pausable, rotatable signer, supply fixed in the constructor with no way to increase it.
contract AxVigilCollectible is ERC721, Ownable2Step, Pausable, EIP712 {
    using Strings for uint256;

    // ---------------------------------------------------------------------
    // Constants
    // ---------------------------------------------------------------------

    bytes32 public constant MINT_AUTH_TYPEHASH = keccak256(
        "MintAuth(uint256 agentId,address to,uint8 vulnClass,uint8 difficulty,uint8 pool,bytes32 submissionHash,uint256 nonce,uint256 deadline)"
    );

    /// @dev Records a verified solve on the skill record WITHOUT minting a collectible.
    ///      Lets an agent's skill record grow past the 2-collectible cap (e.g. all 3 classes).
    bytes32 public constant SKILL_AUTH_TYPEHASH = keccak256(
        "SkillAuth(uint256 agentId,uint8 vulnClass,uint8 difficulty,bytes32 submissionHash,uint256 nonce,uint256 deadline)"
    );

    uint256 public constant MAX_PER_AGENT = 2;
    uint8 public constant NUM_TIERS = 5; // 0 COMMON, 1 RARE, 2 EPIC, 3 LEGENDARY, 4 HIDDEN
    uint8 public constant NUM_CLASSES = 3; // 0 REENTRANCY, 1 PRICE_MANIPULATION, 2 ACCESS_CONTROL
    uint8 public constant NUM_DIFFICULTIES = 3; // 0 BASIC, 1 ADVANCED, 2 LEGENDARY
    uint8 public constant POOL_NORMAL = 0;
    uint8 public constant POOL_PREMIUM = 1;

    uint8 public constant TIER_LEGENDARY = 3;
    uint8 public constant TIER_HIDDEN = 4;
    uint256 public constant STAGES = 4;

    /// @dev Art id layout: tier * 100_000 + vulnClass * 10_000 + index within (tier, vulnClass).
    uint256 private constant ART_TIER_MUL = 100_000;
    uint256 private constant ART_CLASS_MUL = 10_000;

    // ---------------------------------------------------------------------
    // Types
    // ---------------------------------------------------------------------

    struct MintAuth {
        uint256 agentId;
        address to;
        uint8 vulnClass;
        uint8 difficulty;
        uint8 pool;
        bytes32 submissionHash;
        uint256 nonce;
        uint256 deadline;
    }

    struct SkillAuth {
        uint256 agentId;
        uint8 vulnClass;
        uint8 difficulty;
        bytes32 submissionHash;
        uint256 nonce;
        uint256 deadline;
    }

    struct TokenData {
        uint8 vulnClass;
        uint8 difficulty;
        uint8 pool;
        uint8 tier; // valid only once revealed
        bool revealed;
        uint32 batchId;
        uint32 artId; // valid only once revealed
        bytes32 entropy; // block entropy captured at mint
    }

    struct Batch {
        bytes32 seedHash; // keccak256(abi.encodePacked(seed))
        bytes32 seed; // set on reveal
        bool revealed;
    }

    // ---------------------------------------------------------------------
    // Immutable config
    // ---------------------------------------------------------------------

    IAgentRegistry public immutable agentRegistry;
    IAxVigilSkill public immutable skill;
    /// @notice Hard supply cap = sum of tier pools. Immutable: cannot be increased.
    uint256 public immutable maxSupply;

    uint256 private immutable _tier0;
    uint256 private immutable _tier1;
    uint256 private immutable _tier2;
    uint256 private immutable _tier3;
    uint256 private immutable _tier4;

    // ---------------------------------------------------------------------
    // Mutable state
    // ---------------------------------------------------------------------

    address public signer;
    uint256 public hourlyCap;

    uint256 public totalMinted;
    /// @notice Next tokenId whose tier will be drawn (tokens are revealed strictly in order).
    uint256 public nextToReveal = 1;

    uint256[5] private _drawn; // drawn per tier
    mapping(uint256 tier => mapping(uint256 vulnClass => uint256)) public artCount;

    mapping(uint256 nonce => bool) public nonceUsed;
    /// @notice Each verified solve (submissionHash) can drive at most one on-chain action,
    ///         whether a collectible mint or a skill-only record. Prevents a replayed solve.
    mapping(bytes32 submissionHash => bool) public submissionUsed;
    mapping(uint256 agentId => uint256) public mintedPerAgent;
    mapping(uint256 hourIndex => uint256) public mintedInHour;
    mapping(uint256 tokenId => TokenData) private _tokens;
    mapping(uint256 tokenId => uint256) public agentOfToken;

    uint32 public batchCount;
    /// @notice Batch that new mints join. 0 = no open batch (mint blocked until owner commits).
    uint32 public currentBatch;
    mapping(uint32 batchId => Batch) public batches;

    string public baseURI;
    string public unrevealedURI;
    /// @notice Provenance commitment for the pre-generated art + metadata set. Settable once.
    bytes32 public provenanceHash;

    // ---------------------------------------------------------------------
    // Events / errors
    // ---------------------------------------------------------------------

    event Minted(
        uint256 indexed tokenId,
        uint256 indexed agentId,
        address indexed to,
        uint8 vulnClass,
        uint8 difficulty,
        uint8 pool,
        uint32 batchId,
        bytes32 submissionHash,
        uint256 nonce
    );
    event TokenRevealed(uint256 indexed tokenId, uint8 tier, uint32 artId);
    event SkillRecorded(
        uint256 indexed agentId, uint8 vulnClass, uint8 difficulty, bytes32 submissionHash, uint256 nonce
    );
    event SeedCommitted(uint32 indexed batchId, bytes32 seedHash);
    event SeedRevealed(uint32 indexed batchId, bytes32 seed);
    event SignerUpdated(address indexed oldSigner, address indexed newSigner);
    event HourlyCapUpdated(uint256 cap);
    event BaseURIUpdated(string baseURI, string unrevealedURI);
    event ProvenanceHashSet(bytes32 provenanceHash);

    error Expired();
    error NonceUsed();
    error SubmissionUsed();
    error InvalidSignature();
    error NotAgentOwner();
    error AgentQuotaReached();
    error SoldOut();
    error HourlyCapReached();
    error NoOpenBatch();
    error InvalidParams();
    error BadSeed();
    error AlreadyRevealed();
    error ProvenanceAlreadySet();
    error ZeroAddress();

    // ---------------------------------------------------------------------
    // Constructor
    // ---------------------------------------------------------------------

    /// @param tierCounts pools for [COMMON, RARE, EPIC, LEGENDARY, HIDDEN]. Production:
    ///        [5444, 1555, 622, 152, 4]. Smaller configs are allowed for tests.
    constructor(
        IAgentRegistry registry,
        IAxVigilSkill skill_,
        address signer_,
        address owner_,
        uint256[5] memory tierCounts,
        uint256 hourlyCap_
    ) ERC721("AxVigil Collectible", "AXVIGIL") Ownable(owner_) EIP712("AxVigil", "1") {
        if (address(registry) == address(0) || address(skill_) == address(0) || signer_ == address(0)) {
            revert ZeroAddress();
        }
        if (hourlyCap_ == 0) revert InvalidParams();

        uint256 total;
        for (uint256 i; i < NUM_TIERS; ++i) {
            total += tierCounts[i];
        }
        if (total < STAGES || total > 10_000) revert InvalidParams(); // art id layout needs < 10k per bucket

        // Staged release must never leave the released pool empty before the next stage opens.
        // At the last index of stage k, tokens left (incl. this one) must exceed what is still locked.
        for (uint256 k; k < STAGES; ++k) {
            uint256 nextStageStart = _ceilDiv((k + 1) * total, STAGES); // first index of stage k+1
            uint256 locked_ = (tierCounts[3] - (tierCounts[3] * (k + 1)) / STAGES)
                + (tierCounts[4] - (tierCounts[4] * (k + 1)) / STAGES);
            if (total - nextStageStart + 1 <= locked_) revert InvalidParams();
        }

        agentRegistry = registry;
        skill = skill_;
        maxSupply = total;
        _tier0 = tierCounts[0];
        _tier1 = tierCounts[1];
        _tier2 = tierCounts[2];
        _tier3 = tierCounts[3];
        _tier4 = tierCounts[4];
        signer = signer_;
        hourlyCap = hourlyCap_;
        emit SignerUpdated(address(0), signer_);
        emit HourlyCapUpdated(hourlyCap_);
    }

    // ---------------------------------------------------------------------
    // Mint
    // ---------------------------------------------------------------------

    /// @notice Mint one collectible using a backend-signed authorization.
    /// @dev Caller must currently own `auth.agentId` in the Agent ID registry.
    function mint(MintAuth calldata auth, bytes calldata signature) external whenNotPaused returns (uint256 tokenId) {
        _checkAuth(auth, signature);
        uint32 batchId = _checkLimits(auth.agentId);

        // --- effects ---
        nonceUsed[auth.nonce] = true;
        submissionUsed[auth.submissionHash] = true;
        mintedPerAgent[auth.agentId] += 1;
        mintedInHour[block.timestamp / 1 hours] += 1;
        tokenId = ++totalMinted;

        _tokens[tokenId] = TokenData({
            vulnClass: auth.vulnClass,
            difficulty: auth.difficulty,
            pool: auth.pool,
            tier: 0,
            revealed: false,
            batchId: batchId,
            artId: 0,
            // Not secret by itself (validators can see it); combined with the committed seed at reveal.
            // Guard block.number == 0 (genesis / script simulation) so the subtraction can't underflow.
            entropy: keccak256(
                abi.encode(
                    block.number > 0 ? blockhash(block.number - 1) : bytes32(0),
                    block.prevrandao,
                    tokenId,
                    auth.to
                )
            )
        });
        agentOfToken[tokenId] = auth.agentId;

        // --- interactions ---
        // _mint (not _safeMint): no receiver callback, so no reentrancy surface.
        _mint(auth.to, tokenId);
        skill.recordSolve(auth.agentId, auth.vulnClass, auth.difficulty);

        _emitMinted(tokenId, batchId, auth);
    }

    /// @dev Signature, deadline, nonce, field ranges and Agent ID ownership.
    function _checkAuth(MintAuth calldata auth, bytes calldata signature) internal view {
        if (block.timestamp > auth.deadline) revert Expired();
        if (nonceUsed[auth.nonce]) revert NonceUsed();
        if (submissionUsed[auth.submissionHash]) revert SubmissionUsed();
        if (auth.vulnClass >= NUM_CLASSES || auth.difficulty >= NUM_DIFFICULTIES || auth.pool > POOL_PREMIUM) {
            revert InvalidParams();
        }
        if (auth.to == address(0)) revert ZeroAddress();

        (address recovered, ECDSA.RecoverError err,) = ECDSA.tryRecover(hashMintAuth(auth), signature);
        if (err != ECDSA.RecoverError.NoError || recovered != signer) revert InvalidSignature();

        if (agentRegistry.ownerOf(auth.agentId) != msg.sender) revert NotAgentOwner();
    }

    /// @dev Per-agent quota, supply cap, hourly cap, open batch. Returns the open batch id.
    function _checkLimits(uint256 agentId) internal view returns (uint32 batchId) {
        if (mintedPerAgent[agentId] >= MAX_PER_AGENT) revert AgentQuotaReached();
        if (totalMinted >= maxSupply) revert SoldOut();
        if (mintedInHour[block.timestamp / 1 hours] >= hourlyCap) revert HourlyCapReached();
        batchId = currentBatch;
        if (batchId == 0) revert NoOpenBatch();
    }

    function _emitMinted(uint256 tokenId, uint32 batchId, MintAuth calldata a) private {
        emit Minted(tokenId, a.agentId, a.to, a.vulnClass, a.difficulty, a.pool, batchId, a.submissionHash, a.nonce);
    }

    /// @notice EIP-712 digest of a MintAuth (useful for the backend and tests).
    function hashMintAuth(MintAuth calldata a) public view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    MINT_AUTH_TYPEHASH,
                    a.agentId,
                    a.to,
                    a.vulnClass,
                    a.difficulty,
                    a.pool,
                    a.submissionHash,
                    a.nonce,
                    a.deadline
                )
            )
        );
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    // ---------------------------------------------------------------------
    // Skill-only record (no collectible, no quota)
    // ---------------------------------------------------------------------

    /// @notice Record a verified solve on the agent's skill record without minting a collectible.
    /// @dev Collectibles are capped at MAX_PER_AGENT, but the skill record is a resume that should
    ///      grow with every verified solve (so all three class emblems can light up). This path
    ///      shares the signer, nonce space and submissionHash dedup with `mint`, so a given solve
    ///      drives at most one on-chain action. Caller must own `auth.agentId` in the registry.
    function recordSolve(SkillAuth calldata auth, bytes calldata signature) external whenNotPaused {
        if (block.timestamp > auth.deadline) revert Expired();
        if (nonceUsed[auth.nonce]) revert NonceUsed();
        if (submissionUsed[auth.submissionHash]) revert SubmissionUsed();
        if (auth.vulnClass >= NUM_CLASSES || auth.difficulty >= NUM_DIFFICULTIES) revert InvalidParams();

        (address recovered, ECDSA.RecoverError err,) = ECDSA.tryRecover(hashSkillAuth(auth), signature);
        if (err != ECDSA.RecoverError.NoError || recovered != signer) revert InvalidSignature();
        if (agentRegistry.ownerOf(auth.agentId) != msg.sender) revert NotAgentOwner();

        // --- effects ---
        nonceUsed[auth.nonce] = true;
        submissionUsed[auth.submissionHash] = true;

        // --- interactions ---
        // Reverts (rolling back the effects above) if the record was revoked.
        skill.recordSolve(auth.agentId, auth.vulnClass, auth.difficulty);

        emit SkillRecorded(auth.agentId, auth.vulnClass, auth.difficulty, auth.submissionHash, auth.nonce);
    }

    /// @notice EIP-712 digest of a SkillAuth.
    function hashSkillAuth(SkillAuth calldata a) public view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    SKILL_AUTH_TYPEHASH, a.agentId, a.vulnClass, a.difficulty, a.submissionHash, a.nonce, a.deadline
                )
            )
        );
    }

    // ---------------------------------------------------------------------
    // Commit-reveal
    // ---------------------------------------------------------------------

    /// @notice Open a new batch with a committed seed hash. Closes the previous batch.
    /// @param seedHash keccak256(abi.encodePacked(bytes32 seed)); keep `seed` secret until reveal.
    function commitSeed(bytes32 seedHash) external onlyOwner {
        if (seedHash == bytes32(0)) revert InvalidParams();
        uint32 id = ++batchCount;
        batches[id].seedHash = seedHash;
        currentBatch = id;
        emit SeedCommitted(id, seedHash);
    }

    /// @notice Reveal the seed of a batch. Revealing the open batch closes it first,
    ///         so nobody can mint into a batch whose seed is already public.
    function revealSeed(uint32 batchId, bytes32 seed) external onlyOwner {
        Batch storage b = batches[batchId];
        if (b.seedHash == bytes32(0)) revert InvalidParams();
        if (b.revealed) revert AlreadyRevealed();
        if (keccak256(abi.encodePacked(seed)) != b.seedHash) revert BadSeed();
        if (currentBatch == batchId) currentBatch = 0;
        b.seed = seed;
        b.revealed = true;
        emit SeedRevealed(batchId, seed);
    }

    /// @notice Draw tiers for up to `maxCount` pending tokens, strictly in tokenId order.
    ///         Permissionless. Stops at the first token whose batch seed is not yet revealed.
    /// @return count number of tokens revealed in this call
    function revealTokens(uint256 maxCount) external returns (uint256 count) {
        uint256 id = nextToReveal;
        while (count < maxCount && id <= totalMinted) {
            TokenData storage t = _tokens[id];
            Batch storage b = batches[t.batchId];
            if (!b.revealed) break;

            uint256 rand = uint256(keccak256(abi.encode(b.seed, t.entropy)));
            uint8 tier = _drawTier(id - 1, t.pool, rand);

            uint256 index = artCount[tier][t.vulnClass]++;
            uint32 artId = uint32(uint256(tier) * ART_TIER_MUL + uint256(t.vulnClass) * ART_CLASS_MUL + index);

            t.tier = tier;
            t.artId = artId;
            t.revealed = true;
            emit TokenRevealed(id, tier, artId);

            unchecked {
                ++id;
                ++count;
            }
        }
        nextToReveal = id;
    }

    /// @dev Weighted draw over what is currently released and not yet drawn.
    ///      NORMAL: weight = remaining count (uniform without replacement).
    ///      PREMIUM: weight = remaining count * multiplier [1,2,4,8,8].
    function _drawTier(uint256 drawIndex, uint8 pool, uint256 rand) internal returns (uint8) {
        uint256 stage = (drawIndex * STAGES) / maxSupply; // 0..3
        uint256[5] memory w;
        uint256 total;
        for (uint256 t; t < NUM_TIERS; ++t) {
            uint256 avail = _released(t, stage) - _drawn[t];
            w[t] = avail * _weightMultiplier(pool, t);
            total += w[t];
        }
        // total > 0 is guaranteed by the constructor's staged-release check.
        uint256 r = rand % total;
        for (uint256 t; t < NUM_TIERS; ++t) {
            if (r < w[t]) {
                _drawn[t] += 1;
                return uint8(t);
            }
            r -= w[t];
        }
        revert(); // unreachable
    }

    function _weightMultiplier(uint8 pool, uint256 tier) internal pure returns (uint256) {
        if (pool != POOL_PREMIUM) return 1;
        if (tier == 0) return 1;
        if (tier == 1) return 2;
        if (tier == 2) return 4;
        return 8; // LEGENDARY, HIDDEN
    }

    /// @notice How many of `tier` are released into the pool at `stage` (0..3).
    function _released(uint256 tier, uint256 stage) internal view returns (uint256) {
        uint256 n = tierTotal(tier);
        if (tier < TIER_LEGENDARY) return n;
        return (n * (stage + 1)) / STAGES;
    }

    // ---------------------------------------------------------------------
    // Admin
    // ---------------------------------------------------------------------

    function setSigner(address newSigner) external onlyOwner {
        if (newSigner == address(0)) revert ZeroAddress();
        emit SignerUpdated(signer, newSigner);
        signer = newSigner;
    }

    /// @notice Adjust the hourly circuit breaker. Does not affect total supply.
    function setHourlyCap(uint256 cap) external onlyOwner {
        if (cap == 0) revert InvalidParams();
        hourlyCap = cap;
        emit HourlyCapUpdated(cap);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function setBaseURI(string calldata base, string calldata unrevealed) external onlyOwner {
        baseURI = base;
        unrevealedURI = unrevealed;
        emit BaseURIUpdated(base, unrevealed);
    }

    /// @notice Commit to the hash of the full pre-generated art/metadata set. Once only.
    function setProvenanceHash(bytes32 h) external onlyOwner {
        if (provenanceHash != bytes32(0)) revert ProvenanceAlreadySet();
        if (h == bytes32(0)) revert InvalidParams();
        provenanceHash = h;
        emit ProvenanceHashSet(h);
    }

    // ---------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------

    /// @notice `baseURI + artId` once revealed, e.g. artId 120007 = tier 1 (RARE), class 2, art #7.
    ///         Before reveal returns `unrevealedURI`.
    function tokenURI(uint256 tokenId) public view override returns (string memory) {
        _requireOwned(tokenId);
        TokenData memory t = _tokens[tokenId];
        if (!t.revealed) return unrevealedURI;
        return string.concat(baseURI, uint256(t.artId).toString());
    }

    function tokenData(uint256 tokenId) external view returns (TokenData memory) {
        _requireOwned(tokenId);
        return _tokens[tokenId];
    }

    function vulnClassOf(uint256 tokenId) external view returns (uint8) {
        _requireOwned(tokenId);
        return _tokens[tokenId].vulnClass;
    }

    /// @notice Tier of a token. Reverts until revealed.
    function tierOf(uint256 tokenId) external view returns (uint8) {
        _requireOwned(tokenId);
        TokenData memory t = _tokens[tokenId];
        require(t.revealed, "not revealed");
        return t.tier;
    }

    function tierTotal(uint256 tier) public view returns (uint256) {
        if (tier == 0) return _tier0;
        if (tier == 1) return _tier1;
        if (tier == 2) return _tier2;
        if (tier == 3) return _tier3;
        if (tier == 4) return _tier4;
        revert InvalidParams();
    }

    function drawnOf(uint256 tier) external view returns (uint256) {
        return _drawn[tier];
    }

    /// @notice Released-but-undrawn count of each tier for the next draw.
    function availableNow() external view returns (uint256[5] memory avail) {
        uint256 drawIndex = nextToReveal - 1;
        if (drawIndex >= maxSupply) return avail;
        uint256 stage = (drawIndex * STAGES) / maxSupply;
        for (uint256 t; t < NUM_TIERS; ++t) {
            avail[t] = _released(t, stage) - _drawn[t];
        }
    }

    function _ceilDiv(uint256 a, uint256 b) private pure returns (uint256) {
        return (a + b - 1) / b;
    }
}
