"""Fast unit tests for the abuse guards: rate limiting, circuit breaker, tokens."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from axvigil_backend.ratelimit import TokenBucket
from axvigil_backend.circuit import CircuitBreaker, BreakerConfig
from axvigil_backend.store import Store
from axvigil_backend.auth import SessionTokens


def test_token_bucket_limits_then_refills():
    b = TokenBucket(rate_per_sec=100, burst=3)
    assert [b.allow("k") for _ in range(3)] == [True, True, True]
    assert b.allow("k") is False          # burst exhausted
    time.sleep(0.05)                       # ~5 tokens refill at 100/s
    assert b.allow("k") is True
    assert b.allow("other") is True        # keys are independent


def _record(store: Store, mother: str, passed: int, n: int):
    for i in range(n):
        store.record_solve({
            "session_id": f"s{mother}{passed}{i}", "address": "0xabc", "agent_id": 1,
            "mother_id": mother, "challenge_id": f"{mother}-{i}", "vuln_class": 0,
            "difficulty": 0, "passed": passed, "solve_seconds": 5, "submission_hash": "0x00",
        })


def test_circuit_breaker_trips_on_leak_spike():
    store = Store(":memory:")
    cb = CircuitBreaker(store, BreakerConfig(window_s=3600, min_samples=20, pass_rate_trip=0.9))

    # Below sample threshold: never trips, however high the pass rate.
    _record(store, "reentrancy", 1, 10)
    assert cb.is_open("reentrancy") is False

    # Enough volume at a near-100% pass rate => leak suspected, issuance pauses.
    _record(store, "reentrancy", 1, 15)
    assert cb.is_open("reentrancy") is True

    # A healthy mix stays closed.
    _record(store, "price-manipulation", 1, 8)
    _record(store, "price-manipulation", 0, 20)
    assert cb.is_open("price-manipulation") is False


def test_session_token_roundtrip_and_tamper():
    t = SessionTokens("secret", ttl_s=60)
    tok = t.issue("0xAbC0000000000000000000000000000000000001", 7)
    p = t.verify(tok)
    assert p and p["agentId"] == 7
    assert t.verify(tok + "x") is None            # tampered
    assert t.verify("not.a.token") is None
    assert SessionTokens("other", 60).verify(tok) is None  # wrong secret


def test_expired_token_rejected():
    t = SessionTokens("secret", ttl_s=-1)
    assert t.verify(t.issue("0xAbC0000000000000000000000000000000000001", 1)) is None
