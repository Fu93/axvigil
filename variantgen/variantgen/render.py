"""Render a mother template + seed into a concrete, gradeable challenge directory.

The output layout is exactly what verifier/ expects (src/, test/Hidden.t.sol,
solution/patched/<Target>, solution/poc/Poc.t.sol, challenge.json), so everything
downstream — grader, backend, agent — operates on a rendered variant unchanged.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from .fixes import FIXES
from .pools import DISTRACTOR_NAMES, DISTRACTORS, POOLS

SHUF_BEGIN = "// @@SHUF_BEGIN@@"
SHUF_END = "// @@SHUF_END@@"
SHUF_SEP = "// @@SHUF@@"


class Mother:
    def __init__(self, mother_dir: Path):
        self.dir = Path(mother_dir)
        self.meta = json.loads((self.dir / "mother.json").read_text())
        self.src_tmpl = (self.dir / "src.sol.tmpl").read_text()
        self.hidden_tmpl = (self.dir / "hidden.t.sol.tmpl").read_text()
        self.poc_tmpl = (self.dir / "poc.t.sol.tmpl").read_text()

    @property
    def mother_id(self) -> str:
        return self.meta["motherId"]


def _rng(mother_id: str, seed: int) -> random.Random:
    # Deterministic per (mother, seed); distinct mothers never share a stream.
    return random.Random(f"axvigil::{mother_id}::{seed}")


def build_context(mother: Mother, seed: int) -> dict:
    rng = _rng(mother.mother_id, seed)
    ids: dict[str, str] = {}
    used: set[str] = set()
    # Assign each sentinel a concrete name from its pool, without collisions.
    for sentinel, pool_name in mother.meta["identifiers"].items():
        pool = POOLS[pool_name]
        choice = rng.choice(pool)
        # avoid two sentinels mapping to the same concrete name
        tries = 0
        while choice in used and tries < 20:
            choice = rng.choice(pool)
            tries += 1
        used.add(choice)
        ids[sentinel] = choice

    # Distractors: pick a count and a set of structurally-distinct bodies.
    dmin, dmax = mother.meta.get("distractors", [1, 4])
    n = rng.randint(dmin, dmax)
    distractor_blocks: list[str] = []
    names = rng.sample(DISTRACTOR_NAMES, k=min(n, len(DISTRACTOR_NAMES)))
    bodies = rng.sample(DISTRACTORS, k=min(n, len(DISTRACTORS)))
    for name, body in zip(names, bodies):
        distractor_blocks.append(body.format(name="d_" + name))

    return {
        "ids": ids,
        "contract": ids[mother.meta["targetSentinel"]],
        "distractors": distractor_blocks,
        "rng_order": rng,
    }


def _substitute_ids(text: str, ids: dict[str, str]) -> str:
    # Replace longer sentinels first so prefixes don't clobber (e.g. Czz vs CzzX).
    for sentinel in sorted(ids, key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(sentinel)}\b", ids[sentinel], text)
    return text


def _render_shuffle_region(src: str, distractors: list[str], rng: random.Random) -> str:
    if SHUF_BEGIN not in src:
        return src
    pre, rest = src.split(SHUF_BEGIN, 1)
    region, post = rest.split(SHUF_END, 1)
    parts = [p.strip() for p in region.split(SHUF_SEP)]
    blocks = [p for p in parts if p]
    combined = blocks + [d.strip() for d in distractors]
    rng.shuffle(combined)
    # Each block was stripped, so its first line lost the 4-space member indent; restore it.
    combined = ["    " + b if not b.startswith(" ") else b for b in combined]
    body = "\n\n".join(combined)
    # keep consistent indentation/spacing around the region
    return pre.rstrip() + "\n\n" + body + "\n" + post


def render_src(mother: Mother, ctx: dict) -> str:
    src = _render_shuffle_region(mother.src_tmpl, ctx["distractors"], ctx["rng_order"])
    return _substitute_ids(src, ctx["ids"])


def render_challenge(mother: Mother, seed: int, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    ctx = build_context(mother, seed)
    contract = ctx["contract"]
    target_file = f"{contract}.sol"

    rendered_src = render_src(mother, ctx)
    patched_src = FIXES[mother.meta["fixId"]](rendered_src, ctx)
    hidden = _substitute_ids(mother.hidden_tmpl, ctx["ids"])
    poc = _substitute_ids(mother.poc_tmpl, ctx["ids"])

    (out_dir / "src").mkdir(parents=True, exist_ok=True)
    (out_dir / "test").mkdir(parents=True, exist_ok=True)
    (out_dir / "solution" / "patched").mkdir(parents=True, exist_ok=True)
    (out_dir / "solution" / "poc").mkdir(parents=True, exist_ok=True)

    (out_dir / "src" / target_file).write_text(rendered_src)
    (out_dir / "test" / "Hidden.t.sol").write_text(hidden)
    (out_dir / "solution" / "patched" / target_file).write_text(patched_src)
    (out_dir / "solution" / "poc" / "Poc.t.sol").write_text(poc)

    required = [ctx["ids"][s] for s in mother.meta.get("requiredFunctionSentinels", [])]
    challenge = {
        "challengeId": f"{mother.mother_id}-{seed}",
        "motherId": mother.mother_id,
        "seed": seed,
        "vulnClass": mother.meta["vulnClass"],
        "difficulty": mother.meta["difficulty"],
        "targetFile": target_file,
        "contractName": contract,
        "requiredFunctions": required,
        "hiddenTests": "Hidden.t.sol",
        "pragma": mother.meta.get("pragma", "0.8.28"),
        "limits": mother.meta.get("limits", {"maxChangedLines": 40, "maxBytes": 8000}),
        "title": mother.meta.get("title", mother.mother_id),
        "summary": mother.meta.get("summary", ""),
    }
    (out_dir / "challenge.json").write_text(json.dumps(challenge, indent=2))
    return challenge
