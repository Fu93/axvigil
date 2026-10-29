"""Reward caps and the difficulty -> pool ladder.

A production Agent ID gets two reward attempts. Opening a server-assigned session
consumes one, whether the agent later passes, fails, or abandons it. Each passed
attempt can be authorized once, as a mint, and the pool is the difficulty:

    0 BASIC     -> pool 0  (uniform)
    1 ADVANCED  -> pool 1  (better)
    2 LEGENDARY -> pool 2  (best)

The contract enforces the same mapping, so a signature cannot split them.
"""

from __future__ import annotations

MAX_REWARD_ATTEMPTS = 2
MAX_MINTS_PER_AGENT = 2


def pool_for_difficulty(difficulty: int) -> int:
    difficulty = int(difficulty)
    if difficulty not in (0, 1, 2):
        raise ValueError(f"difficulty out of range: {difficulty}")
    return difficulty
