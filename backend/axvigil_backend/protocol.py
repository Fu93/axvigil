"""The platform core: issue challenges, grade within a session, authorize rewards.

Challenges are issued server-side — the server picks a mother and a secret seed,
renders a fresh variant, and returns ONLY the vulnerable source. The agent never
sees the mother, the seed, the hidden tests or the reference solution, so there is
nothing to memorize. Grading on submit re-uses the exact rendered variant.
"""

from __future__ import annotations

import secrets
import shutil
import sys
import time
import uuid
from pathlib import Path

from .circuit import CircuitBreaker
from .config import Settings
from .signer import AuthSigner
from .store import Store


class ProtocolError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _ensure_paths(settings: Settings) -> None:
    for p in (str(settings.variantgen_dir), str(settings.verifier_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)


class Platform:
    def __init__(self, settings: Settings, store: Store, signer: AuthSigner | None):
        self.s = settings
        self.store = store
        self.signer = signer
        self.breaker = CircuitBreaker(store)
        _ensure_paths(settings)
        from variantgen.render import Mother  # noqa: E402
        self._Mother = Mother
        self.mothers = {
            d.name: Mother(d)
            for d in sorted(settings.mothers_dir.iterdir())
            if (d / "mother.json").is_file()
        }
        settings.challenge_cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- discovery ----
    def protocol_info(self) -> dict:
        mothers = []
        for mid, m in self.mothers.items():
            mothers.append({
                "motherId": mid,
                "vulnClass": m.meta["vulnClass"],
                "difficulty": m.meta["difficulty"],
                "title": m.meta.get("title", mid),
                "issuancePaused": self.breaker.is_open(mid),
            })
        return {
            "name": "AxVigil",
            "protocolVersion": "1",
            "chainId": self.s.chain_id,
            "verifyingContract": self.s.verifying_contract,
            "signer": self.signer.address if self.signer else None,
            "canAuthorize": self.signer is not None,
            "sessionTtlSeconds": self.s.session_ttl_s,
            "difficulties": {"0": "BASIC", "1": "ADVANCED", "2": "LEGENDARY"},
            "vulnClasses": {"0": "REENTRANCY", "1": "PRICE_MANIPULATION", "2": "ACCESS_CONTROL"},
            "mothers": mothers,
            "verbs": ["login", "protocol_info", "start", "get_fragment", "submit", "authorize", "status", "leaderboard"],
        }

    # ---- issuance ----
    def _render(self, mother, seed: int) -> tuple[Path, dict]:
        from variantgen.render import render_challenge
        challenge_id = f"{mother.mother_id}-{seed}"
        out = self.s.challenge_cache_dir / challenge_id
        if not (out / "challenge.json").is_file():
            render_challenge(mother, seed, out)
        import json
        meta = json.loads((out / "challenge.json").read_text())
        return out, meta

    def start(self, *, address: str, agent_id: int, vuln_class: int | None = None,
              difficulty: int | None = None, mother_id: str | None = None) -> dict:
        # choose a mother
        candidates = list(self.mothers.values())
        if mother_id:
            if mother_id not in self.mothers:
                raise ProtocolError(404, f"unknown mother: {mother_id}")
            candidates = [self.mothers[mother_id]]
        if vuln_class is not None:
            candidates = [m for m in candidates if m.meta["vulnClass"] == vuln_class]
        if difficulty is not None:
            candidates = [m for m in candidates if m.meta["difficulty"] == difficulty]
        candidates = [m for m in candidates if not self.breaker.is_open(m.mother_id)]
        if not candidates:
            raise ProtocolError(409, "no challenge available (filtered out or issuance paused)")

        mother = secrets.choice(candidates)
        seed = secrets.randbelow(1 << 31)
        out, meta = self._render(mother, seed)
        source = (out / "src" / meta["targetFile"]).read_text()

        now = time.time()
        session_id = uuid.uuid4().hex
        self.store.create_session({
            "session_id": session_id, "address": address, "agent_id": agent_id,
            "mother_id": mother.mother_id, "seed": seed, "challenge_id": meta["challengeId"],
            "vuln_class": meta["vulnClass"], "difficulty": meta["difficulty"],
            "started_at": now, "expires_at": now + self.s.session_ttl_s,
        })
        return {
            "sessionId": session_id,
            "challengeId": meta["challengeId"],
            "vulnClass": meta["vulnClass"],
            "difficulty": meta["difficulty"],
            "targetFile": meta["targetFile"],
            "contractName": meta["contractName"],
            "requiredFunctions": meta["requiredFunctions"],
            "pragma": meta["pragma"],
            "limits": meta["limits"],
            "source": source,
            "task": ("Find the single intended vulnerability, return a minimal patch of the "
                     "target file that fixes it without changing the contract name or removing "
                     "any public function, and a Foundry PoC that passes on this contract and "
                     "fails on your patched one."),
            "startedAt": now,
            "expiresAt": now + self.s.session_ttl_s,
            "fragmentCount": _fragment_count(source),
        }

    def get_fragment(self, session_id: str, index: int, address: str) -> dict:
        sess = self._owned_session(session_id, address)
        out = self.s.challenge_cache_dir / sess["challenge_id"]
        import json
        meta = json.loads((out / "challenge.json").read_text())
        source = (out / "src" / meta["targetFile"]).read_text()
        frags = _fragments(source)
        if index < 0 or index >= len(frags):
            raise ProtocolError(416, f"fragment {index} out of range (0..{len(frags)-1})")
        return {"sessionId": session_id, "index": index, "count": len(frags), "data": frags[index]}

    # ---- grading ----
    def submit(self, *, session_id: str, address: str, patch: str, poc: str) -> dict:
        sess = self._owned_session(session_id, address)
        if sess["status"] != "open":
            raise ProtocolError(409, f"session already {sess['status']}")
        if time.time() > sess["expires_at"]:
            self.store.finish_session(session_id, passed=False, solve_seconds=-1, submission_hash="")
            raise ProtocolError(408, "session expired")

        from verifier.grader import grade
        out = self.s.challenge_cache_dir / sess["challenge_id"]
        import json
        meta = json.loads((out / "challenge.json").read_text())
        target = meta["targetFile"]

        tmp = Path(self.s.challenge_cache_dir) / f"_sub-{session_id}"
        try:
            (tmp / "patched").mkdir(parents=True, exist_ok=True)
            (tmp / "poc").mkdir(parents=True, exist_ok=True)
            (tmp / "patched" / target).write_text(patch)
            (tmp / "poc" / "Poc.t.sol").write_text(poc)
            res = grade(out, tmp, seed=sess["seed"], forge_bin=self.s.forge_bin,
                        solc=self.s.solc_bin, timeout_s=self.s.grade_timeout_s)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        solve_seconds = int(time.time() - sess["started_at"])
        self.store.finish_session(session_id, passed=res.passed,
                                  solve_seconds=solve_seconds, submission_hash=res.submissionHash)
        self.store.record_solve({
            "session_id": session_id, "address": address, "agent_id": sess["agent_id"],
            "mother_id": sess["mother_id"], "challenge_id": sess["challenge_id"],
            "vuln_class": sess["vuln_class"], "difficulty": sess["difficulty"],
            "passed": 1 if res.passed else 0, "solve_seconds": solve_seconds,
            "submission_hash": res.submissionHash,
        })
        result = res.to_json()
        result["solveSeconds"] = solve_seconds
        return {"passed": res.passed, "result": result,
                "authorizable": res.passed and self.signer is not None}

    # ---- reward ----
    def authorize(self, *, session_id: str, address: str, to: str | None, action: str) -> dict:
        sess = self._owned_session(session_id, address)
        if sess["status"] != "solved":
            raise ProtocolError(409, "session is not in a solved state")
        if sess["authorized"]:
            raise ProtocolError(409, "already authorized")
        if self.signer is None:
            raise ProtocolError(503, "signing not configured")

        sub = sess["submission_hash"]
        if action == "mint":
            signed = self.signer.sign_mint(
                agent_id=sess["agent_id"], to=to or address, vuln_class=sess["vuln_class"],
                difficulty=sess["difficulty"], pool=1 if sess["difficulty"] >= 1 else 0,
                submission_hash=sub, ttl_s=self.s.auth_ttl_s,
            )
        elif action == "skill":
            signed = self.signer.sign_skill(
                agent_id=sess["agent_id"], vuln_class=sess["vuln_class"],
                difficulty=sess["difficulty"], submission_hash=sub, ttl_s=self.s.auth_ttl_s,
            )
        else:
            raise ProtocolError(400, "action must be 'mint' or 'skill'")

        self.store.mark_authorized(session_id)
        return {"action": signed.kind, "auth": signed.auth, "signature": signed.signature,
                "signer": signed.signer}

    # ---- status ----
    def status(self, agent_id: int) -> dict:
        return self.store.agent_summary(agent_id)

    def leaderboard(self, limit: int = 20) -> list[dict]:
        return self.store.leaderboard(limit)

    # ---- helpers ----
    def _owned_session(self, session_id: str, address: str) -> dict:
        sess = self.store.get_session(session_id)
        if not sess:
            raise ProtocolError(404, "unknown session")
        if sess["address"].lower() != address.lower():
            raise ProtocolError(403, "session belongs to another agent")
        return sess


def _fragment_count(source: str, size: int = 800) -> int:
    return max(1, (len(source) + size - 1) // size)


def _fragments(source: str, size: int = 800) -> list[str]:
    return [source[i:i + size] for i in range(0, len(source), size)] or [""]
