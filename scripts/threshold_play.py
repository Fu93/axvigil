#!/usr/bin/env python3
"""Reward play against a local AxVigil API, solved by Muse Spark, then 2-of-3 validator signatures.

login -> POST /v1/start -> agent loop -> POST /v1/submit -> POST /v1/authorize
-> POST each validator /sign with the evidence bundle -> write the first two signatures.

Keys come from the environment (PLAYER_KEY, META_API_KEY). This file never prints them.
Set AXV_REPO to the repo root if it is not the parent of this script.
Set AXVIGIL_API, AGENT_ID, OUT, EVIDENCE_DIR.
Validator URLs default to http://127.0.0.1:9101, 9102, 9103.
"""
import json, os, sys, time, datetime, urllib.request, urllib.error
from pathlib import Path

REPO = os.environ.get("AXV_REPO") or str(Path(__file__).resolve().parents[1])
sys.path[:0] = [f"{REPO}/agent", f"{REPO}/verifier"]
from eth_account import Account
from eth_account.messages import encode_defunct
import axvigil_agent.model as M
from axvigil_agent.solver import solve
from axvigil_agent.__main__ import _default_forge, _default_solc

OUT = Path(os.environ["OUT"]); BASE = os.environ["AXVIGIL_API"].rstrip("/")
AGENT_ID = int(os.environ["AGENT_ID"]); CAP = int(os.environ.get("AXV_MAX_REQUESTS", "4"))
acct = Account.from_key(os.environ["PLAYER_KEY"])
VALIDATOR_URLS = [
    u.rstrip("/") for u in os.environ.get(
        "VALIDATOR_URLS", "http://127.0.0.1:9101,http://127.0.0.1:9102,http://127.0.0.1:9103"
    ).split(",") if u.strip()
]

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def log(*a): print(f"[{now()}]", *a, file=sys.stderr, flush=True)
_orig = urllib.request.urlopen

