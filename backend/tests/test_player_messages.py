"""Clear player-facing errors. Caps and ownership stay the implementations on main."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("SIGNER_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
os.environ.setdefault("VERIFYING_CONTRACT", "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a")
os.environ.setdefault("CHAIN_ID", "97")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("CHALLENGE_CACHE_DIR", tempfile.mkdtemp(prefix="axv-msg-"))
sys.path.insert(0, str(REPO / "backend"))

from eth_account import Account  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from axvigil_backend.app import app, platform, store  # noqa: E402
from axvigil_backend import app as appmod  # noqa: E402
from axvigil_backend import auth as authmod  # noqa: E402
from axvigil_backend.config import Settings  # noqa: E402
from axvigil_backend.protocol import redact_public_grade  # noqa: E402
from axvigil_backend.ratelimit import TokenBucket  # noqa: E402
from axvigil_backend.registry import MemoryRegistry  # noqa: E402

AGENT_PK = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
AGENT = Account.from_key(AGENT_PK).address
OTHER_PK = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"
OTHER = Account.from_key(OTHER_PK).address

client = TestClient(app)


@pytest.fixture(autouse=True)
def _owners_and_buckets():
    reg = MemoryRegistry()
    for agent_id in range(80, 86):
        reg.set_owner(agent_id, AGENT)
    reg.set_owner(71, OTHER)
    previous = (platform.registry, platform.dev_skip_ownership)
    buckets = (appmod._login_bucket, appmod._start_bucket, appmod._submit_bucket)
    platform.registry = reg
    platform.dev_skip_ownership = False
    appmod._login_bucket = TokenBucket(1000, burst=1000)
    appmod._start_bucket = TokenBucket(1000, burst=1000)
    appmod._submit_bucket = TokenBucket(1000, burst=1000)
    yield reg
    platform.registry, platform.dev_skip_ownership = previous
    appmod._login_bucket, appmod._start_bucket, appmod._submit_bucket = buckets


def _login(pk: str, address: str, agent_id: int) -> str:
    challenge = client.get("/v1/auth/challenge", params={"address": address, "agentId": agent_id})
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    sig = Account.sign_message(authmod.encode_defunct(text=body["message"]), private_key=pk).signature.hex()
    logged = client.post("/v1/auth/login", json={
        "address": address, "agentId": agent_id, "nonce": body["nonce"], "signature": sig,
    })
    assert logged.status_code == 200, logged.text
    return logged.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_zero_address_does_not_enable_signing():
    settings = Settings(
        signer_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
        chain_id=97,
        verifying_contract="0x0000000000000000000000000000000000000000",
        challenges_dir=Path("."), verifier_dir=Path("."), variantgen_dir=Path("."),
        mothers_dir=Path("."), challenge_cache_dir=Path("/tmp"), db_path=":memory:",
        session_secret="x", forge_bin="forge", solc_bin=None, grade_timeout_s=1,
        auth_ttl_s=1, session_ttl_s=1, start_rate_per_min=1, submit_rate_per_min=1,
    )
    assert settings.can_sign is False


def test_public_grade_drops_seed_and_test_maps():
    public = redact_public_grade({
        "challengeId": "reentrancy-99",
        "seed": 99,
        "passed": False,
        "log": "pocProvesBug: 1/1 tests passed {'test_secretName()': True}",
    }, "ch_abc")
    assert "seed" not in public
    assert public["challengeId"] == "ch_abc"
    assert "test_secretName" not in public["log"]
    assert "{" not in public["log"]


def test_reward_id_hides_the_seed_and_names_remaining_attempts():
    token = _login(AGENT_PK, AGENT, 80)
    rejected = client.post("/v1/start", headers=_auth(token), json={"motherId": "reentrancy"})
    assert rejected.status_code == 400
    assert "practice=true" in rejected.json()["detail"]
    assert "2 of 2" in rejected.json()["detail"]

    started = client.post("/v1/start", headers=_auth(token), json={})
    assert started.status_code == 200, started.text
    body = started.json()
    row = store.get_session(body["sessionId"])
    assert row["mother_id"] not in body["challengeId"]
    assert str(row["seed"]) not in body["challengeId"]
    assert "seed" not in body
    assert body["pool"] == body["difficulty"]
    assert "1 of 2" in body["quotaMessage"]


def test_expired_other_wallet_and_double_submit_name_what_is_left():
    token = _login(AGENT_PK, AGENT, 81)
    other = _login(OTHER_PK, OTHER, 71)
    started = client.post("/v1/start", headers=_auth(token), json={})
    assert started.status_code == 200, started.text
    session_id = started.json()["sessionId"]

    stolen = client.post(
        "/v1/submit", headers=_auth(other),
        json={"sessionId": session_id, "patch": "contract X {}", "poc": "contract Y {}"},
    )
    assert stolen.status_code == 403
    assert "different wallet" in stolen.json()["detail"]

    store.set_expiry(session_id, time.time() - 5)
    expired = client.post(
        "/v1/submit", headers=_auth(token),
        json={"sessionId": session_id, "patch": "contract X {}", "poc": "contract Y {}"},
    )
    assert expired.status_code == 408
    assert "not refunded" in expired.json()["detail"]
    assert "remaining" in expired.json()["detail"]

    second = client.post("/v1/start", headers=_auth(token), json={})
    assert second.status_code == 200, second.text
    store.finish_session(
        second.json()["sessionId"], passed=True, solve_seconds=1,
        submission_hash="0x" + "44" * 32,
    )
    replay = client.post(
        "/v1/submit", headers=_auth(token),
        json={"sessionId": second.json()["sessionId"], "patch": "contract X {}", "poc": "contract Y {}"},
    )
    assert replay.status_code == 409
    assert "already submitted" in replay.json()["detail"]
    assert "remaining" in replay.json()["detail"]

    capped = client.post("/v1/start", headers=_auth(token), json={})
    assert capped.status_code == 409
    assert "2 of 2" in capped.json()["detail"]


def test_oversized_body_is_not_echoed_and_grading_errors_hide_internals(monkeypatch):
    token = _login(AGENT_PK, AGENT, 82)
    # Agent 70 may already have spent reward attempts in earlier tests. Practice
    # does not spend one, and still exercises the body limit and the grader error.
    started = client.post(
        "/v1/start", headers=_auth(token),
        json={"practice": True, "motherId": "reentrancy"},
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["sessionId"]

    huge = client.post(
        "/v1/submit", headers=_auth(token),
        json={"sessionId": session_id, "patch": "A" * 70_000, "poc": "contract Y {}"},
    )
    assert huge.status_code == 422
    assert "AAAA" not in huge.text
    assert len(huge.text) < 2000

    def boom(*_args, **_kwargs):
        raise RuntimeError("SECRET_PATH /tmp/hidden/test_secretName")

    monkeypatch.setattr("axvigil_verifier.grader.grade", boom)
    leaked = client.post(
        "/v1/submit", headers=_auth(token),
        json={"sessionId": session_id, "patch": "contract X {}", "poc": "contract Y {}"},
    )
    assert leaked.status_code == 500
    assert "SECRET_PATH" not in leaked.text
    assert "test_secretName" not in leaked.text
    assert "Traceback" not in leaked.text


def test_rate_limit_sets_retry_after():
    appmod._login_bucket = TokenBucket(0.01, burst=1)
    first = client.get("/v1/auth/challenge", params={"address": AGENT, "agentId": 70})
    second = client.get("/v1/auth/challenge", params={"address": AGENT, "agentId": 70})
    assert first.status_code == 200
    assert second.status_code == 429
    assert "Wait about" in second.json()["detail"]
    assert second.headers["retry-after"].isdigit()
