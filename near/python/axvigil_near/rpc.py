"""Read-only calls against a NEAR testnet RPC. No keys, no mainnet."""

from __future__ import annotations

import base64
import json
import time
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
    body = _rpc(rpc, payload)
    raw = bytes(body["result"]["result"])
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _rpc(rpc: str, payload: dict[str, Any]) -> dict[str, Any]:
    delay = 2.0
    last: Exception | None = None
    for attempt in range(5):
        request = urllib.request.Request(
            rpc,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code != 429 or attempt == 4:
                raise RuntimeError(f"testnet RPC request failed: {exc}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        except urllib.error.URLError as exc:
            last = exc
            if attempt == 4:
                raise RuntimeError(f"testnet RPC request failed: {exc}") from exc
            time.sleep(delay)
            delay *= 2
            continue
        if "error" in body:
            raise RuntimeError(json.dumps(body["error"]))
        return body
    raise RuntimeError(f"testnet RPC request failed: {last}")


def view_access_key(rpc: str, account_id: str, public_key: str) -> dict[str, Any]:
    rpc = assert_testnet_rpc(rpc)
    account_id = assert_testnet_account(account_id)
    if not public_key.startswith("ed25519:"):
        raise ValueError("public key must start with ed25519:")
    body = _rpc(
        rpc,
        {
            "jsonrpc": "2.0",
            "id": "axvigil",
            "method": "query",
            "params": {
                "request_type": "view_access_key",
                "finality": "final",
                "account_id": account_id,
                "public_key": public_key,
            },
        },
    )
    result = body.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("access key query returned no result")
    return result


def access_key_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Describe a view_access_key result without the nonce."""
    permission = (result or {}).get("permission")
    if permission == "FullAccess" or (isinstance(permission, dict) and "FullAccess" in permission):
        return {"kind": "full_access", "method_names": []}
    if isinstance(permission, dict) and "FunctionCall" in permission:
        call = permission["FunctionCall"] or {}
        return {
            "kind": "function_call",
            "allowance_yocto": call.get("allowance"),
            "receiver_id": call.get("receiver_id"),
            "method_names": list(call.get("method_names") or []),
        }
    return {"kind": "unknown", "method_names": []}
