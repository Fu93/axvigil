"""AxVigil backend: grade a submission, and on success sign the on-chain authorization.

    GET  /health
    GET  /challenges
    POST /submit        -> grade; if passed and configured to sign, return a signed
                           MintAuth (default) or SkillAuth carrying the verifier's
                           own submissionHash.

The backend signs ONLY what the verifier passed, and the signed submissionHash is
exactly the one the verifier computed — the chain then enforces one action per solve.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .signer import AuthSigner
from .verify import challenge_meta, grade_submission, list_challenges

settings = Settings.from_env()
app = FastAPI(title="AxVigil backend", version="0.1.0")

_signer: Optional[AuthSigner] = None
if settings.can_sign:
    _signer = AuthSigner(settings.signer_key, settings.chain_id, settings.verifying_contract)


class SubmitRequest(BaseModel):
    challengeId: str
    agentId: int = Field(ge=0)
    to: str = Field(description="recipient of the collectible (mint) / unused for skill")
    patch: str
    poc: str
    pool: int = Field(default=0, ge=0, le=1)
    seed: int = 0
    action: Literal["mint", "skill"] = "mint"
    solveSeconds: Optional[int] = None


class SubmitResponse(BaseModel):
    passed: bool
    result: dict
    action: Optional[str] = None
    auth: Optional[dict] = None
    signature: Optional[str] = None
    signer: Optional[str] = None
    note: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "canSign": _signer is not None,
        "signer": _signer.address if _signer else None,
        "chainId": settings.chain_id,
        "verifyingContract": settings.verifying_contract,
        "challenges": [c["challengeId"] for c in list_challenges(settings)],
    }


@app.get("/challenges")
def challenges() -> list[dict]:
    return list_challenges(settings)


@app.post("/submit", response_model=SubmitResponse)
def submit(req: SubmitRequest) -> SubmitResponse:
    try:
        meta = challenge_meta(settings, req.challengeId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown challenge: {req.challengeId}")

    try:
        res = grade_submission(
            settings, challenge_id=req.challengeId, seed=req.seed,
            target_file=meta["targetFile"], patch=req.patch, poc=req.poc,
            solve_seconds=req.solveSeconds,
        )
    except Exception as e:  # grading infra failure (e.g. forge missing)
        raise HTTPException(status_code=500, detail=f"grading failed: {e}")

    result = res.to_json()
    if not res.passed:
        return SubmitResponse(passed=False, result=result, note="submission did not pass grading")

    if _signer is None:
        return SubmitResponse(
            passed=True, result=result,
            note="passed, but signing is not configured (set SIGNER_KEY + VERIFYING_CONTRACT)",
        )

    if req.action == "mint":
        signed = _signer.sign_mint(
            agent_id=req.agentId, to=req.to, vuln_class=res.vulnClass,
            difficulty=res.difficulty, pool=req.pool,
            submission_hash=res.submissionHash, ttl_s=settings.auth_ttl_s,
        )
    else:
        signed = _signer.sign_skill(
            agent_id=req.agentId, vuln_class=res.vulnClass, difficulty=res.difficulty,
            submission_hash=res.submissionHash, ttl_s=settings.auth_ttl_s,
        )

    return SubmitResponse(
        passed=True, result=result, action=signed.kind,
        auth=signed.auth, signature=signed.signature, signer=signed.signer,
    )
