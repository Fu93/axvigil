"""Run separately from the API and offline grader; never expose this port publicly."""

import hmac
import os
import time
from fastapi import FastAPI, Header, HTTPException
from eth_account import Account
from backend.chain import Chain
from backend.crypto import MINT_FIELDS, typed_data, sign


def create_signer(chain=None, key=None, secret=None):
    key = key or os.environ["MINT_SIGNER_KEY"]
    secret = secret or os.environ["SIGNER_SERVICE_TOKEN"]
    if len(secret) < 32:
        raise ValueError("Signer service token must have at least 32 characters")
    chain = chain or Chain(
        os.environ["RPC_URL"],
        os.environ["AGENT_REGISTRY"],
        os.environ["COLLECTIBLE"],
        int(os.getenv("CHAIN_ID", "97")),
    )
    signer = Account.from_key(key)
    if chain.nft.functions.signer().call().lower() != signer.address.lower():
        raise ValueError("Configured signer does not match contract")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.post("/sign")
    def issue(auth: dict, authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, "Bearer " + secret):
            raise HTTPException(401)
        try:
            now = int(time.time())
            if set(auth) != {n for n, _ in MINT_FIELDS}:
                raise ValueError()
            if not now < auth["deadline"] <= now + 660:
                raise ValueError()
            if (
                auth["vulnClass"] not in range(3)
                or auth["difficulty"] not in range(3)
                or auth["pool"] not in range(2)
            ):
                raise ValueError()
            if not chain.eligible(int(auth["agentId"]), auth["to"]) or not chain.open():
                raise ValueError()
            if chain.consumed(int(auth["nonce"])):
                raise ValueError()
            data = typed_data(
                chain.chain_id, chain.collectible_address, "MintAuth", MINT_FIELDS, auth
            )
            return {"signature": sign(data, key)}
        except Exception:
            raise HTTPException(409, "Authorization not eligible")

    return app
