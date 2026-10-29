"""SQLite persistence for the AxVigil platform.

One file, WAL mode, a module lock for the single-process FastAPI app. Holds
agents, play sessions (the server-held seed lives here and is never sent to the
agent), recorded solves, login nonces and issued authorizations.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  address     TEXT PRIMARY KEY,
  agent_id    INTEGER NOT NULL,
  first_seen  REAL NOT NULL,
  last_seen   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  session_id   TEXT PRIMARY KEY,
  address      TEXT NOT NULL,
  agent_id     INTEGER NOT NULL,
  mother_id    TEXT NOT NULL,
  seed         INTEGER NOT NULL,            -- server-held; never returned to the agent
  challenge_id TEXT NOT NULL,
  vuln_class   INTEGER NOT NULL,
  difficulty   INTEGER NOT NULL,
  started_at   REAL NOT NULL,
  expires_at   REAL NOT NULL,
  status       TEXT NOT NULL,               -- open | solved | failed | expired
  submitted_at REAL,
  solve_seconds INTEGER,
  submission_hash TEXT,
  authorized   INTEGER NOT NULL DEFAULT 0,
  reward       INTEGER NOT NULL DEFAULT 1    -- 1 = server-assigned reward attempt (counts toward the cap)
);
CREATE TABLE IF NOT EXISTS authorizations (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      TEXT NOT NULL UNIQUE,
  agent_id        INTEGER NOT NULL,
  submission_hash TEXT NOT NULL UNIQUE,
  difficulty      INTEGER NOT NULL,
  pool            INTEGER NOT NULL,
  signature       TEXT NOT NULL,
  created_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS solves (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id   TEXT NOT NULL,
  address      TEXT NOT NULL,
  agent_id     INTEGER NOT NULL,
  mother_id    TEXT NOT NULL,
  challenge_id TEXT NOT NULL,
  vuln_class   INTEGER NOT NULL,
  difficulty   INTEGER NOT NULL,
  passed       INTEGER NOT NULL,
  solve_seconds INTEGER,
  submission_hash TEXT,
  created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS nonces (
  nonce      TEXT PRIMARY KEY,
  address    TEXT NOT NULL,
  issued_at  REAL NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_addr ON sessions(address);
CREATE INDEX IF NOT EXISTS idx_sessions_agent_reward ON sessions(agent_id, reward);
CREATE INDEX IF NOT EXISTS idx_solves_agent ON solves(agent_id);
CREATE INDEX IF NOT EXISTS idx_solves_mother_time ON solves(mother_id, created_at);
CREATE INDEX IF NOT EXISTS idx_auth_agent ON authorizations(agent_id);
"""


class QuotaExceeded(Exception):
    """The Agent ID already has two reward attempts or two mint authorizations."""


class AlreadyAuthorized(Exception):
    pass


class DuplicateSubmission(Exception):
    """This submissionHash was already used for an authorization."""


