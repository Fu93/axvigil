"""Agent login and session tokens.

Login is a sign-in-with-Ethereum style challenge: the server issues a nonce, the
agent signs a human-readable message with its wallet (the one that owns its Agent
ID), and the server recovers the address. On success it issues a compact
HMAC-signed session token used as a bearer credential.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address


def new_nonce() -> str:
    return secrets.token_hex(16)


def login_message(address: str, agent_id: int, nonce: str, chain_id: int) -> str:
    """The exact text the agent signs. Deterministic from its parts."""
    return (
        "AxVigil wants you to sign in with your Agent ID.\n\n"
        f"Address: {to_checksum_address(address)}\n"
        f"Agent ID: {agent_id}\n"
        f"Chain ID: {chain_id}\n"
        f"Nonce: {nonce}\n"
        "Statement: Signing in does not authorize any transaction."
    )


def recover_login(message: str, signature: str) -> str:
    return Account.recover_message(encode_defunct(text=message), signature=signature)


class SessionTokens:
    def __init__(self, secret: str, ttl_s: int = 3600):
        self._secret = secret.encode()
        self.ttl_s = ttl_s

    def issue(self, address: str, agent_id: int) -> str:
        payload = {
            "addr": to_checksum_address(address),
            "agentId": int(agent_id),
            "exp": int(time.time()) + self.ttl_s,
        }
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
        sig = self._sign(body)
        return (body + b"." + sig).decode()

    def verify(self, token: str) -> dict | None:
        try:
            body_s, sig_s = token.encode().split(b".", 1)
        except ValueError:
            return None
        if not hmac.compare_digest(sig_s, self._sign(body_s)):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(body_s + b"=" * (-len(body_s) % 4)))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload

    def _sign(self, body: bytes) -> bytes:
        mac = hmac.new(self._secret, body, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(mac).rstrip(b"=")
