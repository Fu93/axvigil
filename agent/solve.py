"""Muse-compatible solver client. Endpoint/model come from your provider dashboard.
No fabricated endpoint, no reference-answer shortcut, no automatic public-chain mint.
"""

import argparse
import json
import os
from pathlib import Path
import time
import httpx
from eth_account import Account
from backend.crypto import sign

SYSTEM = """You repair intentionally vulnerable, authorized local training contracts.
Return ONLY a JSON object with string keys patch and poc. patch is the complete replacement
Solidity source for contract Challenge; poc is a separate self-contained contract Attack
with function run(address target) external payable. No imports. The target is funded by
the verifier. Prove an actual victim-state violation on the original, stop it on the patch,
and preserve all normal functions. No cheatcodes. No test, config or filesystem changes.
Keep the patch small. Never connect to a public-chain attack target."""


def model_solve(code, instructions, feedback=None):
    url = os.environ["MUSE_CHAT_COMPLETIONS_URL"]
    if not url.startswith("https://"):
        raise ValueError("Muse endpoint must use HTTPS")
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": instructions + "\n" + code},
    ]
    if feedback:
        messages.append(
            {
                "role": "user",
                "content": "Previous verification feedback: " + json.dumps(feedback),
            }
        )
    for attempt in range(4):
        response = httpx.post(
            url,
            headers={"Authorization": "Bearer " + os.environ["MUSE_API_KEY"]},
            json={
                "model": os.environ["MUSE_MODEL"],
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 6000,
            },
            timeout=120,
        )
        if response.status_code not in (429, 502, 503):
            break
        time.sleep(2**attempt)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = "\n".join(content.splitlines()[1:-1])
    solution = json.loads(content)
    if set(solution) != {"patch", "poc"} or not all(
        isinstance(x, str) for x in solution.values()
    ):
        raise ValueError("Model must return exactly patch and poc source strings")
    return solution


def poll(client, task_id, token):
    deadline = time.monotonic() + 200
    while time.monotonic() < deadline:
        r = client.get(
            f"/api/challenges/{task_id}/status",
            headers={"Authorization": "Bearer " + token},
        )
        r.raise_for_status()
        result = r.json()
        if result["state"] not in ("calibrating", "grading"):
            return result
        time.sleep(2)
    raise TimeoutError("Verifier has not finished; use status endpoint to resume")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--agent-id", required=True, type=int)
    p.add_argument("--class", dest="vuln_class", type=int, choices=range(3), default=0)
    p.add_argument(
        "--output", type=Path, default=Path("artifacts/muse-submission.json")
    )
    args = p.parse_args()
    wallet = Account.from_key(os.environ["AGENT_WALLET_KEY"])
    with httpx.Client(base_url=args.api, timeout=30) as client:
        r = client.post(
            "/api/prepare",
            json={"wallet": wallet.address, "agentId": str(args.agent_id)},
        )
        r.raise_for_status()
        prep = r.json()
        r = client.post(
            "/api/login",
            json={
                "nonce": prep["nonce"],
                "signature": sign(prep["typedData"], wallet.key),
            },
        )
        r.raise_for_status()
        token = r.json()["token"]
        headers = {"Authorization": "Bearer " + token}
        r = client.post(
            "/api/start", json={"vulnClass": args.vuln_class}, headers=headers
        )
        r.raise_for_status()
        tid = r.json()["challengeId"]
        state = poll(client, tid, token)
        if state["state"] != "issued":
            raise RuntimeError("Reference preflight failed")
        code = ""
        i = 0
        while True:
            r = client.get(f"/api/challenges/{tid}/fragments/{i}", headers=headers)
            r.raise_for_status()
            part = r.json()
            code += part["code"]
            i += 1
            if i == part["total"]:
                break
        solution = model_solve(code, part["instructions"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"challengeId": tid, **solution}, indent=2))
        r = client.post(f"/api/challenges/{tid}/submit", json=solution, headers=headers)
        r.raise_for_status()
        result = poll(client, tid, token)
        print(json.dumps(result, indent=2))
        if result["state"] == "passed":
            r = client.post(f"/api/challenges/{tid}/authorize", headers=headers)
            r.raise_for_status()
            auth_path = args.output.with_suffix(".authorization.json")
            auth_path.write_text(json.dumps(r.json(), indent=2))
            print(
                f"Authorization saved to {auth_path}. Mint through the connected wallet UI."
            )


if __name__ == "__main__":
    main()
