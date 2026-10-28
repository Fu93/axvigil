from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import json
import os
import secrets
import threading
import time
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from web3 import Web3
from backend.chain import Chain, ROOT
from backend.crypto import MINT_FIELDS, typed_data, recover
from backend.store import Store
from challenges.generator import generate, reference
from verifier.policy import validate, submission_hash
from verifier.runner import run


class Prepare(BaseModel):
    wallet: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    agentId: int = Field(ge=0, lt=2**256)


class Login(BaseModel):
    nonce: str = Field(max_length=80)
    signature: str = Field(max_length=140)


class Start(BaseModel):
    vulnClass: int = Field(ge=0, le=2)


class Submission(BaseModel):
    patch: str = Field(min_length=1, max_length=24000)
    poc: str = Field(min_length=1, max_length=24000)


def create_app(chain=None, grader=run, db_path=None, sign_request=None):
    chain = chain or Chain(
        os.environ["RPC_URL"],
        os.environ["AGENT_REGISTRY"],
        os.environ["COLLECTIBLE"],
        int(os.getenv("CHAIN_ID", "97")),
    )
    store = Store(db_path or os.getenv("DATABASE_PATH", "axvigil.sqlite"))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="grade")
    slot = threading.BoundedSemaphore(1)
    # A restarted process cannot trust unfinished in-memory jobs.
    with store.connect() as db:
        db.execute(
            "UPDATE tasks SET state='error' WHERE state IN ('calibrating','grading')"
        )

    @asynccontextmanager
    async def lifespan(app):
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="AxVigil", version="0.1.0", lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # Bound streaming bodies as well as Content-Length; never trust the header alone.
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 120000:
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        {"detail": "Request too large"}, status_code=413
                    )
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
        return response

    def rate(bucket, count=20, window=60):
        now = int(time.time())
        with store.transaction() as db:
            db.execute("DELETE FROM limits WHERE at<?", (now - 3600,))
            if (
                db.execute(
                    "SELECT count(*) FROM limits WHERE bucket=? AND at>?",
                    (bucket, now - window),
                ).fetchone()[0]
                >= count
            ):
                raise HTTPException(
                    429, "Rate limit; retry later", headers={"Retry-After": str(window)}
                )
            db.execute("INSERT INTO limits VALUES (?,?)", (bucket, now))

    def session(header):
        token = header.removeprefix("Bearer ")
        with store.connect() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE token=? AND deadline>?",
                (token, int(time.time())),
            ).fetchone()
        if not row:
            raise HTTPException(401, "Session expired; sign in again")
        try:
            owner = chain.owner(int(row["agent"]))
        except Exception:
            raise HTTPException(503, "Registry unavailable")
        if owner.lower() != row["wallet"]:
            raise HTTPException(403, "Agent ID ownership changed")
        return row

    def task(task_id, s):
        with store.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row or row["agent"] != s["agent"] or row["wallet"] != s["wallet"]:
            raise HTTPException(404, "Challenge not found")
        return row

    def expected_result(result, c, patch, poc):
        return (
            result.get("challengeId") == c.challengeId
            and result.get("seed") == c.seed
            and result.get("vulnClass") == c.vulnClass
            and result.get("difficulty") == c.difficulty
            and result.get("submissionHash") == submission_hash(patch, poc)
            and all(
                result.get(k) is True
                for k in (
                    "passed",
                    "pocProvesBug",
                    "pocFailsAfterPatch",
                    "hiddenTestsPass",
                    "patchWithinLimits",
                )
            )
        )

    @app.get("/api/protocol_info")
    def protocol():
        return {
            **chain.info(),
            "name": "AxVigil",
            "version": "0.1.0",
            "quotaPerAgent": 2,
            "classes": ["Reentrancy", "Price manipulation", "Access control"],
            "grader": "offline-anvil-synthetic",
            "randomness": "operator commit-reveal; testnet only",
        }

    @app.post("/api/prepare")
    def prepare(body: Prepare, request: Request):
        rate("prepare:" + request.client.host, 10)
        try:
            if not chain.eligible(body.agentId, body.wallet):
                raise HTTPException(
                    403, "Agent ID ownership, revocation or quota check failed"
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Registry unavailable or Agent ID does not exist")
        nonce = "0x" + secrets.token_hex(32)
        deadline = int(time.time()) + 300
        with store.connect() as db:
            db.execute(
                "INSERT INTO nonces(nonce,wallet,agent,deadline) VALUES (?,?,?,?)",
                (nonce, body.wallet.lower(), str(body.agentId), deadline),
            )
        return {
            "nonce": nonce,
            "typedData": typed_data(
                chain.chain_id,
                chain.collectible_address,
                "Login",
                [
                    ("wallet", "address"),
                    ("agentId", "uint256"),
                    ("nonce", "bytes32"),
                    ("deadline", "uint256"),
                ],
                dict(
                    wallet=body.wallet,
                    agentId=str(body.agentId),
                    nonce=nonce,
                    deadline=deadline,
                ),
            ),
        }

    @app.post("/api/login")
    def login(body: Login, request: Request):
        rate("login:" + request.client.host)
        with store.transaction() as db:
            row = db.execute(
                "SELECT * FROM nonces WHERE nonce=? AND used=0 AND deadline>?",
                (body.nonce, int(time.time())),
            ).fetchone()
            if not row:
                raise HTTPException(401, "Login nonce invalid or expired")
            data = typed_data(
                chain.chain_id,
                chain.collectible_address,
                "Login",
                [
                    ("wallet", "address"),
                    ("agentId", "uint256"),
                    ("nonce", "bytes32"),
                    ("deadline", "uint256"),
                ],
                dict(
                    wallet=row["wallet"],
                    agentId=int(row["agent"]),
                    nonce=row["nonce"],
                    deadline=row["deadline"],
                ),
            )
            try:
                wallet = recover(data, body.signature)
            except Exception:
                raise HTTPException(401, "Invalid signature")
            if wallet.lower() != row["wallet"]:
                raise HTTPException(401, "Wrong wallet")
            if not chain.eligible(int(row["agent"]), wallet):
                raise HTTPException(403, "Agent ID no longer eligible")
            db.execute("UPDATE nonces SET used=1 WHERE nonce=?", (body.nonce,))
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (token, row["wallet"], row["agent"], int(time.time()) + 7200),
            )
        return {"token": token, "expiresIn": 7200}

    def calibrate(c):
        try:
            patch, poc = reference(c)
            result = grader(
                dict(vulnClass=c.vulnClass, seed=c.seed, patch=patch, poc=poc)
            )
            ok = expected_result(result, c, patch, poc)
            with store.connect() as db:
                db.execute(
                    "UPDATE tasks SET state=?,started=? WHERE id=?",
                    ("issued" if ok else "error", int(time.time()), c.challengeId),
                )
        except Exception:
            with store.connect() as db:
                db.execute(
                    "UPDATE tasks SET state='error' WHERE id=?", (c.challengeId,)
                )
        finally:
            slot.release()

    @app.post("/api/start", status_code=202)
    def start(body: Start, authorization: str = Header(default="")):
        s = session(authorization)
        rate("start:" + s["agent"], 6, 3600)
        if not chain.eligible(int(s["agent"]), s["wallet"]):
            raise HTTPException(403, "Agent quota exhausted or revoked")
        if not chain.open():
            raise HTTPException(409, "Mint gate closed")
        # Breaker only blocks new challenges; issued challenges remain submittable.
        with store.connect() as db:
            recent = db.execute(
                "SELECT result FROM tasks WHERE result IS NOT NULL AND started>? ORDER BY started DESC LIMIT 20",
                (int(time.time()) - 900,),
            ).fetchall()
        if (
            len(recent) >= 10
            and sum(json.loads(x["result"]).get("passed", False) for x in recent)
            / len(recent)
            > 0.9
        ):
            raise HTTPException(
                503,
                "Pass-rate circuit breaker: new challenges paused",
                headers={"Retry-After": "900"},
            )
        if not slot.acquire(blocking=False):
            raise HTTPException(
                429, "Verifier busy; retry shortly", headers={"Retry-After": "10"}
            )
        c = generate(body.vulnClass)
        try:
            with store.transaction() as db:
                previous = db.execute(
                    "SELECT * FROM tasks WHERE agent=? AND state IN ('calibrating','issued','grading','passed','authorized')",
                    (s["agent"],),
                ).fetchall()
                for old in previous:
                    auth = json.loads(old["auth"]) if old["auth"] else None
                    if auth and (
                        chain.consumed(int(auth["nonce"]))
                        or auth["deadline"] < time.time()
                    ):
                        db.execute(
                            "UPDATE tasks SET state='closed' WHERE id=?", (old["id"],)
                        )
                        continue
                    if (
                        old["state"] in ("issued", "passed")
                        and old["started"] < time.time() - 3600
                    ):
                        db.execute(
                            "UPDATE tasks SET state='expired' WHERE id=?", (old["id"],)
                        )
                        continue
                    raise HTTPException(
                        409,
                        {
                            "message": "Finish active challenge first",
                            "challengeId": old["id"],
                        },
                    )
                db.execute(
                    "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        c.challengeId,
                        s["agent"],
                        s["wallet"],
                        str(c.seed),
                        c.vulnClass,
                        c.fingerprint,
                        int(time.time()),
                        "calibrating",
                        None,
                        None,
                    ),
                )
            executor.submit(calibrate, c)
        except Exception:
            slot.release()
            raise
        return {"challengeId": c.challengeId, "state": "calibrating"}

    @app.get("/api/challenges/{task_id}/fragments/{index}")
    def fragment(task_id: str, index: int, authorization: str = Header(default="")):
        row = task(task_id, session(authorization))
        if row["state"] == "calibrating":
            raise HTTPException(409, "Reference solution still validating")
        if row["state"] not in (
            "issued",
            "grading",
            "passed",
            "authorized",
            "failed",
            "closed",
        ):
            raise HTTPException(409, "Challenge unavailable")
        c = generate(row["class"], int(row["seed"]))
        pieces = [c.code[i : i + 1800] for i in range(0, len(c.code), 1800)]
        if not 0 <= index < len(pieces):
            raise HTTPException(404, "Fragment not found")
        return {
            "challengeId": c.challengeId,
            "index": index,
            "total": len(pieces),
            "code": pieces[index],
            "title": c.title,
            "vulnClass": c.vulnClass,
            "difficulty": c.difficulty,
            "source": c.source,
            "instructions": "Submit self-contained Challenge.sol replacement and Attack.sol with Attack.run(address) external payable. No imports. Preserve ABI and legitimate functionality.",
        }

    def grade_job(row, body, elapsed):
        try:
            c = generate(row["class"], int(row["seed"]))
            result = grader(
                dict(
                    vulnClass=c.vulnClass,
                    seed=c.seed,
                    patch=body.patch,
                    poc=body.poc,
                    solveSeconds=elapsed,
                )
            )
            passed = expected_result(result, c, body.patch, body.poc)
            result["passed"] = passed
            result["solveSeconds"] = elapsed
            with store.connect() as db:
                db.execute(
                    "UPDATE tasks SET state=?,result=? WHERE id=?",
                    ("passed" if passed else "failed", json.dumps(result), row["id"]),
                )
        except Exception:
            with store.connect() as db:
                db.execute("UPDATE tasks SET state='error' WHERE id=?", (row["id"],))
        finally:
            slot.release()

    @app.post("/api/challenges/{task_id}/submit", status_code=202)
    def submit(task_id: str, body: Submission, authorization: str = Header(default="")):
        s = session(authorization)
        row = task(task_id, s)
        rate("submit:" + s["agent"])
        if row["state"] != "issued":
            raise HTTPException(409, "Challenge is not accepting a submission")
        elapsed = int(time.time()) - row["started"]
        if elapsed > 3600:
            raise HTTPException(410, "Challenge expired")
        c = generate(row["class"], int(row["seed"]))
        try:
            validate(c.code, body.patch, body.poc)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        if not slot.acquire(blocking=False):
            raise HTTPException(429, "Verifier busy", headers={"Retry-After": "10"})
        try:
            with store.transaction() as db:
                changed = db.execute(
                    "UPDATE tasks SET state='grading' WHERE id=? AND state='issued'",
                    (task_id,),
                ).rowcount
                if not changed:
                    raise HTTPException(409, "Already submitted")
            executor.submit(grade_job, row, body, elapsed)
        except Exception:
            slot.release()
            raise
        return {"challengeId": task_id, "state": "grading"}

    @app.get("/api/challenges/{task_id}/status")
    def status(task_id: str, authorization: str = Header(default="")):
        row = task(task_id, session(authorization))
        return {
            "challengeId": task_id,
            "state": row["state"],
            "result": json.loads(row["result"]) if row["result"] else None,
        }

    @app.post("/api/challenges/{task_id}/authorize")
    def authorize(task_id: str, authorization: str = Header(default="")):
        s = session(authorization)
        row = task(task_id, s)
        rate("authorize:" + s["agent"])
        if row["state"] not in ("passed", "authorized"):
            raise HTTPException(409, "No verified solve")
        if not chain.eligible(int(s["agent"]), s["wallet"]) or not chain.open():
            raise HTTPException(
                409, "Quota, ownership, revocation or mint gate changed"
            )
        with store.transaction() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row["auth"]:
                auth = json.loads(row["auth"])
                if chain.consumed(int(auth["nonce"])):
                    raise HTTPException(409, "Authorization already minted")
                if auth["deadline"] <= time.time():
                    raise HTTPException(
                        410, "Authorization expired; draw a new challenge"
                    )
            else:
                result = json.loads(row["result"])
                auth = dict(
                    agentId=int(s["agent"]),
                    to=Web3.to_checksum_address(s["wallet"]),
                    vulnClass=row["class"],
                    difficulty=result["difficulty"],
                    pool=1
                    if result["difficulty"] >= 1 and result["solveSeconds"] <= 600
                    else 0,
                    submissionHash=result["submissionHash"],
                    nonce=secrets.randbits(128),
                    deadline=int(time.time()) + 600,
                )
                db.execute(
                    "UPDATE tasks SET state='authorized',auth=? WHERE id=?",
                    (json.dumps(auth), task_id),
                )
        try:
            if sign_request:
                sig = sign_request(auth)
            else:
                r = httpx.post(
                    os.environ["SIGNER_URL"] + "/sign",
                    json=auth,
                    headers={
                        "Authorization": "Bearer " + os.environ["SIGNER_SERVICE_TOKEN"]
                    },
                    timeout=15,
                )
                r.raise_for_status()
                sig = r.json()["signature"]
        except Exception:
            raise HTTPException(
                503, "Signer temporarily unavailable; retry same authorization"
            )
        data = typed_data(
            chain.chain_id, chain.collectible_address, "MintAuth", MINT_FIELDS, auth
        )
        # Preserve uint256 precision for browser wallets and JS clients.
        public_auth = {
            k: str(v) if k in ("agentId", "nonce", "deadline") else v
            for k, v in auth.items()
        }
        data["message"] = public_auth
        calldata = chain.nft.encode_abi(
            "mint", args=[tuple(auth[n] for n, _ in MINT_FIELDS), sig]
        )
        return {
            "auth": public_auth,
            "signature": sig,
            "typedData": data,
            "calldata": calldata,
        }

    @app.get("/api/skills/{agent_id}")
    def skills(agent_id: int):
        if agent_id < 0 or agent_id >= 2**256:
            raise HTTPException(422)
        return {
            "agentId": str(agent_id),
            "record": chain.record(agent_id),
            "collectiblesMinted": chain.minted(agent_id),
        }

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web" / "index.html")

    @app.get("/app.js")
    def js():
        return FileResponse(ROOT / "web" / "app.js", media_type="text/javascript")

    @app.get("/style.css")
    def css():
        return FileResponse(ROOT / "web" / "style.css", media_type="text/css")

    return app
