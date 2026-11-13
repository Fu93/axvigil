"""Read-only calls against a NEAR testnet RPC. No keys, no mainnet."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_RPC = "https://rpc.testnet.near.org"
ALLOWED_HOSTS = frozenset(
    {
        "rpc.testnet.near.org",
        "test.rpc.fastnear.com",
        "rpc.testnet.fastnear.com",
    }
)


def assert_testnet_rpc(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or "mainnet" in url.lower():
        raise ValueError(f"refusing RPC {url}; NEAR demo is testnet only")
    return url


def assert_testnet_account(account_id: str) -> str:
    if account_id != account_id.lower() or account_id.endswith(".near") or "mainnet" in account_id:
        raise ValueError(f"refusing account {account_id}; NEAR demo is testnet only")
    named = account_id.endswith(".testnet") and " " not in account_id
    implicit = len(account_id) == 64 and all(c in "0123456789abcdef" for c in account_id)
    if not named and not implicit:
        raise ValueError(f"refusing account {account_id}; expected a .testnet account")
    return account_id


def call_view(rpc: str, contract: str, method: str, args: dict[str, Any]) -> Any:
    rpc = assert_testnet_rpc(rpc)
    contract = assert_testnet_account(contract)
    payload = {
        "jsonrpc": "2.0",
        "id": "axvigil",
        "method": "query",
        "params": {
            "request_type": "call_function",
            "finality": "final",
            "account_id": contract,
            "method_name": method,
            "args_base64": base64.b64encode(
                json.dumps(args, separators=(",", ":")).encode("utf-8")
            ).decode("ascii"),
        },
    }
    request = urllib.request.Request(
        rpc,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"testnet RPC request failed: {exc}") from exc
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"]))
    raw = bytes(body["result"]["result"])
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))
