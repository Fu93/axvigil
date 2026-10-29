"""Reward attempts, 1:1 mint authorizations, and server-assigned challenges.

No forge: sessions are opened for real (a variant is rendered) and then marked
solved directly so the cap can be tested without grading.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "variantgen"))

from axvigil_backend.config import Settings
from axvigil_backend.protocol import Platform, ProtocolError
from axvigil_backend.registry import MemoryRegistry
from axvigil_backend.signer import AuthSigner
from axvigil_backend.store import Store

SIGNER = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
CONTRACT = "0xF62849F9A0B5Bf2913b396098F7c7019b51A820a"
WALLET_A = "0x00000000000000000000000000000000000000aA"
WALLET_B = "0x00000000000000000000000000000000000000bB"


def _platform(tmp_path) -> tuple[Platform, Store, MemoryRegistry]:
    settings = Settings(
        signer_key=SIGNER,
        chain_id=97,
        verifying_contract=CONTRACT,
        challenges_dir=REPO / "challenges",
        verifier_dir=REPO / "verifier",
        variantgen_dir=REPO / "variantgen",
        mothers_dir=REPO / "mothers",
        challenge_cache_dir=tmp_path / "cache",
        db_path=":memory:",
        session_secret="test-secret",
        forge_bin="forge",
        solc_bin=None,
        grade_timeout_s=30,
        auth_ttl_s=3600,
        session_ttl_s=1800,
        start_rate_per_min=1000,
        submit_rate_per_min=1000,
    )
    store = Store(":memory:")
    signer = AuthSigner(SIGNER, 97, CONTRACT)
    registry = MemoryRegistry()
    return Platform(settings, store, signer, registry=registry), store, registry


def _grant(reg: MemoryRegistry, agent_id: int, address: str = WALLET_A) -> None:
    reg.set_owner(agent_id, address)


def _solve(store: Store, session_id: str, submission_hash: str) -> None:
    store.finish_session(session_id, passed=True, solve_seconds=4, submission_hash=submission_hash)


def test_reward_mothers_cover_every_difficulty(tmp_path):
    platform, _store, _reg = _platform(tmp_path)
    diffs = {m.meta["difficulty"] for m in platform.mothers.values()}
    assert diffs == {0, 1, 2}


def test_reward_start_rejects_caller_choice(tmp_path):
    platform, _store, reg = _platform(tmp_path)
    _grant(reg, 1)
    with pytest.raises(ProtocolError) as exc:
        platform.start(address=WALLET_A, agent_id=1, mother_id="reentrancy")
    assert exc.value.status == 400
    with pytest.raises(ProtocolError) as exc:
        platform.start(address=WALLET_A, agent_id=1, difficulty=0)
    assert exc.value.status == 400


def test_opened_reward_session_counts_and_abandon_does_not_refund(tmp_path):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 7, WALLET_A)
    first = platform.start(address=WALLET_A, agent_id=7)
    # The Agent ID moved to another wallet. The cap still follows the id.
    _grant(reg, 7, WALLET_B)
    second = platform.start(address=WALLET_B, agent_id=7)
    assert first["reward"] is True and second["reward"] is True
    assert first["pool"] == first["difficulty"]
    assert second["pool"] == second["difficulty"]
    assert first["challengeId"] != second["challengeId"]
    assert "seed" not in first
    assert store.reward_attempt_count(7) == 2

    # Abandon both (leave them open / fail them). The slots stay spent.
    store.finish_session(first["sessionId"], passed=False, solve_seconds=1, submission_hash="0x" + "11" * 32)
    with pytest.raises(ProtocolError) as exc:
        platform.start(address=WALLET_B, agent_id=7)
    assert exc.value.status == 409
    assert store.reward_attempt_count(7) == 2

    # Practice does not consume a slot and honors the caller's mother.
    practice = platform.start(address=WALLET_B, agent_id=7, practice=True, mother_id="signature-replay")
    assert practice["practice"] is True and practice["reward"] is False
    assert practice["challengeId"].startswith("signature-replay-")
    assert store.reward_attempt_count(7) == 2


def test_parallel_opens_cannot_exceed_two(tmp_path):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 3)
    barrier = threading.Barrier(8)
    outcomes: list[str] = []
    lock = threading.Lock()

    def go():
        barrier.wait()
        try:
            platform.start(address=WALLET_A, agent_id=3)
            with lock:
                outcomes.append("ok")
        except ProtocolError as exc:
            with lock:
                outcomes.append(str(exc.status))

    threads = [threading.Thread(target=go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 2
    assert outcomes.count("409") == 6
    assert store.reward_attempt_count(3) == 2


def test_one_mint_authorization_per_solve_and_pool_matches_difficulty(tmp_path):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 4)
    sessions = []
    for i in range(2):
        started = platform.start(address=WALLET_A, agent_id=4)
        _solve(store, started["sessionId"], "0x" + f"{i+1:064x}")
        sessions.append(started)

    first = platform.authorize(session_id=sessions[0]["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    assert first["action"] == "mint"
    assert first["auth"]["pool"] == first["auth"]["difficulty"] == sessions[0]["difficulty"]
    assert first["auth"]["agentId"] == 4

    with pytest.raises(ProtocolError) as exc:
        platform.authorize(session_id=sessions[0]["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    assert exc.value.status == 409

    second = platform.authorize(session_id=sessions[1]["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    assert second["auth"]["submissionHash"] != first["auth"]["submissionHash"]
    assert store.mint_authorization_count(4) == 2

    # A practice solve cannot be turned into a third mint.
    practice = platform.start(address=WALLET_A, agent_id=4, practice=True, difficulty=2)
    _solve(store, practice["sessionId"], "0x" + "ab" * 32)
    with pytest.raises(ProtocolError) as exc:
        platform.authorize(session_id=practice["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    assert exc.value.status == 403
    assert store.mint_authorization_count(4) == 2


def test_same_submission_hash_cannot_authorize_twice(tmp_path):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 5)
    a = platform.start(address=WALLET_A, agent_id=5)
    b = platform.start(address=WALLET_A, agent_id=5)
    shared = "0x" + "44" * 32
    _solve(store, a["sessionId"], shared)
    _solve(store, b["sessionId"], shared)
    platform.authorize(session_id=a["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    with pytest.raises(ProtocolError) as exc:
        platform.authorize(session_id=b["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
    assert exc.value.status == 409
    assert store.mint_authorization_count(5) == 1


def test_parallel_authorizations_stay_one_per_session(tmp_path):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 6)
    started = platform.start(address=WALLET_A, agent_id=6)
    # Second attempt so the agent is at the cap, but only one session is solved.
    platform.start(address=WALLET_A, agent_id=6)
    _solve(store, started["sessionId"], "0x" + "55" * 32)

    barrier = threading.Barrier(6)
    outcomes: list[str] = []
    lock = threading.Lock()

    def go():
        barrier.wait()
        try:
            platform.authorize(session_id=started["sessionId"], address=WALLET_A, to=WALLET_A, action="mint")
            with lock:
                outcomes.append("ok")
        except ProtocolError as exc:
            with lock:
                outcomes.append(str(exc.status))

    threads = [threading.Thread(target=go) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert outcomes.count("ok") == 1
    assert store.mint_authorization_count(6) == 1


def test_parallel_submits_grade_once(tmp_path, monkeypatch):
    platform, store, reg = _platform(tmp_path)
    _grant(reg, 8)
    started = platform.start(address=WALLET_A, agent_id=8, practice=True, mother_id="reentrancy")
    calls: list[int] = []
    entered = threading.Event()
    release = threading.Event()

    def slow_grade(*_args, **_kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(3), "grader was not released"

        class Result:
            passed = False
            submissionHash = "0x" + "22" * 32

            def to_json(self):
                return {"passed": False, "submissionHash": self.submissionHash, "log": "graded once"}

        return Result()

    import axvigil_verifier.grader as grader
    monkeypatch.setattr(grader, "grade", slow_grade)

    outcomes: list[object] = []
    lock = threading.Lock()

    def go():
        try:
            platform.submit(
                session_id=started["sessionId"], address=WALLET_A, patch="patch", poc="poc",
            )
            with lock:
                outcomes.append("ok")
        except ProtocolError as exc:
            with lock:
                outcomes.append(exc.status)

    first = threading.Thread(target=go)
    second = threading.Thread(target=go)
    first.start()
    assert entered.wait(3), "first submit never reached the grader"
    second.start()
    second.join(3)
    release.set()
    first.join(3)
    assert calls == [1]
    assert outcomes.count("ok") == 1
    assert outcomes.count(409) == 1
    sess = store.get_session(started["sessionId"])
    assert sess is not None and sess["status"] == "failed"
    # The session is closed. Another submit cannot grade it again.
    with pytest.raises(ProtocolError) as exc:
        platform.submit(session_id=started["sessionId"], address=WALLET_A, patch="patch", poc="poc")
    assert exc.value.status == 409
    assert calls == [1]


def test_server_deals_every_difficulty(tmp_path):
    platform, _store, reg = _platform(tmp_path)
    seen = set()
    for agent_id in range(20, 60):
        _grant(reg, agent_id)
        started = platform.start(address=WALLET_A, agent_id=agent_id)
        seen.add(started["difficulty"])
        assert started["pool"] == started["difficulty"]
    assert seen == {0, 1, 2}
