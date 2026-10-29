"""Full agent-protocol flow plus fast unit tests.

The flow test logs in by signing the challenge, receives a server-issued random
variant, reconstructs the reference solution for that exact seed (as an oracle
agent would), submits, and authorizes — proving login -> start -> submit ->
authorize end to end. Skips the forge-dependent part if forge/solc are absent.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Configure the app BEFORE importing it.
os.environ.setdefault("SIGNER_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
os.environ.setdefault("VERIFYING_CONTRACT", "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a")
os.environ.setdefault("CHAIN_ID", "97")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("CHALLENGE_CACHE_DIR", tempfile.mkdtemp(prefix="axv-cache-"))
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "variantgen"))

from fastapi.testclient import TestClient  # noqa: E402
from eth_account import Account  # noqa: E402
from axvigil_backend.app import app, platform  # noqa: E402
from axvigil_backend import auth as authmod  # noqa: E402
from axvigil_backend.registry import MemoryRegistry  # noqa: E402

client = TestClient(app)

_forge = os.environ.get("FORGE") or shutil.which("forge")
_solc = os.environ.get("SOLC") or shutil.which("solc")

AGENT_PK = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
AGENT_ADDR = Account.from_key(AGENT_PK).address
_owners = MemoryRegistry()
_owners.set_owner(1, AGENT_ADDR)
platform.registry = _owners
platform.dev_skip_ownership = False


def _login(agent_id: int = 1) -> str:
    r = client.get("/v1/auth/challenge", params={"address": AGENT_ADDR, "agentId": agent_id})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    nonce = r.json()["nonce"]
    sig = Account.sign_message(authmod.encode_defunct(text=msg), private_key=AGENT_PK).signature.hex()
    r = client.post("/v1/auth/login", json={"address": AGENT_ADDR, "agentId": agent_id,
                                            "nonce": nonce, "signature": sig})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_protocol_info_lists_mothers():
    info = client.get("/v1/protocol_info").json()
    assert info["name"] == "AxVigil"
    ids = {m["motherId"] for m in info["mothers"]}
    assert {"reentrancy", "price-manipulation", "access-control"} <= ids
    assert "start" in info["verbs"] and "authorize" in info["verbs"]


def test_login_rejects_bad_signature():
    r = client.get("/v1/auth/challenge", params={"address": AGENT_ADDR, "agentId": 1})
    nonce = r.json()["nonce"]
    r = client.post("/v1/auth/login", json={"address": AGENT_ADDR, "agentId": 1,
                                            "nonce": nonce, "signature": "0x" + "11" * 65})
    assert r.status_code == 401


def test_protected_endpoints_need_token():
    assert client.post("/v1/start", json={}).status_code == 401
    assert client.get("/v1/status").status_code == 401


def test_nonce_is_single_use():
    r = client.get("/v1/auth/challenge", params={"address": AGENT_ADDR, "agentId": 1})
    nonce, msg = r.json()["nonce"], r.json()["message"]
    sig = Account.sign_message(authmod.encode_defunct(text=msg), private_key=AGENT_PK).signature.hex()
    body = {"address": AGENT_ADDR, "agentId": 1, "nonce": nonce, "signature": sig}
    assert client.post("/v1/auth/login", json=body).status_code == 200
    assert client.post("/v1/auth/login", json=body).status_code == 401  # replay rejected


# The full login → start → submit → authorize flow is exercised through the
# reference client in agent/tests/test_protocol_client.py (one flow implementation).
