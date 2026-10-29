"""Who owns an Agent ID.

`ownerOf(uint256)` on the Agent ID registry must equal the wallet that just
signed in. Production reads that from chain RPC. Tests use `MemoryRegistry`.
`AXVIGIL_DEV_SKIP_OWNERSHIP=1` turns the check off and is local dev only.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Callable, Protocol

from eth_utils import keccak, to_checksum_address

# ownerOf(uint256)
OWNER_OF_SELECTOR = keccak(text="ownerOf(uint256)")[:4]


class RegistryUnavailable(Exception):
    """The ownership lookup could not be completed (RPC down, bad response)."""


class AgentRegistry(Protocol):
    def owner_of(self, agent_id: int) -> str | None:
        """Checksum owner, or None if the Agent ID does not exist."""


class MemoryRegistry:
    """Deterministic ownerOf double. Tests grant ownership explicitly."""

    def __init__(self) -> None:
        self._owners: dict[int, str] = {}

    def set_owner(self, agent_id: int, address: str) -> None:
        self._owners[int(agent_id)] = to_checksum_address(address)

    def owner_of(self, agent_id: int) -> str | None:
        return self._owners.get(int(agent_id))


def _post_json(url: str, payload: dict, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class RpcRegistry:
    """`eth_call` of `ownerOf(agentId)` on `registry`."""

    def __init__(self, rpc_url: str, registry: str, transport: Callable[[str, dict], dict] | None = None):
        self.rpc_url = rpc_url
        self.registry = to_checksum_address(registry)
        self._transport = transport or _post_json

    def owner_of(self, agent_id: int) -> str | None:
        data = "0x" + OWNER_OF_SELECTOR.hex() + int(agent_id).to_bytes(32, "big").hex()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_call",
            "params": [{"to": self.registry, "data": data}, "latest"],
        }
        try:
            body = self._transport(self.rpc_url, payload)
        except Exception as exc:
            raise RegistryUnavailable(str(exc)) from exc
        if not isinstance(body, dict):
            raise RegistryUnavailable("RPC response was not an object")
        if body.get("error"):
            # A revert from ownerOf means the token does not exist.
            return None
        raw = body.get("result")
        if not isinstance(raw, str) or raw in ("0x", "0x0"):
            return None
        hexbody = raw[2:] if raw.startswith("0x") else raw
        if len(hexbody) < 40:
            return None
        addr = "0x" + hexbody[-40:]
        if int(addr, 16) == 0:
            return None
        return to_checksum_address(addr)


def rpc_registry_from_env(agent_registry: str | None, rpc_url: str | None) -> RpcRegistry | None:
    if not agent_registry or not rpc_url:
        return None
    return RpcRegistry(rpc_url, agent_registry)
