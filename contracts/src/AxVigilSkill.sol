// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {IERC165} from "@openzeppelin/contracts/utils/introspection/IERC165.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {IERC721Metadata} from "@openzeppelin/contracts/token/ERC721/extensions/IERC721Metadata.sol";
import {Base64} from "@openzeppelin/contracts/utils/Base64.sol";
import {Strings} from "@openzeppelin/contracts/utils/Strings.sol";

import {IERC5192} from "./interfaces/IERC5192.sol";
import {IAgentRegistry} from "./interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "./interfaces/IAxVigilSkill.sol";

/// @title AxVigilSkill
/// @notice Non-transferable (ERC-5192, permanently locked) skill record for an AI agent.
///
///  - Exactly one record per Agent ID: the record's tokenId IS the Agent ID tokenId.
///  - Ownership is not stored here. `ownerOf(agentId)` proxies the Agent ID registry, so the
///    record follows the Agent ID when it changes wallets and cannot be sold on its own.
///  - Only MINTER_ROLE (the AxVigilCollectible contract) can record solves.
///  - DEFAULT_ADMIN_ROLE can revoke a record (e.g. a confirmed cheat) with a reason.
///    A revoked Agent ID can no longer receive solves.
///  - tokenURI is fully on-chain: base64 JSON with an SVG that gains one visual element per
///    vulnerability class solved.
///
///  Because ownership lives in another contract, `balanceOf` cannot be computed and reverts,
///  and the ERC-721 Transfer events emitted here only reflect the owner at record/revoke time.
contract AxVigilSkill is IERC5192, IERC165, IAxVigilSkill, AccessControl {
    using Strings for uint256;

    // ---------------------------------------------------------------------
    // Constants (shared with SPEC.md)
    // ---------------------------------------------------------------------

    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    uint8 public constant NUM_CLASSES = 3; // 0 REENTRANCY, 1 PRICE_MANIPULATION, 2 ACCESS_CONTROL
    uint8 public constant NUM_DIFFICULTIES = 3; // 0 BASIC, 1 ADVANCED, 2 LEGENDARY

    // ---------------------------------------------------------------------
    // Storage
    // ---------------------------------------------------------------------

    struct Record {
        bool exists;
        bool revoked;
        uint8 maxDifficulty;
        uint8 classMask; // bit i set => vuln class i solved at least once
        uint32 totalSolves;
        uint32[3] solvesPerClass;
        uint64 firstSolveAt;
        uint64 lastSolveAt;
    }

    IAgentRegistry public immutable agentRegistry;

    mapping(uint256 agentId => Record) private _records;
    mapping(uint256 agentId => string) public revokeReason;

    /// @notice Number of live (non-revoked) records.
    uint256 public totalRecords;

    // ---------------------------------------------------------------------
    // Events / errors
    // ---------------------------------------------------------------------

    /// @dev ERC-721 Transfer, emitted on record creation (from 0) and revoke (to 0).
    event Transfer(address indexed from, address indexed to, uint256 indexed tokenId);
    event SolveRecorded(uint256 indexed agentId, uint8 vulnClass, uint8 difficulty, uint32 totalSolves);
    event Revoked(uint256 indexed agentId, string reason);

    error Soulbound();
    error NoRecord(uint256 agentId);
    error AgentRevoked(uint256 agentId);
    error InvalidVulnClass(uint8 vulnClass);
    error InvalidDifficulty(uint8 difficulty);
    error BalanceUnsupported();

    constructor(IAgentRegistry registry, address admin) {
        agentRegistry = registry;
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    // ---------------------------------------------------------------------
    // Writes
    // ---------------------------------------------------------------------

    /// @notice Record a verified solve for `agentId`. Creates the record on first solve.
    /// @dev Only the Collectible contract (MINTER_ROLE) calls this, and only from `mint`.
    ///      One mint writes one solve, so a production skill record cannot grow past the
    ///      two-collectible cap or record a solve that has no collectible.
    function recordSolve(uint256 agentId, uint8 vulnClass, uint8 difficulty) external override onlyRole(MINTER_ROLE) {
        if (vulnClass >= NUM_CLASSES) revert InvalidVulnClass(vulnClass);
        if (difficulty >= NUM_DIFFICULTIES) revert InvalidDifficulty(difficulty);

        Record storage r = _records[agentId];
        if (r.revoked) revert AgentRevoked(agentId);

        if (!r.exists) {
            r.exists = true;
            r.firstSolveAt = uint64(block.timestamp);
            totalRecords += 1;
            // Reverts if the Agent ID does not exist, which is what we want.
            address owner = agentRegistry.ownerOf(agentId);
            emit Transfer(address(0), owner, agentId);
            emit Locked(agentId);
        }

        r.solvesPerClass[vulnClass] += 1;
        r.totalSolves += 1;
        r.classMask |= uint8(1 << vulnClass);
        if (difficulty > r.maxDifficulty) r.maxDifficulty = difficulty;
        r.lastSolveAt = uint64(block.timestamp);

        emit SolveRecorded(agentId, vulnClass, difficulty, r.totalSolves);
    }

    /// @notice Revoke an agent's skill record, with a public reason. Permanent for this contract:
    ///         the record is wiped and the Agent ID cannot earn new solves here.
    function revoke(uint256 agentId, string calldata reason) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Record storage r = _records[agentId];
        if (!r.exists) revert NoRecord(agentId);

        address owner;
        try agentRegistry.ownerOf(agentId) returns (address o) {
            owner = o;
        } catch {}

        delete _records[agentId];
        _records[agentId].revoked = true;
        revokeReason[agentId] = reason;
        totalRecords -= 1;

        emit Revoked(agentId, reason);
        emit Transfer(owner, address(0), agentId);
    }

    // ---------------------------------------------------------------------
    // Soulbound: every transfer/approval path reverts
    // ---------------------------------------------------------------------

    function transferFrom(address, address, uint256) external pure {
        revert Soulbound();
    }

    function safeTransferFrom(address, address, uint256) external pure {
        revert Soulbound();
    }

    function safeTransferFrom(address, address, uint256, bytes calldata) external pure {
        revert Soulbound();
    }

    function approve(address, uint256) external pure {
        revert Soulbound();
    }

    function setApprovalForAll(address, bool) external pure {
        revert Soulbound();
    }

    function getApproved(uint256) external pure returns (address) {
        return address(0);
    }

    function isApprovedForAll(address, address) external pure returns (bool) {
        return false;
    }

    // ---------------------------------------------------------------------
    // ERC-5192
    // ---------------------------------------------------------------------

    /// @inheritdoc IERC5192
    function locked(uint256 agentId) external view override returns (bool) {
        if (!_records[agentId].exists) revert NoRecord(agentId);
        return true;
    }

    // ---------------------------------------------------------------------
    // ERC-721-like views
    // ---------------------------------------------------------------------

    function name() external pure returns (string memory) {
        return "AxVigil Skill Record";
    }

    function symbol() external pure returns (string memory) {
        return "AXSKILL";
    }

    /// @notice Owner of the skill record = current owner of the Agent ID in the registry.
    function ownerOf(uint256 agentId) public view returns (address) {
        if (!_records[agentId].exists) revert NoRecord(agentId);
        return agentRegistry.ownerOf(agentId);
    }

    /// @notice Not computable: ownership lives in the Agent ID registry.
    function balanceOf(address) external pure returns (uint256) {
        revert BalanceUnsupported();
    }

    function exists(uint256 agentId) external view returns (bool) {
        return _records[agentId].exists;
    }

    function isRevoked(uint256 agentId) external view returns (bool) {
        return _records[agentId].revoked;
    }

    /// @notice Solve count for one vulnerability class.
    function solvesOf(uint256 agentId, uint8 vulnClass) external view returns (uint32) {
        if (vulnClass >= NUM_CLASSES) revert InvalidVulnClass(vulnClass);
        return _records[agentId].solvesPerClass[vulnClass];
    }

    /// @notice Solve counts for all classes [REENTRANCY, PRICE_MANIPULATION, ACCESS_CONTROL].
    function classCounts(uint256 agentId) external view returns (uint32[3] memory) {
        return _records[agentId].solvesPerClass;
    }

    /// @notice Highest difficulty solved (0 BASIC, 1 ADVANCED, 2 LEGENDARY). Reverts if no record.
    function maxDifficulty(uint256 agentId) external view returns (uint8) {
        if (!_records[agentId].exists) revert NoRecord(agentId);
        return _records[agentId].maxDifficulty;
    }

    function totalSolves(uint256 agentId) external view returns (uint32) {
        return _records[agentId].totalSolves;
    }

    /// @notice Full record (for frontends / external platforms).
    function getRecord(uint256 agentId) external view returns (Record memory) {
        return _records[agentId];
    }

    // ---------------------------------------------------------------------
    // ERC-165
    // ---------------------------------------------------------------------

    function supportsInterface(bytes4 interfaceId) public view override(AccessControl, IERC165) returns (bool) {
        return interfaceId == type(IERC5192).interfaceId // 0xb45a3c0e
            || interfaceId == type(IERC721).interfaceId || interfaceId == type(IERC721Metadata).interfaceId
            || super.supportsInterface(interfaceId);
    }

    // ---------------------------------------------------------------------
    // On-chain metadata
    // ---------------------------------------------------------------------

    function tokenURI(uint256 agentId) external view returns (string memory) {
        Record memory r = _records[agentId];
        if (!r.exists) revert NoRecord(agentId);

        string memory json = string.concat(
            '{"name":"AxVigil Skill #',
            agentId.toString(),
            '","description":"Non-transferable record of verified smart-contract fixes by this AI agent. Bound to its Agent ID.",',
            '"image":"data:image/svg+xml;base64,',
            Base64.encode(bytes(_svg(agentId, r))),
            '","attributes":',
            _attributes(r),
            "}"
        );
        return string.concat("data:application/json;base64,", Base64.encode(bytes(json)));
    }

    function _attributes(Record memory r) private pure returns (string memory) {
        return string.concat(
            '[{"trait_type":"Max Difficulty","value":"',
            _difficultyName(r.maxDifficulty),
            '"},{"trait_type":"Classes Solved","value":',
            uint256(_popcount(r.classMask)).toString(),
            '},{"trait_type":"Reentrancy","value":',
            uint256(r.solvesPerClass[0]).toString(),
            '},{"trait_type":"Price Manipulation","value":',
            uint256(r.solvesPerClass[1]).toString(),
            '},{"trait_type":"Access Control","value":',
            uint256(r.solvesPerClass[2]).toString(),
            '},{"trait_type":"Total Solves","value":',
            uint256(r.totalSolves).toString(),
            "}]"
        );
    }

    /// @dev 400x400 card. A frame coloured by max difficulty, plus one emblem per solved class.
    ///      Unsolved classes show as a faint dashed placeholder, so the art "grows" as classes are added.
    function _svg(uint256 agentId, Record memory r) private pure returns (string memory) {
        string memory frame = _difficultyColor(r.maxDifficulty);
        return string.concat(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" font-family="monospace">',
            '<rect width="400" height="400" fill="#0b0f17"/>',
            '<rect x="10" y="10" width="380" height="380" rx="18" fill="none" stroke="',
            frame,
            '" stroke-width="4"/>',
            '<text x="30" y="50" fill="#e6edf3" font-size="22">AxVigil Skill</text>',
            '<text x="30" y="78" fill="#8b949e" font-size="14">Agent #',
            agentId.toString(),
            "</text>",
            _reentrancyEmblem(r),
            _priceEmblem(r),
            _accessEmblem(r),
            '<text x="30" y="370" fill="',
            frame,
            '" font-size="14">MAX ',
            _difficultyName(r.maxDifficulty),
            "</text></svg>"
        );
    }

    function _placeholder(string memory cx) private pure returns (string memory) {
        return
            string.concat('<circle cx="', cx, '" cy="200" r="44" fill="none" stroke="#30363d" stroke-dasharray="6 6"/>');
    }

    function _countLabel(string memory x, string memory color, uint32 n) private pure returns (string memory) {
        return string.concat(
            '<text x="',
            x,
            '" y="275" fill="',
            color,
            '" font-size="13" text-anchor="middle">x',
            uint256(n).toString(),
            "</text>"
        );
    }

    /// @dev Class 0 REENTRANCY: a closed loop with an arrow head (a call that comes back).
    function _reentrancyEmblem(Record memory r) private pure returns (string memory) {
        if (r.classMask & 1 == 0) return _placeholder("80");
        return string.concat(
            '<g stroke="#2dd4bf" fill="none" stroke-width="5">',
            '<circle cx="80" cy="200" r="38"/><path d="M110 176 l10 -14 l6 18 z" fill="#2dd4bf"/></g>',
            _countLabel("80", "#2dd4bf", r.solvesPerClass[0])
        );
    }

    /// @dev Class 1 PRICE_MANIPULATION: a spiking price chart.
    function _priceEmblem(Record memory r) private pure returns (string memory) {
        if (r.classMask & 2 == 0) return _placeholder("200");
        return string.concat(
            '<polyline points="160,230 180,215 195,222 210,165 225,210 240,195" fill="none" stroke="#f59e0b" stroke-width="5" stroke-linejoin="round"/>',
            '<line x1="156" y1="240" x2="244" y2="240" stroke="#f59e0b" stroke-width="2"/>',
            _countLabel("200", "#f59e0b", r.solvesPerClass[1])
        );
    }

    /// @dev Class 2 ACCESS_CONTROL: a key.
    function _accessEmblem(Record memory r) private pure returns (string memory) {
        if (r.classMask & 4 == 0) return _placeholder("320");
        return string.concat(
            '<g stroke="#a78bfa" fill="none" stroke-width="5"><circle cx="300" cy="200" r="16"/>',
            '<path d="M316 200 h32 M336 200 v12 M346 200 v8"/></g>',
            _countLabel("320", "#a78bfa", r.solvesPerClass[2])
        );
    }

    function _difficultyName(uint8 d) private pure returns (string memory) {
        if (d == 2) return "LEGENDARY";
        if (d == 1) return "ADVANCED";
        return "BASIC";
    }

    function _difficultyColor(uint8 d) private pure returns (string memory) {
        if (d == 2) return "#facc15";
        if (d == 1) return "#38bdf8";
        return "#9ca3af";
    }

    function _popcount(uint8 x) private pure returns (uint8 c) {
        while (x != 0) {
            c += x & 1;
            x >>= 1;
        }
    }
}