def api(method, path, body=None, token=None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    try:
        with _orig(req, timeout=900) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        t = e.read().decode()
        try: return e.code, json.loads(t)
        except Exception: return e.code, {"detail": t}

calls = []
class _Resp:
    def __init__(s, raw): s._raw = raw
    def read(s): return s._raw
    def __enter__(s): return s
    def __exit__(s, *a): return False

def tapped(req, timeout=None, *a, **k):
    if len(calls) >= CAP: raise RuntimeError(f"model request cap {CAP} reached")
    body = json.loads(req.data.decode()); t0 = time.time(); st = now()
    log(f"[api] Meta request #{len(calls)+1} POST {req.full_url} model={body.get('model')}")
    raw = _orig(req, timeout=max(timeout or 0, 300)).read(); d = json.loads(raw)
    rec = {"n": len(calls)+1, "url": req.full_url, "requestedModel": body.get("model"), "returnedModel": d.get("model"),
           "responseId": d.get("id"), "startedUtc": st, "latencySec": round(time.time()-t0, 2),
           "finishReason": d["choices"][0].get("finish_reason"), "usage": d.get("usage"), "content": d["choices"][0]["message"].get("content")}
    calls.append(rec)
    log(f"[api] Meta response #{rec['n']} id={rec['responseId']} model={rec['returnedModel']} latency={rec['latencySec']}s usage={json.dumps(rec['usage'])}")
    return _Resp(raw)
M.urllib.request.urlopen = tapped

def main():
    s, info = api("GET", "/v1/protocol_info")
    log(f"protocol_info {s}: chain {info.get('chainId')} verifyingContract {info.get('verifyingContract')} signer {info.get('signer')} ownership={info.get('ownershipCheck')}")
    assert info.get("ownershipCheck") == "enforced", "ownership must be enforced"
    s, ch = api("GET", f"/v1/auth/challenge?address={acct.address}&agentId={AGENT_ID}")
    sig = acct.sign_message(encode_defunct(text=ch["message"])).signature.hex()
    sig = sig if sig.startswith("0x") else "0x" + sig
    s, lg = api("POST", "/v1/auth/login", {"address": acct.address, "agentId": AGENT_ID, "nonce": ch["nonce"], "signature": sig})
    assert s == 200, (s, lg); tok = lg["token"]; log(f"login {s}: {lg['address']} agent {lg['agentId']}")
    s, st = api("POST", "/v1/start", {}, tok); assert s == 200, (s, st)
    log(f"reward start {s}: session {st['sessionId']} public id {st['challengeId']} class {st['vulnClass']} difficulty {st['difficulty']} pool {st['pool']} contract {st['contractName']}")
    json.dump({k: v for k, v in st.items()}, open(OUT / "start_response.json", "w"), indent=2)
    ws = OUT / "agent_workspace"; (ws / "src").mkdir(parents=True, exist_ok=True); (ws / "test").mkdir(exist_ok=True)
    (ws / "src" / st["targetFile"]).write_text(st["source"])
    (ws / "test" / "Hidden.t.sol").write_text(f'// SPDX-License-Identifier: MIT\npragma solidity {st["pragma"]};\nimport {{Test}} from "forge-std/Test.sol";\ncontract SelfCheckStub is Test {{ function test_stub() public pure {{}} }}\n')
    (ws / "challenge.json").write_text(json.dumps({"challengeId": st["challengeId"], "vulnClass": st["vulnClass"], "difficulty": st["difficulty"],
        "targetFile": st["targetFile"], "contractName": st["contractName"], "requiredFunctions": st["requiredFunctions"],
        "hiddenTests": "Hidden.t.sol", "pragma": st["pragma"], "limits": st["limits"]}, indent=2))
    c = M.MetaModelClient(); log(f"[agent] MetaModelClient base_url={c.base_url} model={c.model} (key from env, not shown); oracle=OFF")
    oc = solve(c, ws, max_iters=CAP, forge_bin=_default_forge(), solc=_default_solc(), timeout_s=180, on_event=lambda m: log("[agent]", m))
    its = [{"iter": it.index, "selfCheckPassed": it.passed, "checks": it.checks, "log": it.log, "analysis": it.analysis} for it in oc.iterations]
    summ = {"requests": len(calls), "returnedModels": sorted({x["returnedModel"] for x in calls if x["returnedModel"]}),
            "usageTotals": {k: sum((x["usage"] or {}).get(k, 0) for x in calls) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "selfCheckIterations": its, "calls": calls}
    json.dump(summ, open(OUT / "api_calls.json", "w"), indent=2)
    if not oc.solved:
        log("[agent] self-check never passed; NOT submitting (session left unsubmitted)"); return 3
    (OUT / f"submitted_{st['targetFile']}").write_text(oc.final_patch); (OUT / "submitted_Poc.t.sol").write_text(oc.final_poc)
    log(f"[agent] self-check passed after {len(oc.iterations)} iteration(s); submitting ONCE to the server")
    s, gr = api("POST", "/v1/submit", {"sessionId": st["sessionId"], "patch": oc.final_patch, "poc": oc.final_poc}, tok)
    json.dump(gr, open(OUT / "submit_response.json", "w"), indent=2)
    log(f"server submit {s}: passed={gr.get('passed')} {gr.get('summary', '')}")
    if s != 200 or not gr.get("passed"): log("server grade did not pass; stopping before authorize"); return 4
    s, au = api("POST", "/v1/authorize", {"sessionId": st["sessionId"], "action": "mint"}, tok)
    assert s == 200, (s, au)
    json.dump(au, open(OUT / "authorize_response.json", "w"), indent=2)
    m = dict(au["auth"]); m["backendSignature"] = au["signature"]; m["backendSigner"] = au.get("signer"); m["evidenceCid"] = au.get("evidenceCid")
    json.dump(m, open(OUT / "mint_auth.json", "w"), indent=2)
    log(f"authorize {s}: coordinator MintAuth submissionHash {m['submissionHash']} pool {m['pool']} evidenceCid {au.get('evidenceCid')}")
    sub = au["auth"]["submissionHash"]
    mpath = Path(os.environ["EVIDENCE_DIR"]) / sub / "manifest.json"
    manifest = json.loads(mpath.read_text())
    log(f"evidence bundle {mpath} cid {(mpath.parent / 'cid.txt').read_text().strip()}")
    sigs, results = [], []
    for url in VALIDATOR_URLS:
        t0 = time.time()
        req = urllib.request.Request(url + "/sign", data=json.dumps({"manifest": manifest, "auth": au["auth"]}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with _orig(req, timeout=900) as r: code, body = r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read() or b"{}"
            try: body = json.loads(raw)
            except Exception: body = {"error": raw.decode()}
            code = e.code
        results.append({"url": url, "status": code, "seconds": round(time.time() - t0, 1), **body})
        log(f"validator {url} -> {code} signer={body.get('signer')} error={body.get('error')} ({round(time.time()-t0,1)}s)")
        if code == 200: sigs.append(body["signature"])
    json.dump(results, open(OUT / "validator_signatures.json", "w"), indent=2)
    if len(sigs) < 2:
        log("fewer than 2 validator signatures; no mint")
        return 5
    (OUT / "mint_signatures.txt").write_text("[" + ",".join(sigs[:2]) + "]\n")
    log(f"collected {len(sigs)} validator signatures; using the first 2 for mint(auth, bytes[])")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
