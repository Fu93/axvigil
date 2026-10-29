"""The platform core: issue challenges, grade within a session, authorize rewards.

Challenges are issued server-side — the server picks a mother and a secret seed,
renders a fresh variant, and returns ONLY the vulnerable source. The agent never
sees the mother, the seed, the hidden tests or the reference solution, so there is
nothing to memorize. Grading on submit re-uses the exact rendered variant.
"""

from __future__ import annotations

import logging
import re
import secrets
import shutil
import sys
import time
import uuid
from pathlib import Path

from .circuit import CircuitBreaker
from .config import Settings
from .quota import MAX_REWARD_ATTEMPTS, pool_for_difficulty

logger = logging.getLogger("axvigil")
_TEST_MAP = re.compile(r"\s*\{[^{}]*\}")
from .registry import AgentRegistry, RegistryUnavailable, rpc_registry_from_env
from .signer import AuthSigner
from .store import (
    AlreadyAuthorized,
    DuplicateSubmission,
    NotRewardSession,
    QuotaExceeded,
    Store,
)


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
    def __init__(
        self, settings: Settings, store: Store, signer: AuthSigner | None,
        registry: AgentRegistry | None = None,
    ):
        self.s = settings
        self.store = store
        self.signer = signer
        self.dev_skip_ownership = bool(settings.dev_skip_ownership)
        # An injected registry (the test double) wins. Otherwise use chain RPC
        # when AGENT_REGISTRY and RPC_URL are set.
        self.registry = registry if registry is not None else rpc_registry_from_env(
            settings.agent_registry, settings.rpc_url,
        )
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
            "maxRewardAttempts": MAX_REWARD_ATTEMPTS,
            "maxMintsPerAgent": MAX_REWARD_ATTEMPTS,
            "ownershipCheck": self.ownership_mode(),
            "pools": {
                "0": "BASIC (uniform)",
                "1": "ADVANCED (better odds)",
                "2": "LEGENDARY (best odds)",
            },
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

    def ownership_mode(self) -> str:
        if self.dev_skip_ownership:
            return "dev-skip"
        if self.registry is None:
            return "unconfigured"
        return "enforced"

    def require_owner(self, agent_id: int, address: str) -> None:
        """The wallet must currently own `agentId` in the Agent ID registry.

        Skipped only when AXVIGIL_DEV_SKIP_OWNERSHIP is set (local dev). A missing
        registry in any other mode is a configuration error, not a free pass.
        """
        if self.dev_skip_ownership:
            return
        if self.registry is None:
            raise ProtocolError(
                503,
                "Agent ID ownership check is not configured. Set AGENT_REGISTRY and RPC_URL. "
                "AXVIGIL_DEV_SKIP_OWNERSHIP=1 disables the check for local dev only.",
            )
        try:
            owner = self.registry.owner_of(int(agent_id))
        except RegistryUnavailable as exc:
            raise ProtocolError(503, f"Agent ID registry unavailable: {exc}") from exc
        if owner is None or owner.lower() != address.lower():
            raise ProtocolError(
                403,
                "The authenticated wallet does not own this Agent ID. " + self.quota_message(agent_id),
            )

    def start(self, *, address: str, agent_id: int, vuln_class: int | None = None,
              difficulty: int | None = None, mother_id: str | None = None,
              practice: bool = False) -> dict:
        # Before a reward attempt is spent, and again for practice so a stranger
        # cannot open a session in someone else's name.
        self.require_owner(agent_id, address)
        reward = not practice
        if reward:
            # The caller does not pick the challenge. Any of basic / advanced / legendary
            # can come up: each available mother is equally likely.
            if vuln_class is not None or difficulty is not None or mother_id is not None:
                raise ProtocolError(
                    400,
                    "Reward challenges are chosen by the server across all difficulties. "
                    "Omit motherId, vulnClass, and difficulty. "
                    "Pass practice=true to choose a mother. "
                    + self.quota_message(agent_id),
                )
            candidates = [m for m in self.mothers.values() if not self.breaker.is_open(m.mother_id)]
        else:
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
            raise ProtocolError(
                409,
                "No challenge is available. It was filtered out, or the answer-leak circuit breaker "
                "paused issuance because the recent pass rate was too high. "
                + self.quota_message(agent_id),
            )

        mother = secrets.choice(candidates)
        seed = secrets.randbelow(1 << 31)
        out, meta = self._render(mother, seed)
        source = (out / "src" / meta["targetFile"]).read_text()

        now = time.time()
        session_id = uuid.uuid4().hex
        try:
            self.store.create_session({
                "session_id": session_id, "address": address, "agent_id": agent_id,
                "mother_id": mother.mother_id, "seed": seed, "challenge_id": meta["challengeId"],
                "vuln_class": meta["vulnClass"], "difficulty": meta["difficulty"],
                "started_at": now, "expires_at": now + self.s.session_ttl_s,
                "reward": reward,
            })
        except QuotaExceeded as e:
            raise ProtocolError(
                409,
                "Reward attempt cap reached: 2 of 2 lifetime reward sessions have been opened "
                "for this Agent ID. Opening a session spends the attempt, including if it expires "
                "or fails. Practice mode is still available and cannot be minted. "
                + self.quota_message(agent_id),
            ) from e
        return {
            "sessionId": session_id,
            "reward": reward,
            "practice": not reward,
            "challengeId": public_challenge_id(session_id),
            "vulnClass": meta["vulnClass"],
            "difficulty": meta["difficulty"],
            "pool": pool_for_difficulty(meta["difficulty"]) if reward else None,
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
            "quotaMessage": self.quota_message(agent_id),
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
        if not patch.strip() or not poc.strip():
            raise ProtocolError(
                400,
                "Both patch and poc must be non-empty Solidity source. No grade was started.",
            )
        # One grader run per session. The open -> grading transition is atomic,
        # so a second submit cannot start another forge run while the first grades.
        code, sess = self.store.claim_for_grading(session_id, address, time.time())
        if code == "missing" or sess is None:
            raise ProtocolError(404, "Unknown session. Check the sessionId from POST /v1/start.")
        if code == "forbidden":
            raise ProtocolError(
                403,
                "This session belongs to a different wallet. Log in with the wallet that started it.",
            )
        if code == "expired":
            spent = (
                "The reward attempt was counted when the session opened and is not refunded. "
                if sess.get("reward") else
                "Practice sessions do not spend a reward attempt. "
            )
            raise ProtocolError(
                408,
                "This session expired. " + spent + self.quota_message(sess["agent_id"]),
            )
        if code != "ok":
            status_name = sess.get("status") or "closed"
            if status_name == "solved":
                why = "This session was already submitted and solved. Each session is graded once. "
            elif status_name == "failed":
                why = "This session was already submitted and did not pass. Each session is graded once. "
            elif status_name == "grading":
                why = "This session is already being graded. Wait for that result. "
            else:
                why = f"This session is {status_name} and cannot be submitted again. "
            raise ProtocolError(409, why + self.quota_message(sess["agent_id"]))

        from axvigil_verifier.grader import grade
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
        except Exception:
            logger.exception("grading failed")
            # The attempt was already claimed. Close it so it cannot be graded again.
            self.store.finish_grading(
                session_id, passed=False,
                solve_seconds=int(time.time() - sess["started_at"]), submission_hash="",
            )
            raise ProtocolError(
                500,
                "Grading failed before a result was produced. "
                + self.quota_message(sess["agent_id"]),
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        from axvigil_verifier.forge_runner import environment_failure
        if environment_failure(getattr(res, "log", "") or ""):
            # Not a grade of the patch. Release the claim so the same session can be
            # submitted again. The reward attempt was already counted when it opened.
            self.store.release_grading(session_id)
            raise ProtocolError(
                503,
                feedback_summary(res.to_json()) + " " + self.quota_message(sess["agent_id"]),
            )

        solve_seconds = int(time.time() - sess["started_at"])
        if not self.store.finish_grading(
            session_id, passed=res.passed, solve_seconds=solve_seconds,
            submission_hash=res.submissionHash,
        ):
            raise ProtocolError(409, "session already graded")
        # Practice passes must not move the leaderboard or the leak breaker.
        if sess["reward"]:
            self.store.record_solve({
                "session_id": session_id, "address": address, "agent_id": sess["agent_id"],
                "mother_id": sess["mother_id"], "challenge_id": sess["challenge_id"],
                "vuln_class": sess["vuln_class"], "difficulty": sess["difficulty"],
                "passed": 1 if res.passed else 0, "solve_seconds": solve_seconds,
                "submission_hash": res.submissionHash,
            })
        result = redact_public_grade(res.to_json(), public_challenge_id(session_id))
        result["solveSeconds"] = solve_seconds
        return {
            "passed": res.passed,
            "result": result,
            "summary": feedback_summary(result),
            "authorizable": bool(res.passed and sess["reward"] and self.signer is not None),
            "quotaMessage": self.quota_message(sess["agent_id"]),
        }

    # ---- reward ----
    def authorize(self, *, session_id: str, address: str, to: str | None, action: str) -> dict:
        sess = self._owned_session(session_id, address)
        self.require_owner(sess["agent_id"], address)
        if action != "mint":
            raise ProtocolError(
                400,
                "only mint authorizations are issued; each passed solve pairs with one collectible",
            )
        if not sess["reward"]:
            raise ProtocolError(
                403,
                "Practice sessions are not reward-bearing and cannot be minted. "
                + self.quota_message(sess["agent_id"]),
            )
        if sess["status"] != "solved":
            raise ProtocolError(
                409,
                f"This session is not solved (status: {sess['status']}), so there is nothing to authorize. "
                + self.quota_message(sess["agent_id"]),
            )
        if sess["authorized"]:
            raise ProtocolError(
                409,
                "This solve was already authorized. Each solved challenge can be minted once. "
                + self.quota_message(sess["agent_id"]),
            )
        if self.signer is None:
            raise ProtocolError(503, "signing not configured")

        sub = sess["submission_hash"]
        pool = pool_for_difficulty(sess["difficulty"])
        signed = self.signer.sign_mint(
            agent_id=sess["agent_id"], to=to or address, vuln_class=sess["vuln_class"],
            difficulty=sess["difficulty"], pool=pool,
            submission_hash=sub, ttl_s=self.s.auth_ttl_s,
        )
        try:
            self.store.commit_mint_authorization(
                session_id=session_id, agent_id=sess["agent_id"], submission_hash=sub,
                difficulty=sess["difficulty"], pool=pool, signature=signed.signature,
            )
        except QuotaExceeded as e:
            raise ProtocolError(
                409,
                "Mint cap reached: 2 of 2 lifetime mints used for this Agent ID. "
                + self.quota_message(sess["agent_id"]),
            ) from e
        except AlreadyAuthorized as e:
            raise ProtocolError(
                409,
                "This solve was already authorized. Each solved challenge can be minted once. "
                + self.quota_message(sess["agent_id"]),
            ) from e
        except DuplicateSubmission as e:
            raise ProtocolError(
                409,
                "This solution was already minted. Each solved challenge can be minted once. "
                + self.quota_message(sess["agent_id"]),
            ) from e
        except NotRewardSession as e:
            raise ProtocolError(
                403,
                "Practice sessions are not reward-bearing and cannot be minted. "
                + self.quota_message(sess["agent_id"]),
            ) from e
        return {
            "action": signed.kind, "auth": signed.auth, "signature": signed.signature,
            "signer": signed.signer, "quotaMessage": self.quota_message(sess["agent_id"]),
        }

    # ---- status ----
    def status(self, agent_id: int) -> dict:
        summary = self.store.agent_summary(agent_id)
        summary["rewardAttempts"] = self.store.reward_attempt_count(agent_id)
        summary["rewardAttemptCap"] = MAX_REWARD_ATTEMPTS
        summary["mintAuthorizations"] = self.store.mint_authorization_count(agent_id)
        summary["mintCap"] = MAX_REWARD_ATTEMPTS
        summary["attemptsRemaining"] = max(0, MAX_REWARD_ATTEMPTS - summary["rewardAttempts"])
        summary["mintsRemaining"] = max(0, MAX_REWARD_ATTEMPTS - summary["mintAuthorizations"])
        summary["quotaMessage"] = self.quota_message(agent_id)
        return summary

    def leaderboard(self, limit: int = 20) -> list[dict]:
        return self.store.leaderboard(limit)

    # ---- helpers ----
    def quota_message(self, agent_id: int) -> str:
        used = self.store.reward_attempt_count(agent_id)
        mints = self.store.mint_authorization_count(agent_id)
        attempts_left = max(0, MAX_REWARD_ATTEMPTS - used)
        mints_left = max(0, MAX_REWARD_ATTEMPTS - mints)
        return (
            f"Reward attempts remaining: {attempts_left} of {MAX_REWARD_ATTEMPTS}. "
            f"Mints remaining: {mints_left} of {MAX_REWARD_ATTEMPTS}. "
            "A reward attempt is spent when the session opens."
        )

    def _owned_session(self, session_id: str, address: str) -> dict:
        sess = self.store.get_session(session_id)
        if not sess:
            raise ProtocolError(404, "unknown session")
        if sess["address"].lower() != address.lower():
            raise ProtocolError(403, "session belongs to another agent")
        return sess


def public_challenge_id(session_id: str) -> str:
    """Opaque id. The stored challenge id is `{mother}-{seed}` and must not be shown."""
    return "ch_" + session_id[:12]


def redact_public_grade(result: dict, public_id: str) -> dict:
    """Drop the seed and any `{testName: bool}` map from a grade payload."""
    out = {key: value for key, value in result.items() if key != "seed"}
    out["challengeId"] = public_id
    log = out.get("log")
    if isinstance(log, str):
        out["log"] = _TEST_MAP.sub("", log).strip()
    return out


def feedback_summary(result: dict) -> str:
    log = result.get("log") or ""
    lowered = log.lower()
    if "solidity compiler is not available" in lowered:
        return (
            "Grading did not run because the Solidity compiler is not available yet. "
            "From the repo run `cd contracts && forge build` once while online, then submit again."
        )
    if "forge was not found" in lowered:
        return "Grading did not run because forge is not on PATH. Install Foundry, then submit again."
    if result.get("passed"):
        return "All four checks passed."
    reasons = []
    if result.get("pocProvesBug") is False:
        reasons.append("the PoC did not pass on the original contract, so it does not prove the bug")
    if result.get("pocFailsAfterPatch") is False:
        reasons.append("the PoC still passed after the patch, so the bug still works")
    if result.get("hiddenTestsPass") is False:
        reasons.append("the patch broke required behavior")
    if result.get("patchWithinLimits") is False:
        reasons.append("the patch is outside the size limit or drops the contract name or a public function")
    if not reasons:
        return "Not solved."
    return "Not solved: " + "; ".join(reasons) + "."


def _fragment_count(source: str, size: int = 800) -> int:
    return max(1, (len(source) + size - 1) // size)


def _fragments(source: str, size: int = 800) -> list[str]:
    return [source[i:i + size] for i in range(0, len(source), size)] or [""]
