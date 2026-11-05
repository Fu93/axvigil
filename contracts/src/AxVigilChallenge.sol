// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

import {IAxVigilSkill} from "./interfaces/IAxVigilSkill.sol";

/// @notice Collectible validator set. The collectible owner administers membership and `threshold`.
interface IValidatorSet {
    function isValidator(address account) external view returns (bool);
    function threshold() external view returns (uint256);
}

interface ICollectibleDifficulty {
    struct TokenData {
        uint8 vulnClass;
        uint8 difficulty;
        uint8 pool;
        uint8 tier;
        bool revealed;
        uint32 batchId;
        uint32 artId;
        bytes32 entropy;
    }
    function tokenData(uint256 tokenId) external view returns (TokenData memory);
}

/// @title AxVigilChallenge
/// @notice Optimistic challenge window for an AxVigil mint.
///
/// `AxVigilCollectible.mint` calls `onMint`. While `challengeWindow` is non-zero the
/// record stays Pending until `finalize`. Anyone can `challenge` during that window
/// by posting `challengeBond`. A verdict is not the challenger's word: `threshold`
/// distinct validators (the set on the collectible) must sign
/// `ChallengeVerdict(uint256 tokenId,uint32 round,address challenger,bytes32 evidenceHash,bool upheld,bytes32 reasonHash)`
/// under this contract's EIP-712 domain (name "AxVigil", version "1", this address).
///
/// Upheld: the collectible is flagged, the pending skill solve is dropped, and the
/// challenger is credited their bond plus the operator escrow (or `protocolReward`
/// from the pool when the escrow is zero). Rejected: the challenger's bond is
/// credited to `treasury` and another challenge is allowed until the window ends.
/// If validators never answer, anyone can `expireChallenge` after `respondBy`;
/// the bond is returned and the record can be challenged again until `readyAt`.
/// Finality is therefore late by at most `challengeWindow + responseWindow`.
///
/// Payouts are pull-based (`withdraw`) so a reverting recipient cannot brick
/// resolution or reenter the bond accounting.
contract AxVigilChallenge is Ownable2Step, EIP712, ReentrancyGuard {
    // ---------------------------------------------------------------------
    // Types
    // ---------------------------------------------------------------------

    bytes32 public constant CHALLENGE_VERDICT_TYPEHASH =
        keccak256("ChallengeVerdict(uint256 tokenId,uint256 round,address challenger,bytes32 evidenceHash,bool upheld,bytes32 reasonHash)");

    /// @dev Numeric values are part of the public ABI (cast / indexers).
    enum RecordStatus {
        None,
        Pending,
        Challenged,
        Final,
        Revoked
    }

    struct Record {
        uint256 agentId;
        uint8 vulnClass;
        uint8 difficulty;
        bytes32 submissionHash;
        address operator;
        address challenger;
        uint256 escrow;
        uint256 challengerBond;
        bytes32 evidenceHash;
        uint256 round;
        uint64 mintedAt;
        uint64 readyAt;
        uint64 respondBy;
        bool known;
        bool challengeOpen;
        bool upheld;
        bool finalized;
    }

    uint256 public constant MAX_WINDOW = 30 days;

    // ---------------------------------------------------------------------
    // Config
    // ---------------------------------------------------------------------

    /// @notice The only contract allowed to open a record (`mint`).
    address public immutable collectible;
    IAxVigilSkill public immutable skill;

    /// @notice Seconds after mint during which `challenge` is open. Zero finalizes in `onMint`.
    ///         Snapshotted into `readyAt` per token so a later change is not retroactive.
    uint256 public challengeWindow;
    /// @notice How long validators have to sign after a challenge is posted. Snapshotted.
    uint256 public responseWindow;
    uint256 public challengeBond;
    uint256 public operatorBond;
    /// @notice Paid from `poolBalance` on an upheld challenge when that mint escrowed nothing.
    uint256 public protocolReward;
    address public treasury;

    // ---------------------------------------------------------------------
    // Accounting. escrowed + bondsHeld + poolBalance + claimable == address(this).balance
    // ---------------------------------------------------------------------

    uint256 public escrowed;
    uint256 public bondsHeld;
    uint256 public poolBalance;
    uint256 public claimable;
    mapping(address => uint256) public withdrawable;

    mapping(uint256 tokenId => Record) private _records;
    mapping(bytes32 submissionHash => uint256 tokenId) public tokenBySubmission;

    // ---------------------------------------------------------------------
    // Events / errors
    // ---------------------------------------------------------------------

    event EvidenceAnchored(uint256 indexed tokenId, bytes32 indexed submissionHash, uint64 challengeDeadline);
    event Challenged(uint256 indexed tokenId, address indexed challenger, bytes32 evidenceHash, uint256 bond);
    event ChallengeResolved(uint256 indexed tokenId, bool upheld, bytes32 reasonHash);
    event ChallengeExpired(uint256 indexed tokenId);
    event Revoked(uint256 indexed tokenId, bytes32 reasonHash);
    event Finalized(uint256 indexed tokenId);
    event ChallengeWindowUpdated(uint256 window);
    event ResponseWindowUpdated(uint256 window);
    event BondsUpdated(uint256 challengeBond, uint256 operatorBond, uint256 protocolReward);
    event TreasuryUpdated(address indexed treasury);
    event PoolFunded(address indexed from, uint256 amount);
    event PoolReclaimed(address indexed to, uint256 amount);
    event Withdrawn(address indexed account, uint256 amount);

    error ZeroAddress();
    error InvalidParams();
    error NotCollectible();
    error BadBond(uint256 sent, uint256 expected);
    error EmptyEvidence();
    error DoubleChallenge();
    error ChallengeStillOpen();
    error ChallengeWindowClosed();
    error ChallengeWindowOpen();
    error NoChallenge();
    error AlreadyFinal();
    error AlreadyRevoked();
    error InvalidSignature();
    error InsufficientSignatures(uint256 got, uint256 required);
    error DuplicateSigner(address signer);
    error NotValidator(address signer);
    error PayFailed();

    constructor(
        address collectible_,
        IAxVigilSkill skill_,
        address owner_,
        uint256 challengeWindow_,
        uint256 responseWindow_,
        uint256 challengeBond_,
        uint256 operatorBond_,
        uint256 protocolReward_
    ) Ownable(owner_) EIP712("AxVigil", "1") {
        if (collectible_ == address(0) || address(skill_) == address(0) || owner_ == address(0)) revert ZeroAddress();
        if (challengeWindow_ > MAX_WINDOW || responseWindow_ == 0 || responseWindow_ > MAX_WINDOW) {
            revert InvalidParams();
        }
        collectible = collectible_;
        skill = skill_;
        treasury = owner_;
        challengeWindow = challengeWindow_;
        responseWindow = responseWindow_;
        challengeBond = challengeBond_;
        operatorBond = operatorBond_;
        protocolReward = protocolReward_;
        emit TreasuryUpdated(owner_);
        emit ChallengeWindowUpdated(challengeWindow_);
        emit ResponseWindowUpdated(responseWindow_);
        emit BondsUpdated(challengeBond_, operatorBond_, protocolReward_);
    }

    // ---------------------------------------------------------------------
    // Mint hook
    // ---------------------------------------------------------------------

    /// @notice Open the window for a collectible `mint` just recorded on the skill.
    ///         `operator` is the Agent ID owner who posted `operatorBond` (zero when the
    ///         window is zero). The evidence anchor is `submissionHash`: challengers
    ///         fetch the bundle (and its CIDv1) off-chain from that key.
    function onMint(uint256 tokenId, uint256 agentId, uint8 vulnClass, bytes32 submissionHash, address operator)
        external
        payable
        nonReentrant
    {
        if (msg.sender != collectible) revert NotCollectible();
        if (tokenId == 0 || operator == address(0) || _records[tokenId].known) revert InvalidParams();

        uint256 window = challengeWindow;
        uint256 due = window == 0 ? 0 : operatorBond;
        if (msg.value != due) revert BadBond(msg.value, due);

        Record storage r = _records[tokenId];
        r.known = true;
        r.agentId = agentId;
        r.vulnClass = vulnClass;
        try ICollectibleDifficulty(msg.sender).tokenData(tokenId) returns (ICollectibleDifficulty.TokenData memory td) {
            if (td.difficulty >= 3) revert InvalidParams();
            r.difficulty = td.difficulty;
        } catch {
            r.difficulty = 0;
        }
        r.submissionHash = submissionHash;
        r.operator = operator;
        r.escrow = due;
        r.mintedAt = uint64(block.timestamp);
        r.readyAt = uint64(block.timestamp + window);
        if (due != 0) escrowed += due;
        tokenBySubmission[submissionHash] = tokenId;
        emit EvidenceAnchored(tokenId, submissionHash, r.readyAt);

        if (window == 0) {
            r.finalized = true;
            skill.confirmSolve(agentId, vulnClass);
            emit Finalized(tokenId);
        }
    }

    // ---------------------------------------------------------------------
    // Challenge / resolution
    // ---------------------------------------------------------------------

    /// @notice Post a bond and a commitment to counter-evidence during the window.
    ///         `evidence` is opaque (CIDv1 text, canonical bundle bytes, or a counterexample).
    ///         The contract stores `keccak256(evidence)` and does not grade it.
    function challenge(uint256 tokenId, bytes calldata evidence) external payable nonReentrant {
        if (evidence.length == 0) revert EmptyEvidence();
        Record storage r = _records[tokenId];
        if (!r.known) revert InvalidParams();
        if (r.upheld) revert AlreadyRevoked();
        if (r.finalized) revert AlreadyFinal();
        if (r.challengeOpen) revert DoubleChallenge();
        if (block.timestamp >= r.readyAt) revert ChallengeWindowClosed();
        if (msg.value != challengeBond) revert BadBond(msg.value, challengeBond);

        r.challengeOpen = true;
        r.round += 1;
        r.challenger = msg.sender;
        r.challengerBond = msg.value;
        r.evidenceHash = keccak256(evidence);
        r.respondBy = uint64(block.timestamp + responseWindow);
        bondsHeld += msg.value;
        emit Challenged(tokenId, msg.sender, r.evidenceHash, msg.value);
    }

    /// @notice Apply a 2-of-3 (or current threshold) validator re-vote.
    /// @dev `upheld` means the challenger was right and the mint must be revoked.
    function resolveChallenge(uint256 tokenId, bool upheld, bytes32 reasonHash, bytes[] calldata signatures)
        external
        nonReentrant
    {
        Record storage r = _records[tokenId];
        if (!r.challengeOpen) revert NoChallenge();
        _verifyVerdict(tokenId, upheld, reasonHash, signatures);

        address challenger = r.challenger;
        uint256 bond = r.challengerBond;
        r.challengeOpen = false;
        r.challenger = address(0);
        r.challengerBond = 0;
        r.respondBy = 0;
        bondsHeld -= bond;
        emit ChallengeResolved(tokenId, upheld, reasonHash);

        if (upheld) {
            r.upheld = true;
            uint256 reward = _takeEscrow(r);
            skill.revokeSolve(r.agentId, r.vulnClass, r.difficulty);
            emit Revoked(tokenId, reasonHash);
            _credit(challenger, bond + reward);
        } else {
            _credit(treasury, bond);
            if (r.readyAt <= block.timestamp) {
                r.readyAt = uint64(block.timestamp + challengeWindow);
            }
        }
    }

    /// @notice Close a challenge the validators did not answer. Returns the bond.
    ///         Another challenge is allowed while `block.timestamp < readyAt`.
    function expireChallenge(uint256 tokenId) external nonReentrant {
        Record storage r = _records[tokenId];
        if (!r.challengeOpen) revert NoChallenge();
        if (block.timestamp < r.respondBy) revert ChallengeWindowOpen();

        address challenger = r.challenger;
        uint256 bond = r.challengerBond;
        r.challengeOpen = false;
        r.challenger = address(0);
        r.challengerBond = 0;
        r.evidenceHash = bytes32(0);
        r.respondBy = 0;
        bondsHeld -= bond;

        emit ChallengeExpired(tokenId);
        _credit(challenger, bond);
    }

    /// @notice Mark a record Final after the window if no challenge is open and none was upheld.
    ///         Credits the operator escrow back and confirms the skill solve.
    function finalize(uint256 tokenId) external nonReentrant {
        Record storage r = _records[tokenId];
        if (!r.known) revert InvalidParams();
        if (r.upheld) revert AlreadyRevoked();
        if (r.finalized) revert AlreadyFinal();
        if (r.challengeOpen) revert ChallengeStillOpen();
        if (block.timestamp < r.readyAt) revert ChallengeWindowOpen();

        if (skill.isRevoked(r.agentId)) {
            r.upheld = true;
            uint256 penalty = _releaseEscrow(r);
            if (penalty != 0) {
                _credit(treasury, penalty);
            }
            emit ChallengeResolved(tokenId, true, bytes32(0));
            emit Revoked(tokenId, bytes32(0));
            return;
        }

        r.finalized = true;
        uint256 escrow = _releaseEscrow(r);
        skill.confirmSolve(r.agentId, r.vulnClass);
        emit Finalized(tokenId);
        _credit(r.operator, escrow);
    }

    /// @notice Pull credited ETH (returned bonds, slashed escrow, protocol rewards, treasury).
    function withdraw() external nonReentrant {
        uint256 amount = withdrawable[msg.sender];
        if (amount == 0) revert InvalidParams();
        withdrawable[msg.sender] = 0;
        claimable -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        if (!ok) revert PayFailed();
        emit Withdrawn(msg.sender, amount);
    }

    // ---------------------------------------------------------------------
    // Views
    // ---------------------------------------------------------------------

    function status(uint256 tokenId) public view returns (RecordStatus) {
        Record storage r = _records[tokenId];
        if (!r.known) return RecordStatus.None;
        if (r.upheld || skill.isRevoked(r.agentId)) return RecordStatus.Revoked;
        if (r.challengeOpen) return RecordStatus.Challenged;
        if (r.finalized || block.timestamp >= r.readyAt) return RecordStatus.Final;
        return RecordStatus.Pending;
    }

    /// @notice True once an upheld verdict has flagged this collectible. The NFT is not burned.
    function flagged(uint256 tokenId) external view returns (bool) {
        return _records[tokenId].upheld;
    }

    function record(uint256 tokenId) external view returns (Record memory) {
        return _records[tokenId];
    }

    function submissionHashOf(uint256 tokenId) external view returns (bytes32) {
        return _records[tokenId].submissionHash;
    }

    function hashChallengeVerdict(
        uint256 tokenId,
        uint256 round,
        address challenger,
        bytes32 evidenceHash,
        bool upheld,
        bytes32 reasonHash
    ) public view returns (bytes32) {
        return _hashTypedDataV4(
            keccak256(
                abi.encode(
                    CHALLENGE_VERDICT_TYPEHASH,
                    tokenId,
                    round,
                    challenger,
                    evidenceHash,
                    upheld,
                    reasonHash
                )
            )
        );
    }

    /// @notice Overload hashing the verdict against the currently active challenge state
    function hashChallengeVerdict(uint256 tokenId, bool upheld, bytes32 reasonHash) public view returns (bytes32) {
        Record storage r = _records[tokenId];
        return hashChallengeVerdict(tokenId, r.round, r.challenger, r.evidenceHash, upheld, reasonHash);
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    // ---------------------------------------------------------------------
    // Admin
    // ---------------------------------------------------------------------

    function setChallengeWindow(uint256 window) external onlyOwner {
        if (window > MAX_WINDOW) revert InvalidParams();
        challengeWindow = window;
        emit ChallengeWindowUpdated(window);
    }

    function setResponseWindow(uint256 window) external onlyOwner {
        if (window == 0 || window > MAX_WINDOW) revert InvalidParams();
        responseWindow = window;
        emit ResponseWindowUpdated(window);
    }

    function setBonds(uint256 challengeBond_, uint256 operatorBond_, uint256 protocolReward_) external onlyOwner {
        challengeBond = challengeBond_;
        operatorBond = operatorBond_;
        protocolReward = protocolReward_;
        emit BondsUpdated(challengeBond_, operatorBond_, protocolReward_);
    }

    function setTreasury(address next) external onlyOwner {
        if (next == address(0)) revert ZeroAddress();
        treasury = next;
        emit TreasuryUpdated(next);
    }

    function fundPool() external payable {
        poolBalance += msg.value;
        emit PoolFunded(msg.sender, msg.value);
    }

    /// @notice Owner can take unused protocol-pool funds. Operator escrows and challenge bonds stay.
    function reclaimPool(address to, uint256 amount) external onlyOwner nonReentrant {
        if (to == address(0) || amount > poolBalance) revert InvalidParams();
        poolBalance -= amount;
        (bool ok,) = to.call{value: amount}("");
        if (!ok) revert PayFailed();
        emit PoolReclaimed(to, amount);
    }

    // ---------------------------------------------------------------------
    // Internals
    // ---------------------------------------------------------------------

    function _verifyVerdict(uint256 tokenId, bool upheld, bytes32 reasonHash, bytes[] calldata signatures)
        internal
        view
    {
        uint256 need = IValidatorSet(collectible).threshold();
        if (signatures.length < need) revert InsufficientSignatures(signatures.length, need);
        address[] memory seen = new address[](signatures.length);
        uint256 valid;
        bytes32 digest = hashChallengeVerdict(tokenId, upheld, reasonHash);
        for (uint256 i; i < signatures.length; ++i) {
            (address recovered, ECDSA.RecoverError err,) = ECDSA.tryRecover(digest, signatures[i]);
            if (err != ECDSA.RecoverError.NoError) revert InvalidSignature();
            if (!IValidatorSet(collectible).isValidator(recovered)) revert NotValidator(recovered);
            for (uint256 j; j < valid; ++j) {
                if (seen[j] == recovered) revert DuplicateSigner(recovered);
            }
            seen[valid] = recovered;
            unchecked {
                ++valid;
            }
        }
        if (valid < need) revert InsufficientSignatures(valid, need);
    }

    /// @dev Escrow first, otherwise a full `protocolReward` from the pool. Never a partial reward.
    function _takeEscrow(Record storage r) private returns (uint256 reward) {
        reward = r.escrow;
        if (reward != 0) {
            r.escrow = 0;
            escrowed -= reward;
            return reward;
        }
        reward = protocolReward;
        if (reward == 0 || poolBalance < reward) return 0;
        poolBalance -= reward;
        return reward;
    }

    function _releaseEscrow(Record storage r) private returns (uint256 escrow) {
        escrow = r.escrow;
        if (escrow == 0) return 0;
        r.escrow = 0;
        escrowed -= escrow;
    }

    function _credit(address to, uint256 amount) private {
        if (amount == 0) return;
        claimable += amount;
        withdrawable[to] += amount;
    }
}
