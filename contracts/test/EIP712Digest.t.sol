// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {console2} from "forge-std/Test.sol";
import {AxVigilBase} from "./utils/AxVigilBase.sol";
import {AxVigilCollectible} from "../src/AxVigilCollectible.sol";

/// @notice Emits the on-chain EIP-712 digests for fixed inputs so the Python signer
///         (backend) can be cross-checked against them. Run with:
///         forge test --match-path test/EIP712Digest.t.sol -vv
contract EIP712DigestTest is AxVigilBase {
    function setUp() public {
        vm.chainId(97); // BSC testnet, so the domain separator matches the backend's
        _deploy(_production(), 50);
    }

    function test_logMintAuthDigest() public view {
        AxVigilCollectible.MintAuth memory a = AxVigilCollectible.MintAuth({
            agentId: 7,
            to: 0x1111111111111111111111111111111111111111,
            vulnClass: 0,
            difficulty: 1,
            pool: 1,
            submissionHash: 0x2222222222222222222222222222222222222222222222222222222222222222,
            nonce: 123,
            deadline: 1893456000
        });
        console2.log("CHAINID", block.chainid);
        console2.log("VERIFYING_CONTRACT", address(nft));
        console2.log("DOMAIN_SEPARATOR");
        console2.logBytes32(nft.domainSeparator());
        console2.log("MINT_DIGEST");
        console2.logBytes32(nft.hashMintAuth(a));
    }
}
