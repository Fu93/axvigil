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
from axvigil_backend.app import app  # noqa: E402
from axvigil_backend import auth as authmod  # noqa: E402

client = TestClient(app)

_forge = os.environ.get("FORGE") or shutil.which("forge")
_solc = os.environ.get("SOLC") or shutil.which("solc")

AGENT_PK = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
AGENT_ADDR = Account.from_key(AGENT_PK).address


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


@pytest.mark.skipif(not (_forge and _solc), reason="forge/solc not available")
def test_full_flow_start_submit_authorize():
    from variantgen.render import Mother, render_challenge

    token = _login(agent_id=1)
    hdr = {"Authorization": f"Bearer {token}"}

    r = client.post("/v1/start", headers=hdr, json={"motherId": "reentrancy"})
    assert r.status_code == 200, r.text
    ch = r.json()
    assert "source" in ch and "solution" not in ch  # agent never gets the solution
    seed = int(re.search(r"-(\d+)$", ch["challengeId"]).group(1))

    # fragment delivery works and reassembles to the full source
    n = ch["fragmentCount"]
    frags = [client.get("/v1/get_fragment", headers=hdr,
                        params={"sessionId": ch["sessionId"], "index": i}).json()["data"]
             for i in range(n)]
    assert "".join(frags) == ch["source"]

    # reconstruct the reference solution for this exact seed (as an oracle agent)
    tmp = Path(tempfile.mkdtemp(prefix="axv-sol-"))
    try:
        render_challenge(Mother(REPO / "mothers" / "reentrancy"), seed, tmp)
        patch = (tmp / "solution" / "patched" / ch["targetFile"]).read_text()
        poc = (tmp / "solution" / "poc" / "Poc.t.sol").read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    r = client.post("/v1/submit", headers=hdr,
                    json={"sessionId": ch["sessionId"], "patch": patch, "poc": poc})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is True, body["result"]["log"]
    assert body["result"]["solveSeconds"] is not None
    assert body["authorizable"] is True

    # authorize -> a signed MintAuth whose signature recovers to the signer
    r = client.post("/v1/authorize", headers=hdr,
                    json={"sessionId": ch["sessionId"], "action": "mint"})
    assert r.status_code == 200, r.text
    az = r.json()
    assert az["auth"]["submissionHash"] == body["result"]["submissionHash"]
    assert az["signature"].startswith("0x") and len(az["signature"]) == 132

    # authorizing twice is refused
    assert client.post("/v1/authorize", headers=hdr,
                       json={"sessionId": ch["sessionId"], "action": "mint"}).status_code == 409

    # status + leaderboard reflect the solve
    st = client.get("/v1/status", headers=hdr).json()
    assert st["solved"] >= 1 and st["score"] >= 1
    lb = client.get("/v1/leaderboard").json()
    assert any(row["agentId"] == 1 for row in lb)
