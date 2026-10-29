"""AxVigil platform API.

Legacy (unversioned) direct grading:
    GET  /health
    GET  /challenges
    POST /submit                      grade a submission directly (no session)

Agent protocol (v1): the server issues challenges, so agents never see the mother.
    GET  /v1/protocol_info
    GET  /v1/auth/challenge            -> message + nonce to sign
    POST /v1/auth/login               -> session token
    POST /v1/start            (auth)  -> a freshly rendered variant (source only)
    GET  /v1/get_fragment     (auth)  -> chunked source delivery
    POST /v1/submit           (auth)  -> grade within the session (+ solveSeconds)
    POST /v1/authorize        (auth)  -> sign one MintAuth for a solved reward session
    GET  /v1/status           (auth)  -> this agent's score summary
    GET  /v1/leaderboard              -> top agents
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from . import auth as authmod
from .config import Settings
from .protocol import Platform, ProtocolError
from .ratelimit import TokenBucket
from .signer import AuthSigner
from .store import Store
from .verify import challenge_meta, grade_submission, list_challenges

settings = Settings.from_env()
app = FastAPI(title="AxVigil platform", version="1.0.0")

store = Store(settings.db_path)
_signer: Optional[AuthSigner] = None
if settings.can_sign:
    _signer = AuthSigner(settings.signer_key, settings.chain_id, settings.verifying_contract)
platform = Platform(settings, store, _signer)
tokens = authmod.SessionTokens(settings.session_secret, ttl_s=settings.auth_ttl_s)

_start_bucket = TokenBucket(settings.start_rate_per_min / 60.0, burst=5)
_submit_bucket = TokenBucket(settings.submit_rate_per_min / 60.0, burst=10)
_login_bucket = TokenBucket(1.0, burst=10)


# --------------------------------------------------------------------------- auth
def require_agent(authorization: str = Header(default="")) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = tokens.verify(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(401, "invalid or expired token")
    return payload


def _rl(bucket: TokenBucket, key: str) -> None:
    if not bucket.allow(key):
        raise HTTPException(429, f"rate limited; retry in ~{bucket.retry_after(key):.1f}s")


def _client_ip(req: Request) -> str:
    return (req.client.host if req.client else "?")


# --------------------------------------------------------------------------- legacy
@app.get("/health")
def health() -> dict:
    return {
        "ok": True, "canSign": _signer is not None,
        "signer": _signer.address if _signer else None,
        "chainId": settings.chain_id, "verifyingContract": settings.verifying_contract,
        "mothers": list(platform.mothers.keys()),
        "challenges": [c["challengeId"] for c in list_challenges(settings)],
    }


@app.get("/challenges")
def challenges() -> list[dict]:
    return list_challenges(settings)


class SubmitRequest(BaseModel):
    challengeId: str
    agentId: int = Field(ge=0)
    to: str
    patch: str
    poc: str
    solveSeconds: Optional[int] = None


@app.post("/submit")
def submit(req: SubmitRequest) -> dict:
    try:
        meta = challenge_meta(settings, req.challengeId)
    except FileNotFoundError:
        raise HTTPException(404, f"unknown challenge: {req.challengeId}")
    # The client does not choose the seed. Grading uses the challenge's own seed.
    seed = int(meta.get("seed", 0))
    try:
        res = grade_submission(settings, challenge_id=req.challengeId, seed=seed,
                               target_file=meta["targetFile"], patch=req.patch, poc=req.poc,
                               solve_seconds=req.solveSeconds)
    except Exception as e:
        raise HTTPException(500, f"grading failed: {e}")
    result = res.to_json()
    # Direct grading does not deal a server-chosen challenge and does not sign.
    # Mint authorizations come only from /v1/authorize on a reward session.
    return {
        "passed": res.passed,
        "result": result,
        "authorizable": False,
        "note": "mint authorizations are issued only for server-assigned reward sessions via /v1/authorize",
    }


# --------------------------------------------------------------------------- v1
@app.get("/v1/protocol_info")
def v1_protocol_info() -> dict:
    return platform.protocol_info()


@app.get("/v1/auth/challenge")
def v1_auth_challenge(address: str, agentId: int, request: Request) -> dict:
    _rl(_login_bucket, _client_ip(request))
    nonce = authmod.new_nonce()
    store.put_nonce(nonce, address)
    msg = authmod.login_message(address, agentId, nonce, settings.chain_id)
    return {"nonce": nonce, "message": msg}


class LoginRequest(BaseModel):
    address: str
    agentId: int
    nonce: str
    signature: str


@app.post("/v1/auth/login")
def v1_auth_login(req: LoginRequest, request: Request) -> dict:
    _rl(_login_bucket, _client_ip(request))
    if not store.consume_nonce(req.nonce, req.address):
        raise HTTPException(401, "invalid or expired nonce")
    msg = authmod.login_message(req.address, req.agentId, req.nonce, settings.chain_id)
    try:
        recovered = authmod.recover_login(msg, req.signature)
    except Exception:
        raise HTTPException(401, "bad signature")
    if recovered.lower() != req.address.lower():
        raise HTTPException(401, "signature does not match address")
    try:
        platform.require_owner(req.agentId, recovered)
    except ProtocolError as e:
        raise HTTPException(e.status, e.detail)
    store.upsert_agent(recovered, req.agentId)
    token = tokens.issue(recovered, req.agentId)
    return {"token": token, "expiresInSeconds": tokens.ttl_s,
            "address": recovered, "agentId": req.agentId}


class StartRequest(BaseModel):
    vulnClass: Optional[int] = None
    difficulty: Optional[int] = None
    motherId: Optional[str] = None
    practice: bool = False


@app.post("/v1/start")
def v1_start(req: StartRequest, agent: dict = Depends(require_agent)) -> dict:
    _rl(_start_bucket, agent["addr"])
    try:
        return platform.start(address=agent["addr"], agent_id=agent["agentId"],
                              vuln_class=req.vulnClass, difficulty=req.difficulty,
                              mother_id=req.motherId, practice=req.practice)
    except ProtocolError as e:
        raise HTTPException(e.status, e.detail)


@app.get("/v1/get_fragment")
def v1_get_fragment(sessionId: str, index: int, agent: dict = Depends(require_agent)) -> dict:
    try:
        return platform.get_fragment(sessionId, index, agent["addr"])
    except ProtocolError as e:
        raise HTTPException(e.status, e.detail)


class PlaySubmit(BaseModel):
    sessionId: str
    patch: str
    poc: str


@app.post("/v1/submit")
def v1_submit(req: PlaySubmit, agent: dict = Depends(require_agent)) -> dict:
    _rl(_submit_bucket, agent["addr"])
    try:
        return platform.submit(session_id=req.sessionId, address=agent["addr"],
                               patch=req.patch, poc=req.poc)
    except ProtocolError as e:
        raise HTTPException(e.status, e.detail)
    except Exception as e:
        raise HTTPException(500, f"grading failed: {e}")


class AuthorizeRequest(BaseModel):
    sessionId: str
    to: Optional[str] = None
    action: Literal["mint"] = "mint"


@app.post("/v1/authorize")
def v1_authorize(req: AuthorizeRequest, agent: dict = Depends(require_agent)) -> dict:
    try:
        return platform.authorize(session_id=req.sessionId, address=agent["addr"],
                                  to=req.to, action=req.action)
    except ProtocolError as e:
        raise HTTPException(e.status, e.detail)


@app.get("/v1/status")
def v1_status(agent: dict = Depends(require_agent)) -> dict:
    return platform.status(agent["agentId"])


@app.get("/v1/leaderboard")
def v1_leaderboard(limit: int = 20) -> list[dict]:
    return platform.leaderboard(limit)
