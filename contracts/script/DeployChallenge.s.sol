// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";
import {AxVigilSkill} from "../src/AxVigilSkill.sol";
import {AxVigilChallenge} from "../src/AxVigilChallenge.sol";
import {MockAgentID} from "../src/MockAgentID.sol";
import {IAgentRegistry} from "../src/interfaces/IAgentRegistry.sol";
import {IAxVigilSkill} from "../src/interfaces/IAxVigilSkill.sol";

/// @notice Deploy collectible + skill + challenge book with a threshold validator set.
///         Compiles on its own. Broadcast only when you mean to: chain 97 or local anvil.
///         Env is loaded into `Cfg` so `run` stays under the legacy stack limit (`via_ir` off).
///
/// Required:
///   PRIVATE_KEY     deployer, initial owner of all three contracts
///   SIGNER          validator 1, also the legacy single signer
/// Optional:
///   VALIDATOR_2, VALIDATOR_3, THRESHOLD (default 2, applied only when both extras are set)
///   OWNER, AGENT_REGISTRY, HOURLY_CAP, BASE_URI, UNREVEALED_URI, SEED_HASH
///   CHALLENGE_WINDOW   seconds, default 3600. Use 120 for a short demo. 0 finalizes inside mint.
///   RESPONSE_WINDOW    seconds validators have to sign a verdict, default 3600. Must be non-zero.
///   CHALLENGE_BOND     wei a challenger posts, default 0.001 ether
///   OPERATOR_BOND      wei the minter escrows while the window is non-zero, default 0.002 ether
///   PROTOCOL_REWARD    wei paid from the pool when an upheld mint escrowed nothing, default 0
///   POOL_FUND          wei the deployer puts in the pool during this script, default 0
///   TREASURY           rejected-challenge bond recipient, default OWNER
///
///   forge script script/DeployChallenge.s.sol --rpc-url bsc_testnet --broadcast --legacy --with-gas-price 1000000000
contract DeployChallenge is Script {
    struct Cfg {
        uint256 pk;
        address deployer;
        address signer;
        address owner;
        address registryAddr;
        uint256 hourlyCap;
        string baseURI;
        string unrevealedURI;
        bytes32 seedHash;
        address validator2;
        address validator3;
        uint256 k;
        uint256 challengeWindow;
        uint256 responseWindow;
        uint256 challengeBond;
        uint256 operatorBond;
        uint256 protocolReward;
        uint256 poolFund;
        address treasury;
    }

    struct Out {
        address registry;
        address skill;
        address nft;
        address book;
    }

    function run() external {
        require(block.chainid == 97 || block.chainid == 31337, "DeployChallenge: chain 97 or anvil");
        Cfg memory c = _cfg();
        vm.startBroadcast(c.pk);
        Out memory o = _deploy(c);
        vm.stopBroadcast();
        _log(o);
    }

    function _cfg() internal view returns (Cfg memory c) {
        c.pk = vm.envUint("PRIVATE_KEY");
        c.deployer = vm.addr(c.pk);
        c.signer = vm.envAddress("SIGNER");
        c.owner = vm.envOr("OWNER", c.deployer);
        c.registryAddr = vm.envOr("AGENT_REGISTRY", address(0));
        c.hourlyCap = vm.envOr("HOURLY_CAP", uint256(50));
        c.baseURI = vm.envOr("BASE_URI", string(""));
        c.unrevealedURI = vm.envOr("UNREVEALED_URI", string("ipfs://unrevealed.json"));
        c.seedHash = vm.envOr("SEED_HASH", bytes32(0));
        c.validator2 = vm.envOr("VALIDATOR_2", address(0));
        c.validator3 = vm.envOr("VALIDATOR_3", address(0));
        c.k = vm.envOr("THRESHOLD", uint256(2));
        c.challengeWindow = vm.envOr("CHALLENGE_WINDOW", uint256(1 hours));
        c.responseWindow = vm.envOr("RESPONSE_WINDOW", uint256(1 hours));
        c.challengeBond = vm.envOr("CHALLENGE_BOND", uint256(0.001 ether));
        c.operatorBond = vm.envOr("OPERATOR_BOND", uint256(0.002 ether));
        c.protocolReward = vm.envOr("PROTOCOL_REWARD", uint256(0));
        c.poolFund = vm.envOr("POOL_FUND", uint256(0));
        c.treasury = vm.envOr("TREASURY", c.owner);
    }

    function _deploy(Cfg memory c) internal returns (Out memory o) {
        o.registry = c.registryAddr;
        if (o.registry == address(0)) {
            o.registry = address(new MockAgentID());
        }
        o.skill = address(new AxVigilSkill(IAgentRegistry(o.registry), c.deployer));
        o.nft = address(_collectible(c, o.skill));
        AxVigilSkill skill = AxVigilSkill(o.skill);
        skill.grantRole(skill.MINTER_ROLE(), o.nft);
        o.book = address(_book(c, o.nft, o.skill));
        _wire(c, o);
    }

    function _collectible(Cfg memory c, address skill) internal returns (AxVigilCollectible) {
        uint256[5] memory tiers = [uint256(5444), 1555, 622, 152, 4];
        return new AxVigilCollectible(
            IAgentRegistry(c.registryAddr == address(0) ? _registryOf(skill) : c.registryAddr),
            IAxVigilSkill(skill),
            c.signer,
            c.deployer,
            tiers,
            c.hourlyCap
        );
    }

    /// @dev Registry address after a fresh MockAgentID deploy. Avoids rereading env inside the constructor call.
    function _registryOf(address skill) private view returns (address) {
        return address(AxVigilSkill(skill).agentRegistry());
    }

    function _book(Cfg memory c, address nft, address skill) internal returns (AxVigilChallenge) {
        return new AxVigilChallenge(
            nft,
            IAxVigilSkill(skill),
            c.deployer,
            c.challengeWindow,
            c.responseWindow,
            c.challengeBond,
            c.operatorBond,
            c.protocolReward
        );
    }

    function _wire(Cfg memory c, Out memory o) internal {
        AxVigilCollectible nft = AxVigilCollectible(o.nft);
        AxVigilSkill skill = AxVigilSkill(o.skill);
        AxVigilChallenge book = AxVigilChallenge(o.book);

        nft.setChallengeBook(o.book);
        skill.grantRole(skill.MINTER_ROLE(), o.book);
        if (c.validator2 != address(0)) nft.addValidator(c.validator2);
        if (c.validator3 != address(0)) nft.addValidator(c.validator3);
        if (c.validator2 != address(0) && c.validator3 != address(0)) nft.setThreshold(c.k);
        if (c.treasury != c.deployer) book.setTreasury(c.treasury);
        if (bytes(c.baseURI).length > 0 || bytes(c.unrevealedURI).length > 0) {
            nft.setBaseURI(c.baseURI, c.unrevealedURI);
        }
        if (c.seedHash != bytes32(0)) nft.commitSeed(c.seedHash);
        if (c.poolFund != 0) book.fundPool{value: c.poolFund}();
        if (c.owner != c.deployer) _handoff(c, skill, nft, book);
    }

    function _handoff(Cfg memory c, AxVigilSkill skill, AxVigilCollectible nft, AxVigilChallenge book) internal {
        skill.grantRole(skill.DEFAULT_ADMIN_ROLE(), c.owner);
        skill.renounceRole(skill.DEFAULT_ADMIN_ROLE(), c.deployer);
        nft.transferOwnership(c.owner);
        book.transferOwnership(c.owner);
    }

    function _log(Out memory o) internal view {
        console2.log("DEPLOY_RESULT");
        console2.log("AgentRegistry", o.registry);
        console2.log("AxVigilSkill", o.skill);
        console2.log("AxVigilCollectible", o.nft);
        console2.log("AxVigilChallenge", o.book);
        console2.log("Threshold", AxVigilCollectible(o.nft).threshold());
        console2.log("ChallengeWindow", AxVigilChallenge(o.book).challengeWindow());
        console2.log("Mint verifying contract (MintAuth)", o.nft);
        console2.log("Verdict verifying contract (ChallengeVerdict)", o.book);
    }
}
