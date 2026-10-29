"""EIP-712 signing of MintAuth / SkillAuth.

The domain and type encodings here are cross-checked against the contract's
`hashMintAuth` / `hashSkillAuth` in contracts/test/EIP712Digest.t.sol — the
digests must match exactly or the chain will reject every signature.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak, to_checksum_address

_MINT_TYPES = {
    "MintAuth": [
        {"name": "agentId", "type": "uint256"},
        {"name": "to", "type": "address"},
        {"name": "vulnClass", "type": "uint8"},
        {"name": "difficulty", "type": "uint8"},
        {"name": "pool", "type": "uint8"},
        {"name": "submissionHash", "type": "bytes32"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
    ]
}
_SKILL_TYPES = {
    "SkillAuth": [
        {"name": "agentId", "type": "uint256"},
        {"name": "vulnClass", "type": "uint8"},
        {"name": "difficulty", "type": "uint8"},
        {"name": "submissionHash", "type": "bytes32"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
    ]
}

# Public aliases — the single source of truth for the EIP-712 MintAuth encoding,
# reused by the mint_auth CLI so there is only one definition in the repo.
MINT_AUTH_TYPES = _MINT_TYPES
SKILL_AUTH_TYPES = _SKILL_TYPES
DOMAIN_NAME = "AxVigil"
DOMAIN_VERSION = "1"


def domain(chain_id: int, verifying_contract: str) -> dict:
    return {
        "name": DOMAIN_NAME,
        "version": DOMAIN_VERSION,
        "chainId": int(chain_id),
        "verifyingContract": to_checksum_address(verifying_contract),
    }


def mint_typed_data(chain_id: int, verifying_contract: str, message: dict) -> dict:
    """Full EIP-712 typed-data dict for a MintAuth (for encode_typed_data full_message)."""
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            **MINT_AUTH_TYPES,
        },
        "primaryType": "MintAuth",
        "domain": domain(chain_id, verifying_contract),
        "message": message,
    }


@dataclass
class SignedAuth:
    kind: str  # "mint" | "skill"
    auth: dict
    signature: str  # 0x r||s||v (65 bytes)
    signer: str
    digest: str


class AuthSigner:
    def __init__(self, private_key: str, chain_id: int, verifying_contract: str):
        self._acct = Account.from_key(private_key)
        self.chain_id = int(chain_id)
        self.verifying_contract = to_checksum_address(verifying_contract)

    @property
    def address(self) -> str:
        return self._acct.address

    def _domain(self) -> dict:
        return {
            "name": "AxVigil",
            "version": "1",
            "chainId": self.chain_id,
            "verifyingContract": self.verifying_contract,
        }

    @staticmethod
    def _nonce() -> int:
        # 256-bit random: the contract only requires global uniqueness, and a
        # collision is negligible. No shared state to coordinate between signers.
        return secrets.randbits(256)

    @staticmethod
    def _deadline(ttl_s: int) -> int:
        return int(time.time()) + int(ttl_s)

    def _sign(self, types: dict, message: dict) -> tuple[str, str]:
        signable = encode_typed_data(self._domain(), types, message)
        digest = keccak(b"\x19\x01" + signable.header + signable.body)
        signed = self._acct.sign_message(signable)
        sig = "0x" + signed.signature.hex() if not signed.signature.hex().startswith("0x") else signed.signature.hex()
        return sig, "0x" + digest.hex()

    def sign_mint(
        self, *, agent_id: int, to: str, vuln_class: int, difficulty: int, pool: int,
        submission_hash: str, ttl_s: int = 3600,
    ) -> SignedAuth:
        msg = {
            "agentId": int(agent_id),
            "to": to_checksum_address(to),
            "vulnClass": int(vuln_class),
            "difficulty": int(difficulty),
            "pool": int(pool),
            "submissionHash": _b32(submission_hash),
            "nonce": self._nonce(),
            "deadline": self._deadline(ttl_s),
        }
        sig, digest = self._sign(_MINT_TYPES, msg)
        out = dict(msg)
        out["submissionHash"] = submission_hash
        return SignedAuth("mint", out, sig, self.address, digest)

    def sign_skill(
        self, *, agent_id: int, vuln_class: int, difficulty: int,
        submission_hash: str, ttl_s: int = 3600,
    ) -> SignedAuth:
        msg = {
            "agentId": int(agent_id),
            "vulnClass": int(vuln_class),
            "difficulty": int(difficulty),
            "submissionHash": _b32(submission_hash),
            "nonce": self._nonce(),
            "deadline": self._deadline(ttl_s),
        }
        sig, digest = self._sign(_SKILL_TYPES, msg)
        out = dict(msg)
        out["submissionHash"] = submission_hash
        return SignedAuth("skill", out, sig, self.address, digest)


def _b32(h: str) -> bytes:
    h = h[2:] if h.startswith("0x") else h
    b = bytes.fromhex(h)
    if len(b) != 32:
        raise ValueError("submissionHash must be 32 bytes")
    return b
