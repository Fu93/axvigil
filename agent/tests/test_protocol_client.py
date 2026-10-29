"""Drives the reference PlatformClient against the in-process backend app:
login → start → (reassemble source) → submit the reference solution → authorize →
status / leaderboard. This is the single happy-path flow implementation.

Skips the forge-dependent part if forge/solc are absent.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Configure the backend app BEFORE importing it.
os.environ.setdefault("SIGNER_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
os.environ.setdefault("VERIFYING_CONTRACT", "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a")
os.environ.setdefault("CHAIN_ID", "97")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("CHALLENGE_CACHE_DIR", tempfile.mkdtemp(prefix="axv-cache-"))
for p in ("backend", "agent", "variantgen"):
    sys.path.insert(0, str(REPO / p))

from fastapi.testclient import TestClient  # noqa: E402
from axvigil_backend.app import app, platform  # noqa: E402
from axvigil_backend.registry import MemoryRegistry  # noqa: E402
from axvigil_agent.protocol_client import PlatformClient  # noqa: E402

sys.path.insert(0, str(REPO / "verifier"))
from axvigil_verifier.toolchain import discover_solc, forge_executable  # noqa: E402

_forge = forge_executable()
_solc = discover_solc()

AGENT_PK = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
_owners = MemoryRegistry()
_owners.set_owner(1, __import__("eth_account").Account.from_key(AGENT_PK).address)
platform.registry = _owners
platform.dev_skip_ownership = False


def _client() -> PlatformClient:
    return PlatformClient(TestClient(app), AGENT_PK, agent_id=1)


def test_client_info_and_login():
    c = _client()
    info = c.protocol_info()
    assert info["name"] == "AxVigil"
    token = c.login()
    assert token and c.token == token


def test_client_plays_a_full_challenge():
    if not _forge:
        pytest.fail("forge is required. Install foundry; solc is discovered from svm if needed.")
    from variantgen.render import Mother, render_challenge

    c = _client()
    c.login()

    # Choosing the mother is practice mode. Reward challenges are server-assigned
    # and an opened one would consume one of the two lifetime attempts.
    ch = c.start(mother_id="reentrancy", practice=True)
    assert "source" in ch and "solution" not in ch           # agent never gets the solution
    assert c.fetch_source(ch) == ch["source"]                 # fragments reassemble
    from axvigil_backend.app import store
    sess = store.get_session(ch["sessionId"])
    assert "seed" not in ch
    assert sess["mother_id"] not in ch["challengeId"]
    assert str(sess["seed"]) not in ch["challengeId"]
    seed = sess["seed"]

    # reconstruct the reference solution for this exact seed (as an oracle agent would)
    tmp = Path(tempfile.mkdtemp(prefix="axv-sol-"))
    try:
        render_challenge(Mother(REPO / "mothers" / "reentrancy"), seed, tmp)
        patch = (tmp / "solution" / "patched" / ch["targetFile"]).read_text()
        poc = (tmp / "solution" / "poc" / "Poc.t.sol").read_text()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out = c.submit(ch["sessionId"], patch, poc)
    assert out["passed"] is True, out["result"]["log"]
    assert out["result"]["solveSeconds"] is not None
    assert out["authorizable"] is False

    # Practice sessions are graded but not reward-bearing, and they do not
    # consume one of the two lifetime reward attempts.
    from axvigil_agent.protocol_client import PlatformError
    with pytest.raises(PlatformError) as exc:
        c.authorize(ch["sessionId"], action="mint")
    assert exc.value.status == 403
    st = c.status()
    assert st["rewardAttempts"] == 0
    assert st["mintAuthorizations"] == 0
    assert st["solved"] == 0
