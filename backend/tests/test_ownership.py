"""Agent ID ownership: login, reward start, and authorize all require ownerOf."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("SIGNER_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
os.environ.setdefault("VERIFYING_CONTRACT", "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a")
os.environ.setdefault("CHAIN_ID", "97")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("CHALLENGE_CACHE_DIR", tempfile.mkdtemp(prefix="axv-own-"))
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "variantgen"))

from eth_account import Account  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from axvigil_backend.app import app, platform  # noqa: E402
from axvigil_backend import auth as authmod  # noqa: E402
from axvigil_backend.config import Settings  # noqa: E402
from axvigil_backend.protocol import Platform, ProtocolError  # noqa: E402
from axvigil_backend.registry import (  # noqa: E402
    OWNER_OF_SELECTOR,
    MemoryRegistry,
    RegistryUnavailable,
    RpcRegistry,
)
from axvigil_backend.signer import AuthSigner  # noqa: E402
from axvigil_backend.store import Store  # noqa: E402

AGENT_PK = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
AGENT = Account.from_key(AGENT_PK).address
OTHER = "0x00000000000000000000000000000000000000bB"
SIGNER = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
CONTRACT = "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a"

client = TestClient(app)


@pytest.fixture
def owners():
    reg = MemoryRegistry()
    previous = (platform.registry, platform.dev_skip_ownership)
    platform.registry = reg
    platform.dev_skip_ownership = False
    yield reg
    platform.registry, platform.dev_skip_ownership = previous


def _settings(tmp_path, *, skip: bool = False, registry: str | None = None, rpc: str | None = None) -> Settings:
    return Settings(
        signer_key=SIGNER, chain_id=97, verifying_contract=CONTRACT,
        challenges_dir=REPO / "challenges", verifier_dir=REPO / "verifier",
        variantgen_dir=REPO / "variantgen", mothers_dir=REPO / "mothers",
        challenge_cache_dir=tmp_path / "cache", db_path=":memory:",
        session_secret="test-secret", forge_bin="forge", solc_bin=None,
        grade_timeout_s=30, auth_ttl_s=3600, session_ttl_s=1800,
        start_rate_per_min=1000, submit_rate_per_min=1000,
        agent_registry=registry, rpc_url=rpc, dev_skip_ownership=skip,
    )


def _login(agent_id: int, address: str = AGENT, pk: str = AGENT_PK) -> tuple[int, dict]:
    challenge = client.get("/v1/auth/challenge", params={"address": address, "agentId": agent_id})
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    sig = Account.sign_message(authmod.encode_defunct(text=body["message"]), private_key=pk).signature.hex()
    response = client.post("/v1/auth/login", json={
        "address": address, "agentId": agent_id, "nonce": body["nonce"], "signature": sig,
    })
    return response.status_code, response.json()


def test_owner_of_selector_is_the_erc721_id():
    assert OWNER_OF_SELECTOR.hex() == "6352211e"


def test_login_rejects_an_agent_id_the_wallet_does_not_own(owners):
    owners.set_owner(1, OTHER)
    status, body = _login(1)
    assert status == 403
    assert "does not own" in body["detail"]


def test_login_accepts_the_registry_owner(owners):
    owners.set_owner(1, AGENT)
    status, body = _login(1)
    assert status == 200, body
    assert body["agentId"] == 1


def test_missing_registry_is_not_a_free_pass(tmp_path):
    bare = Platform(_settings(tmp_path), Store(":memory:"), None)
    assert bare.ownership_mode() == "unconfigured"
    with pytest.raises(ProtocolError) as exc:
        bare.require_owner(1, AGENT)
    assert exc.value.status == 503


def test_dev_skip_flag_is_the_only_bypass(tmp_path):
    skipped = Platform(_settings(tmp_path, skip=True), Store(":memory:"), None)
    assert skipped.ownership_mode() == "dev-skip"
    skipped.require_owner(1, AGENT)  # does not raise


def test_stranger_cannot_spend_a_reward_attempt_or_authorize(tmp_path):
    reg = MemoryRegistry()
    reg.set_owner(9, AGENT)
    plat = Platform(_settings(tmp_path), Store(":memory:"), AuthSigner(SIGNER, 97, CONTRACT), registry=reg)
    with pytest.raises(ProtocolError) as exc:
        plat.start(address=OTHER, agent_id=9)
    assert exc.value.status == 403
    assert plat.store.reward_attempt_count(9) == 0

    started = plat.start(address=AGENT, agent_id=9)
    plat.store.finish_session(started["sessionId"], passed=True, solve_seconds=1, submission_hash="0x" + "11" * 32)
    # Ownership moved away before authorize.
    reg.set_owner(9, OTHER)
    with pytest.raises(ProtocolError) as exc:
        plat.authorize(session_id=started["sessionId"], address=AGENT, to=AGENT, action="mint")
    assert exc.value.status == 403
    assert plat.store.mint_authorization_count(9) == 0
    # The new owner does not hold this session, so they cannot mint it either.
    with pytest.raises(ProtocolError) as exc:
        plat.authorize(session_id=started["sessionId"], address=OTHER, to=OTHER, action="mint")
    assert exc.value.status == 403


def test_rpc_registry_decodes_owner_of_and_treats_reverts_as_missing():
    seen = {}

    def transport(url, payload):
        seen["url"] = url
        seen["data"] = payload["params"][0]["data"]
        if payload["params"][0]["data"].endswith("0" * 63 + "2"):
            return {"jsonrpc": "2.0", "id": 1, "error": {"code": 3, "message": "execution reverted"}}
        return {
            "jsonrpc": "2.0", "id": 1,
            "result": "0x" + "00" * 12 + AGENT[2:].lower(),
        }

    rpc = RpcRegistry("http://rpc.test", "0x00000000000000000000000000000000000000aa", transport=transport)
    assert rpc.owner_of(1) == AGENT
    assert seen["data"].startswith("0x6352211e")
    assert rpc.owner_of(2) is None

    def down(_url, _payload):
        raise TimeoutError("rpc down")

    broken = RpcRegistry("http://rpc.test", "0x00000000000000000000000000000000000000aa", transport=down)
    with pytest.raises(RegistryUnavailable):
        broken.owner_of(1)


def test_rpc_rate_limit_is_unavailable_not_a_missing_token(tmp_path):
    def transport(_url, _payload):
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32005, "message": "rate limit exceeded"}}

    rpc = RpcRegistry("http://rpc.test", "0x00000000000000000000000000000000000000aa", transport=transport)
    with pytest.raises(RegistryUnavailable):
        rpc.owner_of(1)
    plat = Platform(_settings(tmp_path), Store(":memory:"), None, registry=rpc)
    with pytest.raises(ProtocolError) as exc:
        plat.require_owner(1, AGENT)
    assert exc.value.status == 503
    assert "does not own" not in exc.value.detail


def test_registry_post_sets_an_explicit_user_agent(monkeypatch):
    import urllib.request
    from axvigil_backend.registry import USER_AGENT, _post_json

    captured = {}

    class _Resp:
        def read(self):
            return b'{"jsonrpc":"2.0","id":1,"result":"0x1"}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(req, timeout=10):
        captured["ua"] = req.get_header("User-agent")
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    _post_json("http://rpc.test", {"jsonrpc": "2.0"})
    assert captured["ua"] == USER_AGENT
    assert "python-urllib" not in captured["ua"].lower()
