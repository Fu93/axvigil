#!/usr/bin/env python3
"""Drive both challenge-window paths against a deployed AxVigil book.

(a) An honest record is left unchallenged and finalized after the window.
(b) A bad record is minted by a local collusion signature (validators refuse
    /sign), then challenged. Validators re-grade it and 2-of-3 sign an upheld
    ChallengeVerdict. resolveChallenge revokes the collectible.

No model calls. Keys come from the environment and are never printed.
Refuses chain id 97 unless I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1.

Required env:
  RPC_URL, CHAIN_ID
  AXVIGIL_COLLECTIBLE, AXVIGIL_SKILL, AXVIGIL_CHALLENGE, AGENT_REGISTRY
  PRIVATE_KEY          player / agent owner (also pays the operator bond)
  CHALLENGER_KEY       posts the challenge bond
  VALIDATOR_KEY_1/2/3  only used to collude-sign the deliberately bad mint
  VALIDATOR_URLS       default http://127.0.0.1:9101,9102,9103
Optional:
  GAS_PRICE            default 1000000000 (1 gwei, legacy)
  OPERATOR_BOND        wei, must match the deploy (default 2000000000000000)
  CHALLENGE_BOND       wei, must match the deploy (default 1000000000000000)
  CHALLENGE_WINDOW     seconds to advance (anvil) or sleep (other chains)
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "verifier"))

from eth_account import Account  # noqa: E402

from axvigil_backend.evidence import canonical_json, recompute_submission_hash  # noqa: E402
from axvigil_backend.signer import AuthSigner  # noqa: E402

STATUS = {0: "None", 1: "Pending", 2: "Challenged", 3: "Final", 4: "Revoked"}
GAS_PRICE = os.environ.get("GAS_PRICE", "1000000000")


def _need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.stderr.write(f"missing env {name}\n")
        raise SystemExit(2)
    return value


def _cast(args: list[str]) -> str:
    cmd = ["cast", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode or 1)
    return proc.stdout.strip()


def _send(pk: str, to: str, sig: str, args: list[str], value: int = 0) -> dict:
    cmd = [
        "cast", "send", to, sig, *args,
        "--rpc-url", _need("RPC_URL"),
        "--private-key", pk,
        "--legacy",
        "--gas-price", GAS_PRICE,
        "--json",
    ]
    if value:
        cmd.extend(["--value", str(value)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode or 1)
    receipt = json.loads(proc.stdout)
    gas = int(receipt.get("gasUsed", "0x0"), 16) if isinstance(receipt.get("gasUsed"), str) else int(receipt.get("gasUsed", 0))
    tx = receipt.get("transactionHash")
    return {"hash": tx, "gasUsed": gas, "status": receipt.get("status")}


def _call(to: str, sig: str, *args: str) -> str:
    return _cast(["call", to, sig, *args, "--rpc-url", _need("RPC_URL")])


def _manifest(label: str, passed: bool) -> dict:
    manifest = {
        "challengeId": f"challenge-demo-{label}",
        "seed": 1 if passed else 2,
        "patch": f"contract {label} {{}}",
        "poc": f"contract {label}Test {{}}",
        "axvTestGradePassed": passed,
    }
    manifest["submissionHash"] = recompute_submission_hash(manifest)
    return manifest


def _post(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode() or "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": raw}
        return exc.code, body


def _auth(agent_id: int, to: str, submission: str) -> dict:
    return {
        "agentId": agent_id,
        "to": to,
        "vulnClass": 0,
        "difficulty": 0,
        "pool": 0,
        "submissionHash": submission,
        "nonce": secrets.randbits(255),
        "deadline": int(time.time()) + 7200,
    }


def _tuple(auth: dict) -> str:
    return "({},{},{},{},{},{},{},{})".format(
        auth["agentId"], auth["to"], auth["vulnClass"], auth["difficulty"], auth["pool"],
        auth["submissionHash"], auth["nonce"], auth["deadline"],
    )


def _sign_local(auth: dict, keys: list[str], collectible: str, chain_id: int) -> list[str]:
    sigs = []
    for key in keys[:2]:
        signed = AuthSigner(key, chain_id, collectible).sign_prepared_mint(auth)
        sigs.append(signed.signature)
    return sigs


def _ask_sign(urls: list[str], manifest: dict, auth: dict) -> tuple[list[str], list[dict]]:
    sigs, rows = [], []
    for url in urls:
        code, body = _post(url + "/sign", {"manifest": manifest, "auth": auth})
        rows.append({"url": url, "status": code, "error": body.get("error"), "signer": body.get("signer")})
        if code == 200 and body.get("signature"):
            sigs.append(body["signature"])
    return sigs, rows


def _ask_challenge(
    urls: list[str],
    token_id: int,
    manifest: dict,
    *,
    round_num: int = 1,
    challenger: str = "0x" + "00" * 20,
) -> tuple[list[dict], list[dict]]:
    agreed, rows = [], []
    for url in urls:
        code, body = _post(
            url + "/challenge",
            {"tokenId": token_id, "manifest": manifest, "round": round_num, "challenger": challenger},
        )
        rows.append({"url": url, "status": code, "upheld": body.get("upheld"), "error": body.get("error")})
        if code == 200:
            agreed.append(body)
    return agreed, rows


def _advance(chain_id: int, window: int) -> None:
    rpc = _need("RPC_URL")
    if chain_id == 31337:
        _cast(["rpc", "anvil_increaseTime", str(window), "--rpc-url", rpc])
        _cast(["rpc", "anvil_mine", "1", "--rpc-url", rpc])
        return
    sys.stderr.write(f"waiting {window + 20}s for the challenge window on chain {chain_id}\n")
    time.sleep(window + 20)


def main() -> int:
    chain_id = int(_need("CHAIN_ID"))
    if chain_id == 97 and os.environ.get("I_UNDERSTAND_THIS_SENDS_TESTNET_TX") != "1":
        sys.stderr.write("refusing BSC testnet txs without I_UNDERSTAND_THIS_SENDS_TESTNET_TX=1\n")
        return 2
    observed = int(_cast(["chain-id", "--rpc-url", _need("RPC_URL")]))
    if observed != chain_id:
        sys.stderr.write(f"CHAIN_ID {chain_id} does not match RPC chain {observed}\n")
        return 2

    nft = _need("AXVIGIL_COLLECTIBLE")
    skill = _need("AXVIGIL_SKILL")
    book = _need("AXVIGIL_CHALLENGE")
    registry = _need("AGENT_REGISTRY")
    player_pk = _need("PRIVATE_KEY")
    challenger_pk = _need("CHALLENGER_KEY")
    player = Account.from_key(player_pk).address
    challenger = Account.from_key(challenger_pk).address
    vkeys = [_need("VALIDATOR_KEY_1"), _need("VALIDATOR_KEY_2"), _need("VALIDATOR_KEY_3")]
    urls = [u.strip().rstrip("/") for u in os.environ.get(
        "VALIDATOR_URLS", "http://127.0.0.1:9101,http://127.0.0.1:9102,http://127.0.0.1:9103"
    ).split(",") if u.strip()]
    operator_bond = int(os.environ.get("OPERATOR_BOND", "2000000000000000"))
    challenge_bond = int(os.environ.get("CHALLENGE_BOND", "1000000000000000"))
    window = int(os.environ.get("CHALLENGE_WINDOW", "120"))
    gas_total = 0

    def send(pk: str, to: str, sig: str, args: list[str], value: int = 0) -> str:
        nonlocal gas_total
        receipt = _send(pk, to, sig, args, value)
        gas_total += receipt["gasUsed"]
        if receipt.get("status") not in (1, "0x1", "1"):
            sys.stderr.write(f"tx {sig} status {receipt.get('status')} hash {receipt.get('hash')}\n")
            raise SystemExit(1)
        return receipt["hash"] or ""

    agent_id = int(_call(registry, "nextId()(uint256)"))
    send(player_pk, registry, "mint(address)", [player])
    owner = _call(registry, "ownerOf(uint256)(address)", str(agent_id))
    if owner.lower() != player.lower():
        sys.stderr.write(f"agent {agent_id} owner {owner} is not the player\n")
        return 3

    honest = _manifest("honest", True)
    bad = _manifest("bad", False)
    honest_auth = _auth(agent_id, player, honest["submissionHash"])
    bad_auth = _auth(agent_id, player, bad["submissionHash"])

    honest_sigs, honest_rows = _ask_sign(urls, honest, honest_auth)
    sys.stderr.write(f"honest /sign: {json.dumps(honest_rows)}\n")
    if len(honest_sigs) < 2:
        sys.stderr.write("honest bundle was not signed by 2 validators\n")
        return 4
    bad_sigs, bad_rows = _ask_sign(urls, bad, bad_auth)
    sys.stderr.write(f"bad /sign (expect refusals): {json.dumps(bad_rows)}\n")
    if any(row["status"] == 200 for row in bad_rows):
        sys.stderr.write("a validator signed the failing bundle; collusion demo is invalid\n")
        return 4
    collusion = _sign_local(bad_auth, vkeys, nft, chain_id)

    preview, preview_rows = _ask_challenge(urls, 2**255 - 1, honest)
    sys.stderr.write(f"honest re-grade preview: {json.dumps([{k: r.get(k) for k in ('upheld', 'reason', 'status')} for r in preview_rows])}\n")
    if not preview or any(row.get("upheld") for row in preview):
        sys.stderr.write("honest re-grade was not a rejection\n")
        return 4

    mint_sig = "mint((uint256,address,uint8,uint8,uint8,bytes32,uint256,uint256),bytes[])"
    honest_hash = send(
        player_pk, nft, mint_sig,
        [_tuple(honest_auth), "[" + ",".join(honest_sigs[:2]) + "]"],
        operator_bond,
    )
    bad_hash = send(
        player_pk, nft, mint_sig,
        [_tuple(bad_auth), "[" + ",".join(collusion) + "]"],
        operator_bond,
    )
    honest_id = int(_call(book, "tokenBySubmission(bytes32)(uint256)", honest["submissionHash"]))
    bad_id = int(_call(book, "tokenBySubmission(bytes32)(uint256)", bad["submissionHash"]))
    if int(_call(book, "status(uint256)(uint8)", str(honest_id))) != 1:
        sys.stderr.write("honest token is not Pending\n")
        return 3
    if int(_call(book, "status(uint256)(uint8)", str(bad_id))) != 1:
        sys.stderr.write("bad token is not Pending\n")
        return 3

    evidence = canonical_json(bad)
    challenge_hash = send(
        challenger_pk, book, "challenge(uint256,bytes)",
        [str(bad_id), "0x" + evidence.hex()],
        challenge_bond,
    )
    if int(_call(book, "status(uint256)(uint8)", str(bad_id))) != 2:
        sys.stderr.write("bad token is not Challenged\n")
        return 3

    verdicts, verdict_rows = _ask_challenge(urls, bad_id, bad, round_num=1, challenger=challenger)
    sys.stderr.write(f"bad /challenge: {json.dumps(verdict_rows)}\n")
    upheld = [row for row in verdicts if row.get("upheld") is True]
    if len(upheld) < 2:
        sys.stderr.write("fewer than 2 upheld verdicts\n")
        return 4
    reason = upheld[0]["reasonHash"]
    if any(row["reasonHash"] != reason for row in upheld[:2]):
        sys.stderr.write("validators disagreed on reasonHash\n")
        return 4
    resolve_hash = send(
        player_pk, book, "resolveChallenge(uint256,bool,bytes32,bytes[])",
        [str(bad_id), "true", reason, "[" + ",".join(row["signature"] for row in upheld[:2]) + "]"],
    )
    if int(_call(book, "status(uint256)(uint8)", str(bad_id))) != 4:
        sys.stderr.write("bad token was not revoked\n")
        return 3
    flagged = _call(nft, "flagged(uint256)(bool)", str(bad_id)).lower()
    if flagged not in ("true", "1"):
        sys.stderr.write(f"collectible flagged={flagged}\n")
        return 3
    send(challenger_pk, book, "withdraw()", [])

    _advance(chain_id, window)
    if int(_call(book, "status(uint256)(uint8)", str(honest_id))) != 3:
        sys.stderr.write("honest token is not lazily Final after the window\n")
        return 3
    finalize_hash = send(player_pk, book, "finalize(uint256)", [str(honest_id)])
    send(player_pk, book, "withdraw()", [])

    valid = _call(skill, "isValid(uint256)(bool)", str(agent_id)).lower()
    if valid not in ("true", "1"):
        sys.stderr.write(f"skill isValid={valid} after one revoked and one finalized solve\n")
        return 3
    solves = int(_call(skill, "totalSolves(uint256)(uint32)", str(agent_id)))
    if solves != 1:
        sys.stderr.write(f"totalSolves={solves}, want 1 (bad solve slashed)\n")
        return 3

    cost_wei = gas_total * int(GAS_PRICE)
    summary = {
        "chainId": chain_id,
        "agentId": agent_id,
        "honestToken": honest_id,
        "badToken": bad_id,
        "honestStatus": STATUS[3],
        "badStatus": STATUS[4],
        "skillValid": True,
        "totalSolves": solves,
        "gasUsed": gas_total,
        "gasPriceWei": int(GAS_PRICE),
        "gasCostWei": cost_wei,
        "gasCostTbnb": cost_wei / 1e18,
        "operatorBondWei": operator_bond,
        "challengeBondWei": challenge_bond,
        "txs": {
            "honestMint": honest_hash,
            "badMint": bad_hash,
            "challenge": challenge_hash,
            "resolve": resolve_hash,
            "finalize": finalize_hash,
        },
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"challenge_play failed: {type(exc).__name__}: {exc}\n")
        raise SystemExit(1)
