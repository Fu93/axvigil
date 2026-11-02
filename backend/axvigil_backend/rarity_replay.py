"""Replay AxVigilCollectible tier draws off-chain.

Mirrors ``_drawTier``, ``_stage``, ``_released``, and ``hiddenRollHits``.
Used by ``scripts/reveal_and_recompute.py`` to check tokenURI after a seed
is known. Pure: no RPC and no keys.
"""

from __future__ import annotations

TIER_HIDDEN = 4
STAGES = 4
HIDDEN_CHANCE_BPS = 25
HIDDEN_CHANCE_DENOM = 10_000
ART_TIER_MUL = 100_000
ART_CLASS_MUL = 10_000
# Production tier counts: Common, Rare, Epic, Legendary, Hidden.
DEFAULT_TIER_TOTALS = (5444, 1555, 622, 152, 4)
DEFAULT_DRAWABLE = 7773


def weight_multiplier(pool: int, tier: int) -> int:
    if tier == TIER_HIDDEN:
        return 0
    if pool == 0 or tier == 0:
        return 1
    if pool == 1:
        return {1: 2, 2: 4, 3: 8}[tier]
    return {1: 3, 2: 8, 3: 16}[tier]


def stage_of(draw_index: int, drawable: int = DEFAULT_DRAWABLE) -> int:
    if draw_index >= drawable:
        return STAGES - 1
    return (draw_index * STAGES) // drawable


def released(tier: int, stage: int, totals: tuple[int, ...] = DEFAULT_TIER_TOTALS) -> int:
    if tier == TIER_HIDDEN:
        return 0
    n = totals[tier]
    if tier < 3:
        return n
    return (n * (stage + 1)) // STAGES


def hidden_roll_hits(rand: int, pool: int) -> bool:
    if pool != 2:
        return False
    return (rand % HIDDEN_CHANCE_DENOM) < HIDDEN_CHANCE_BPS


def draw_tier(
    draw_index: int,
    pool: int,
    rand: int,
    drawn: list[int],
    totals: tuple[int, ...] = DEFAULT_TIER_TOTALS,
    drawable: int = DEFAULT_DRAWABLE,
) -> tuple[bool, int]:
    """Return (ok, tier) and mutate ``drawn`` the way the contract does."""
    if pool == 2 and drawn[TIER_HIDDEN] < totals[TIER_HIDDEN] and hidden_roll_hits(rand, pool):
        drawn[TIER_HIDDEN] += 1
        return True, TIER_HIDDEN

    stage = stage_of(draw_index, drawable)
    weights = []
    total = 0
    for tier in range(5):
        avail_cap = released(tier, stage, totals)
        avail = 0 if drawn[tier] >= avail_cap else avail_cap - drawn[tier]
        w = avail * weight_multiplier(pool, tier)
        weights.append(w)
        total += w
    if total == 0:
        return False, 0
    rest = rand % total
    for tier, w in enumerate(weights):
        if rest < w:
            drawn[tier] += 1
            return True, tier
        rest -= w
    return False, 0


def art_id(tier: int, vuln_class: int, index: int) -> int:
    return tier * ART_TIER_MUL + vuln_class * ART_CLASS_MUL + index


def replay(tokens: list[dict], totals: tuple[int, ...] = DEFAULT_TIER_TOTALS,
           drawable: int = DEFAULT_DRAWABLE) -> list[dict]:
    """Replay tokens in id order.

    Each token dict needs ``id``, ``pool``, ``vulnClass``, ``rand`` (int).
    Returns one row per token with ``tier`` and ``artId``. Stops early if a
    draw cannot be made (public ladder empty and Hidden not rolled).
    """
    drawn = [0, 0, 0, 0, 0]
    art_count: dict[tuple[int, int], int] = {}
    rows = []
    for token in tokens:
        ok, tier = draw_tier(token["id"] - 1, int(token["pool"]), int(token["rand"]), drawn, totals, drawable)
        if not ok:
            break
        key = (tier, int(token["vulnClass"]))
        index = art_count.get(key, 0)
        art_count[key] = index + 1
        rows.append({
            "id": token["id"],
            "tier": tier,
            "artId": art_id(tier, int(token["vulnClass"]), index),
        })
    return rows
