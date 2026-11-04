"""Answer-leak circuit breaker (PRD §5.4).

If a mother's recent pass rate spikes above a threshold on enough volume, the
public answer has likely leaked — stop issuing that mother until an operator
rotates it. Pure read over recorded solves, so it needs no extra state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .store import Store


@dataclass
class BreakerConfig:
    window_s: int = 900          # 15 min rolling window
    min_samples: int = 20        # need enough attempts before judging
    pass_rate_trip: float = 0.9  # >90% passing on volume => likely leaked


class CircuitBreaker:
    def __init__(self, store: Store, config: BreakerConfig | None = None):
        self.store = store
        self.cfg = config or BreakerConfig()
        self._latched_open: set[str] = set()
        self._reset_at: dict[str, float] = {}
        self._global_reset_at: float = 0.0

    def reset(self, mother_id: str | None = None) -> None:
        """Reset the breaker latch for a specific mother (e.g. after operator rotation) or all mothers."""
        now = time.time()
        if mother_id is not None:
            self._latched_open.discard(mother_id)
            self._reset_at[mother_id] = now
        else:
            self._latched_open.clear()
            self._reset_at.clear()
            self._global_reset_at = now

    def state(self, mother_id: str) -> dict:
        reset_time = max(self._reset_at.get(mother_id, 0.0), self._global_reset_at)
        since = reset_time if reset_time > 0 else None
        passed, total = self.store.recent_outcomes(mother_id, self.cfg.window_s, since_override=since)
        rate = (passed / total) if total else 0.0
        tripped = (total >= self.cfg.min_samples and rate >= self.cfg.pass_rate_trip) or (mother_id in self._latched_open)
        if tripped:
            self._latched_open.add(mother_id)
        return {
            "motherId": mother_id,
            "windowSeconds": self.cfg.window_s,
            "recentAttempts": total,
            "recentPassRate": round(rate, 3),
            "open": tripped,  # open = issuance paused
        }

    def is_open(self, mother_id: str) -> bool:
        return self.state(mother_id)["open"]
