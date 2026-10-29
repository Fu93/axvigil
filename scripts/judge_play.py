#!/usr/bin/env python3
"""Drive one reward solve against a local AxVigil API and write the mint auth.

The reference patch is read from the server's challenge cache. That stands in
for the model: a real agent only receives the vulnerable source. Login uses the
local MockAgentID (AGENT_REGISTRY + RPC_URL); ownership is not skipped.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct


def _request(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "axvigil-judge-demo/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"detail": payload}
        return exc.code, parsed


def main() -> int:
    base = os.environ["AXVIGIL_API"].rstrip("/")
    db_path = os.environ["DB_PATH"]
    cache = Path(os.environ["CHALLENGE_CACHE_DIR"])
    out_path = Path(os.environ["MINT_AUTH_OUT"])
    account = Account.from_key(os.environ["PLAYER_KEY"])
    agent_id = int(os.environ["AGENT_ID"])

    status, info = _request("GET", f"{base}/v1/protocol_info")
    if status != 200:
        print(f"protocol_info failed: {status} {info}", file=sys.stderr)
        return 1
    print(
        f"protocol: {info['name']} chain {info['chainId']} "
        f"ownership={info.get('ownershipCheck')} mothers={len(info['mothers'])}"
    )
    if info.get("ownershipCheck") != "enforced":
        print("ownership check is not enforced; set AGENT_REGISTRY and RPC_URL", file=sys.stderr)
        return 1

    status, challenge = _request(
        "GET", f"{base}/v1/auth/challenge?address={account.address}&agentId={agent_id}",
    )
    if status != 200:
        print(f"login challenge failed: {status} {challenge}", file=sys.stderr)
        return 1
    signature = account.sign_message(encode_defunct(text=challenge["message"])).signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature
    status, logged = _request("POST", f"{base}/v1/auth/login", {
        "address": account.address, "agentId": agent_id,
        "nonce": challenge["nonce"], "signature": signature,
    })
    if status != 200:
        print(f"login failed: {status} {logged}", file=sys.stderr)
        return 1
    token = logged["token"]
    print(f"logged in as {logged['address']} agent {logged['agentId']}")

    status, rejected = _request(
        "POST", f"{base}/v1/start", {"motherId": "reentrancy"}, token,
    )
    print(f"reward + motherId -> {status}: {rejected.get('detail')}")
    if status != 400:
        print("expected 400 when a reward start names a mother", file=sys.stderr)
        return 1

    status, practice = _request(
        "POST", f"{base}/v1/start", {"practice": True, "motherId": "reentrancy"}, token,
    )
    if status != 200:
        print(f"practice start failed: {status} {practice}", file=sys.stderr)
        return 1
    print(f"practice session {practice['sessionId']} difficulty {practice['difficulty']}")
    print(practice.get("quotaMessage", ""))

    status, started = _request("POST", f"{base}/v1/start", {}, token)
    if status != 200:
        print(f"reward start failed: {status} {started}", file=sys.stderr)
        return 1
    print(
        f"reward session {started['sessionId']} "
        f"class {started['vulnClass']} difficulty {started['difficulty']} "
        f"pool {started['pool']} public id {started['challengeId']}"
    )
    if started["pool"] != started["difficulty"]:
        print("pool must equal difficulty", file=sys.stderr)
        return 1
    if "seed" in started:
        print("reward start leaked a seed", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT mother_id, seed, challenge_id FROM sessions WHERE session_id=?",
        (started["sessionId"],),
    ).fetchone()
    if row is None:
        print("session missing from the server database", file=sys.stderr)
        return 1
    if row["mother_id"] in started["challengeId"] or str(row["seed"]) in started["challengeId"]:
        print("public challenge id contains the mother or seed", file=sys.stderr)
        return 1
    challenge_dir = cache / row["challenge_id"]
    target = started["targetFile"]
    patch = (challenge_dir / "solution" / "patched" / target).read_text()
    poc = next((challenge_dir / "solution" / "poc").glob("*.t.sol")).read_text()
    print(f"submitting the reference fix for {row['mother_id']} (server cache, not shown to agents)")

    status, graded = _request("POST", f"{base}/v1/submit", {
        "sessionId": started["sessionId"], "patch": patch, "poc": poc,
    }, token)
    if status != 200 or not graded.get("passed"):
        print(f"submit failed: {status} {json.dumps(graded)[:2000]}", file=sys.stderr)
        return 1
    print(graded.get("summary"))
    print(graded.get("quotaMessage", ""))
    if "seed" in graded.get("result", {}):
        print("submit leaked the seed", file=sys.stderr)
        return 1

    status, auth = _request("POST", f"{base}/v1/authorize", {
        "sessionId": started["sessionId"], "action": "mint",
    }, token)
    if status != 200:
        print(f"authorize failed: {status} {auth}", file=sys.stderr)
        return 1
    minted = dict(auth["auth"])
    if minted["pool"] != minted["difficulty"]:
        print("signed pool does not match difficulty", file=sys.stderr)
        return 1
    minted["signature"] = auth["signature"]
    out_path.write_text(json.dumps(minted, indent=2))
    print(f"authorized mint pool={minted['pool']} signer={auth['signer']}")
    print(auth.get("quotaMessage", ""))
    print(f"wrote {out_path}")

    status, board = _request("GET", f"{base}/v1/leaderboard?limit=5")
    print("leaderboard:", json.dumps(board))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