class NotRewardSession(Exception):
    pass


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if str(path) != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            self._ensure_reward_column()
            self._conn.commit()

    def _ensure_reward_column(self) -> None:
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(sessions)")}
        if "reward" not in cols:
            self._conn.execute("ALTER TABLE sessions ADD COLUMN reward INTEGER NOT NULL DEFAULT 1")

    # ---- agents ----
    def upsert_agent(self, address: str, agent_id: int) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO agents(address, agent_id, first_seen, last_seen) VALUES(?,?,?,?) "
                "ON CONFLICT(address) DO UPDATE SET last_seen=?, agent_id=?",
                (address, agent_id, now, now, now, agent_id),
            )
            self._conn.commit()

    # ---- login nonces ----
    def put_nonce(self, nonce: str, address: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO nonces(nonce, address, issued_at, used) VALUES(?,?,?,0)",
                (nonce, address, time.time()),
            )
            self._conn.commit()

    def consume_nonce(self, nonce: str, address: str, ttl_s: int = 600) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT address, issued_at, used FROM nonces WHERE nonce=?", (nonce,)
            ).fetchone()
            if not row or row["used"] or row["address"] != address:
                return False
            if time.time() - row["issued_at"] > ttl_s:
                return False
            self._conn.execute("UPDATE nonces SET used=1 WHERE nonce=?", (nonce,))
            self._conn.commit()
            return True

    # ---- sessions ----
    def reward_attempt_count(self, agent_id: int) -> int:
        with self._lock:
            return int(self._conn.execute(
                "SELECT COUNT(*) AS n FROM sessions WHERE agent_id=? AND reward=1", (agent_id,)
            ).fetchone()["n"])

    def mint_authorization_count(self, agent_id: int) -> int:
        with self._lock:
            return int(self._conn.execute(
                "SELECT COUNT(*) AS n FROM authorizations WHERE agent_id=?", (agent_id,)
            ).fetchone()["n"])

    def create_session(self, s: dict[str, Any]) -> None:
        """Insert a session. Reward sessions are capped at 2 per Agent ID, counted at open
        time so abandoning one does not free the slot."""
        reward = 1 if s.get("reward", True) else 0
        with self._lock:
            if reward:
                n = int(self._conn.execute(
                    "SELECT COUNT(*) AS n FROM sessions WHERE agent_id=? AND reward=1",
                    (s["agent_id"],),
                ).fetchone()["n"])
                if n >= 2:
                    raise QuotaExceeded(
                        "reward cap reached: 2 server-assigned challenges per Agent ID"
                    )
            row = dict(s)
            row["reward"] = reward
            self._conn.execute(
                "INSERT INTO sessions(session_id,address,agent_id,mother_id,seed,challenge_id,"
                "vuln_class,difficulty,started_at,expires_at,status,reward) "
                "VALUES(:session_id,:address,:agent_id,:mother_id,:seed,:challenge_id,"
                ":vuln_class,:difficulty,:started_at,:expires_at,'open',:reward)", row,
            )
            self._conn.commit()

    def commit_mint_authorization(
        self, *, session_id: str, agent_id: int, submission_hash: str,
        difficulty: int, pool: int, signature: str,
    ) -> None:
        """Record one mint authorization. One per solved reward session, at most two per
        Agent ID, and a submissionHash can be authorized only once."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            if not row["reward"]:
                raise NotRewardSession()
            if row["status"] != "solved":
                raise ValueError("session is not solved")
            if int(row["agent_id"]) != int(agent_id):
                raise ValueError("agent mismatch")
            if row["submission_hash"] != submission_hash:
                raise ValueError("submission hash mismatch")
            if row["authorized"]:
                raise AlreadyAuthorized()
            n = int(self._conn.execute(
                "SELECT COUNT(*) AS n FROM authorizations WHERE agent_id=?", (agent_id,)
            ).fetchone()["n"])
            if n >= 2:
                raise QuotaExceeded("mint authorization cap reached")
            taken = self._conn.execute(
                "SELECT 1 FROM authorizations WHERE submission_hash=?", (submission_hash,)
            ).fetchone()
            if taken:
                raise DuplicateSubmission()
            self._conn.execute(
                "INSERT INTO authorizations(session_id,agent_id,submission_hash,difficulty,pool,"
                "signature,created_at) VALUES(?,?,?,?,?,?,?)",
                (session_id, agent_id, submission_hash, difficulty, pool, signature, time.time()),
            )
            self._conn.execute(
                "UPDATE sessions SET authorized=1 WHERE session_id=? AND authorized=0",
                (session_id,),
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def claim_for_grading(self, session_id: str, address: str, now: float) -> tuple[str, Optional[dict]]:
        """Move an open session to 'grading' in one locked transaction.

        Returns (code, session). code is ok, missing, forbidden, expired, or closed.
        A second caller sees status grading and gets closed, so it cannot start
        another grade of the same session.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                return "missing", None
            sess = dict(row)
            if sess["address"].lower() != address.lower():
                return "forbidden", sess
            if sess["status"] == "open" and float(sess["expires_at"]) < now:
                self._conn.execute(
                    "UPDATE sessions SET status='expired', submitted_at=? "
                    "WHERE session_id=? AND status='open'",
                    (now, session_id),
                )
                self._conn.commit()
                sess["status"] = "expired"
                return "expired", sess
            if sess["status"] != "open":
                return "closed", sess
            cur = self._conn.execute(
                "UPDATE sessions SET status='grading' WHERE session_id=? AND status='open'",
                (session_id,),
            )
            self._conn.commit()
            if cur.rowcount != 1:
                again = self._conn.execute(
                    "SELECT * FROM sessions WHERE session_id=?", (session_id,)
                ).fetchone()
                return "closed", dict(again) if again else sess
            sess["status"] = "grading"
            return "ok", sess

    def finish_grading(self, session_id: str, *, passed: bool, solve_seconds: int,
                       submission_hash: str) -> bool:
        """Persist the single grade. Only a session currently in 'grading' matches."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE sessions SET status=?, submitted_at=?, solve_seconds=?, submission_hash=? "
                "WHERE session_id=? AND status='grading'",
                ("solved" if passed else "failed", time.time(), solve_seconds, submission_hash, session_id),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def finish_session(self, session_id: str, *, passed: bool, solve_seconds: int,
                       submission_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET status=?, submitted_at=?, solve_seconds=?, submission_hash=? "
                "WHERE session_id=?",
                ("solved" if passed else "failed", time.time(), solve_seconds, submission_hash, session_id),
            )
            self._conn.commit()

    def mark_authorized(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE sessions SET authorized=1 WHERE session_id=?", (session_id,))
            self._conn.commit()

    # ---- solves ----
    def record_solve(self, s: dict[str, Any]) -> None:
        s = dict(s)
        s["created_at"] = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO solves(session_id,address,agent_id,mother_id,challenge_id,vuln_class,"
                "difficulty,passed,solve_seconds,submission_hash,created_at) "
                "VALUES(:session_id,:address,:agent_id,:mother_id,:challenge_id,:vuln_class,"
                ":difficulty,:passed,:solve_seconds,:submission_hash,:created_at)", s,
            )
            self._conn.commit()

    def agent_summary(self, agent_id: int) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT passed, difficulty, vuln_class, solve_seconds FROM solves WHERE agent_id=?",
                (agent_id,),
            ).fetchall()
        passed = [r for r in rows if r["passed"]]
        return {
            "agentId": agent_id,
            "attempts": len(rows),
            "solved": len(passed),
            "classesSolved": len({r["vuln_class"] for r in passed}),
            "score": sum(_difficulty_points(r["difficulty"]) for r in passed),
            "fastestSolveSeconds": min((r["solve_seconds"] for r in passed if r["solve_seconds"] is not None), default=None),
        }

    def leaderboard(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT agent_id, difficulty, vuln_class, solve_seconds FROM solves WHERE passed=1"
            ).fetchall()
        agg: dict[int, dict] = {}
        for r in rows:
            a = agg.setdefault(r["agent_id"], {"agentId": r["agent_id"], "solved": 0, "score": 0,
                                               "classes": set(), "fastest": None})
            a["solved"] += 1
            a["score"] += _difficulty_points(r["difficulty"])
            a["classes"].add(r["vuln_class"])
            if r["solve_seconds"] is not None:
                a["fastest"] = r["solve_seconds"] if a["fastest"] is None else min(a["fastest"], r["solve_seconds"])
        out = [
            {"agentId": a["agentId"], "solved": a["solved"], "score": a["score"],
             "classesSolved": len(a["classes"]), "fastestSolveSeconds": a["fastest"]}
            for a in agg.values()
        ]
        out.sort(key=lambda x: (-x["score"], -x["classesSolved"], x["fastestSolveSeconds"] or 1e9))
        return out[:limit]

    def recent_outcomes(self, mother_id: str, window_s: int) -> tuple[int, int]:
        """(passed, total) solves for a mother within the last window_s seconds."""
        since = time.time() - window_s
        with self._lock:
            rows = self._conn.execute(
                "SELECT passed FROM solves WHERE mother_id=? AND created_at>=?", (mother_id, since)
            ).fetchall()
        total = len(rows)
        passed = sum(1 for r in rows if r["passed"])
        return passed, total


def _difficulty_points(difficulty: int) -> int:
    # BASIC 1, ADVANCED 3, LEGENDARY 8 — difficulty-weighted, matching the PRD's
    # "難度加權分" and roughly the target pass rates (80% / 30% / 5%).
    return {0: 1, 1: 3, 2: 8}.get(int(difficulty), 1)
