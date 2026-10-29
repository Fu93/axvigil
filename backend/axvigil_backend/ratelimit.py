"""Per-key token-bucket rate limiting (in-process).

Keeps NONCE-style 429 storms and brute-force submits in check (PRD §5.4). Keys
are usually the agent address or the client IP.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = float(rate_per_sec)
        self.burst = int(burst)
        self._state: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (float(self.burst), now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if tokens >= cost:
                self._state[key] = (tokens - cost, now)
                return True
            self._state[key] = (tokens, now)
            return False

    def retry_after(self, key: str, cost: float = 1.0) -> float:
        with self._lock:
            tokens, _ = self._state.get(key, (float(self.burst), time.monotonic()))
            deficit = max(0.0, cost - tokens)
            return deficit / self.rate if self.rate > 0 else 0.0
