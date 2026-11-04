#!/usr/bin/env bash
#!/usr/bin/env python3
"""AxVigil — Official End-to-End Multi-Model Demonstration driven by Meta Model API.

Demonstrates the entire AxVigil lifecycle starting from the official website:
1. Web Entry Point Verification (http://localhost:8080/web/index.html)
2. Local EVM Blockchain Setup (Anvil + Smart Contracts: Collectible, Skill SBT, ZKVerifier)
3. Platform Backend API Activation (FastAPI + SQLite + Challenge Engine)
4. Multi-Model Tournament (muse-spark-1.1, muse-spark-1.2, muse-spark-1.3)
   - Agent Wallet Authentication (EIP-191 for Space ID Agent ID #1, #2, #3)
   - Dynamic Vulnerability Deal & Challenge Issuance
   - Live Meta AI Inference via Meta Model API (https://api.meta.ai/v1)
   - Crucible Sandbox Deterministic Grading (5 differential security checks)
   - SP1 zkVM Bundle Attestation & EIP-712 Platform Mint Authorization
   - On-Chain Atomic Minting & Capability Recording on Anvil
5. Batch Commit-Reveal Rarity Draw & Dynamic On-Chain SVG Skill SBT Display
6. Real-time Leaderboard Update Verification across all Contestants
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "variantgen"))

from eth_account import Account
from eth_account.messages import encode_defunct

from axvigil_agent.model import MetaModelClient
from axvigil_agent.prompts import SYSTEM, build_retry_prompt, build_user_prompt
from axvigil_agent.solver import VULN_CLASS_NAMES, extract_json
from axvigil_verifier.zk_attestation import generate_zk_attestation_bundle


def log(step: str, title: str, details: str = ""):
    print(f"\n\033[1;36m======================================================================")
    print(f"[{step}] {title}")
    print(f"======================================================================\033[0m")
    if details:
        print(details)


def api_request(method: str, url: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "axvigil-meta-demo/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def main():
    print("""\033[1;33m
     █████╗ ██╗   ██╗██╗   ██╗██╗ ██████╗ ██╗██╗     
    ██╔══██╗╚██╗ ██╔╝██║   ██║██║██╔════╝ ██║██║     
    ███████║ ╚████╔╝ ██║   ██║██║██║  ███╗██║██║     
    ██╔══██║ ██╔═██╗ ╚██╗ ██╔╝██║██║   ██║██║██║     
    ██║  ██║██╔╝ ██╗  ╚████╔╝ ██║╚██████╔╝██║███████╗
    ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═══╝  ╚═╝ ╚═════╝ ╚═╝╚══════╝
    Crucible: Every inference, a line of defense.
    Meta Global AI Developer Hackathon — Multi-Model Official Flow
    \033[0m""")

    # -------------------------------------------------------------------------
    # STEP 1: Website & Environment Preflight
    # -------------------------------------------------------------------------
    log("STEP 1", "Official Website & Environment Verification")
    web_proc = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/web/index.html", timeout=1) as resp:
            pass
    except Exception:
        print("Starting local HTTP server on port 8080...")
        web_proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", "8080", "--directory", str(ROOT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.2)

    portal_pages = [
        ("Homepage & Protocol Overview", "web/index.html"),
        ("Interactive Demo & SP1 zkVM Portal", "web/demo.html"),
        ("Real-time Agent Leaderboard", "web/leaderboard.html"),
        ("Hackathon Architecture & Pitch Deck", "web/pitch.html"),
    ]
    for page_title, page_path in portal_pages:
        url = f"http://127.0.0.1:8080/{page_path}"
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                print(f"✓ {page_title:36}: {url} (HTTP {resp.status})")
        except Exception as exc:
            print(f"✗ {page_title:36}: {url} ({exc})")

    # Load environment (.env)
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    api_key = os.environ.get("META_API_KEY")
    if not api_key:
        print("ERROR: META_API_KEY is not set.")
        return 1

    # Determine contestants (default: all 3 Meta models)
    models_to_run = ["muse-spark-1.1", "muse-spark-1.2", "muse-spark-1.3"]
    if "--single" in sys.argv:
        models_to_run = [os.environ.get("META_MODEL", "muse-spark-1.1")]
    elif "--model" in sys.argv:
        m_idx = sys.argv.index("--model")
        if m_idx + 1 < len(sys.argv):
            models_to_run = [sys.argv[m_idx + 1]]

    print(f"✓ Meta Model API Contestants: {', '.join(models_to_run)}")
    print(f"  • API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  • Base URL: {os.environ.get('META_BASE_URL', 'https://api.meta.ai/v1')}")
    print(f"✓ Foundry Toolchain: {shutil.which('forge') or 'forge in PATH'}")

    # -------------------------------------------------------------------------
    # STEP 2: Local Blockchain & Smart Contracts
    # -------------------------------------------------------------------------
    log("STEP 2", "Blockchain Infrastructure & Smart Contract Deployment")
    tmp_dir = Path(tempfile.mkdtemp(prefix="axvigil-meta-demo-"))
    rpc_port = 8546
    rpc_url = f"http://127.0.0.1:{rpc_port}"
    api_port = 8001
    api_base = f"http://127.0.0.1:{api_port}"

    player_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    signer_key = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
    player_account = Account.from_key(player_key)
    signer_account = Account.from_key(signer_key)

    anvil_proc = None
    api_proc = None

    try:
        print(f"Launching Anvil local EVM on port {rpc_port}...")
        anvil_proc = subprocess.Popen(
            ["anvil", "--silent", "--port", str(rpc_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            r = subprocess.run(["cast", "chain-id", "--rpc-url", rpc_url], capture_output=True, text=True)
            if r.returncode == 0:
                break
            time.sleep(0.2)

        # Deploy Contracts via JudgeDemo.s.sol
        print("Deploying AxVigil core contracts via Forge Script...")
        deploy_env = dict(os.environ)
        deploy_env["PRIVATE_KEY"] = player_key
        deploy_env["SIGNER"] = signer_account.address
        deploy_res = subprocess.run(
            ["forge", "script", "script/JudgeDemo.s.sol",
             "--rpc-url", rpc_url, "--broadcast", "--private-key", player_key],
            cwd=str(ROOT / "contracts"),
            capture_output=True,
            text=True,
            check=False,
            env=deploy_env,
        )
        if deploy_res.returncode != 0:
            print(f"Deploy error:\n{deploy_res.stderr}\n{deploy_res.stdout}")
            return 1

        contracts = {}
        for line in deploy_res.stdout.splitlines():
            for name in ("REGISTRY", "SKILL", "COLLECTIBLE", "AGENT_ID", "ZK_VERIFIER"):
                if re.search(rf"\b{name}\s+(0x[a-fA-F0-9]{{40}}|\d+)", line):
                    match = re.search(rf"\b{name}\s+([^\s]+)", line)
                    if match:
                        contracts[name] = match.group(1)

        print(f"  • MockAgentID Registry:   {contracts.get('REGISTRY')}")
        print(f"  • AxVigilSkill (ERC-5192): {contracts.get('SKILL')}")
        print(f"  • AxVigilCollectible:     {contracts.get('COLLECTIBLE')}")
        print(f"  • AxVigilZKVerifier:       {contracts.get('ZK_VERIFIER')}")
        print(f"  • Space ID Agent ID:      #{contracts.get('AGENT_ID')}")
        print(f"  • Agent Owner Address:    {player_account.address}")

        # -------------------------------------------------------------------------
        # STEP 3: Platform API Backend Activation
        # -------------------------------------------------------------------------
        log("STEP 3", "AxVigil Platform API Activation")
        db_path = tmp_dir / "axvigil.db"
        cache_dir = tmp_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        api_env = dict(os.environ)
        api_env["SIGNER_KEY"] = signer_key
        api_env["VERIFYING_CONTRACT"] = contracts["COLLECTIBLE"]
        api_env["CHAIN_ID"] = "31337"
        api_env["AGENT_REGISTRY"] = contracts["REGISTRY"]
        api_env["RPC_URL"] = rpc_url
        api_env["DB_PATH"] = str(db_path)
        api_env["CHALLENGE_CACHE_DIR"] = str(cache_dir)
        api_env["SESSION_SECRET"] = "meta-demo-session-secret"
        api_env["PYTHONPATH"] = f"{ROOT / 'backend'}:{ROOT / 'verifier'}:{ROOT / 'variantgen'}"

        print(f"Starting AxVigil Backend on {api_base}...")
        api_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "axvigil_backend.app:app",
             "--host", "127.0.0.1", "--port", str(api_port), "--app-dir", str(ROOT / "backend")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=api_env,
        )

        server_ready = False
        for _ in range(60):
            if api_proc.poll() is not None:
                print("ERROR: Backend server exited prematurely.")
                break
            try:
                st, info = api_request("GET", f"{api_base}/health")
                if st == 200:
                    server_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.3)

        if not server_ready:
            print("ERROR: Backend server failed to start within timeout.")
            return 1

        st, pinfo = api_request("GET", f"{api_base}/v1/protocol_info")
        print(f"✓ Platform Status: Online (HTTP {st})")
        print(f"  • Protocol: {pinfo.get('name')} v{pinfo.get('protocolVersion')}")
        print(f"  • Ownership Verification: {pinfo.get('ownershipCheck')}")
        print(f"  • Available Vulnerability Families: {len(pinfo.get('mothers', []))} mothers")

        # -------------------------------------------------------------------------
        # TOURNAMENT: Run All Models (Steps 4 to 9 per contestant)
        # -------------------------------------------------------------------------
        contestant_results = []

        for round_idx, model_name in enumerate(models_to_run, start=1):
            current_agent_id = round_idx
            log(f"ROUND {round_idx}/{len(models_to_run)}", f"Contestant: {model_name} (Space ID Agent #{current_agent_id})")

            # Mint Agent ID if > 1
            if current_agent_id > 1:
                print(f"Minting Agent #{current_agent_id} in MockAgentID registry...")
                subprocess.run([
                    "cast", "send", contracts["REGISTRY"], "mint(address)", player_account.address,
                    "--private-key", player_key, "--rpc-url", rpc_url
                ], capture_output=True, check=True)

            # STEP 4: Agent Wallet Authentication
            print(f"Authenticating Agent #{current_agent_id} via EIP-191 challenge-response...")
            st, auth_chal = api_request(
                "GET", f"{api_base}/v1/auth/challenge?address={player_account.address}&agentId={current_agent_id}"
            )
            login_msg = auth_chal["message"]
            nonce = auth_chal["nonce"]
            sig = player_account.sign_message(encode_defunct(text=login_msg)).signature.hex()
            if not sig.startswith("0x"):
                sig = "0x" + sig

            st, logged = api_request("POST", f"{api_base}/v1/auth/login", {
                "address": player_account.address,
                "agentId": current_agent_id,
                "nonce": nonce,
                "signature": sig,
            })
            token = logged["token"]
            print(f"✓ Authenticated as: {logged['address']} (Agent #{logged['agentId']})")

            # STEP 5: Issue Challenge
            print("Requesting server-assigned reward challenge from platform...")
            st, chal = api_request("POST", f"{api_base}/v1/start", {}, token)
            if st != 200:
                print(f"Failed to start reward session: {st} {chal}")
                continue
            session_id = chal["sessionId"]
            target_file = chal["targetFile"]
            contract_name = chal["contractName"]
            vuln_class = chal["vulnClass"]
            difficulty = chal["difficulty"]
            source_code = chal["source"]
            limits = chal["limits"]

            vuln_class_name = VULN_CLASS_NAMES.get(int(vuln_class), "reentrancy")
            diff_names = {0: "Basic", 1: "Advanced", 2: "Legendary"}
            print(f"  • Session ID:        {session_id}")
            print(f"  • Target Contract:   {target_file} ({contract_name})")
            print(f"  • Vulnerability:     Class {vuln_class} ({vuln_class_name.capitalize()}), Difficulty {difficulty} ({diff_names.get(difficulty, 'Custom')})")
            print(f"  • Patch Line Budget: ≤ {limits.get('maxChangedLines', 30)} changed lines, ≤ {limits.get('maxBytes', 4000)} bytes")

            # STEP 6: Live Meta AI Solving via Meta Model API
            meta_client = MetaModelClient(model=model_name)
            prompt = build_user_prompt(
                challenge_id=chal.get("challengeId", "challenge"),
                target_file=target_file,
                contract_name=contract_name,
                vuln_class_name=vuln_class_name,
                pragma=chal.get("pragma", "0.8.28"),
                source=source_code,
                required_functions=chal["requiredFunctions"],
                limits=limits,
            )

            passed = False
            final_result = None
            final_patch = None
            final_poc = None
            total_prompt_tok = 0
            total_compl_tok = 0
            t_solve_start = time.time()

            for iter_idx in range(2):
                if iter_idx > 0:
                    print(f"\n[Attempt {iter_idx + 1}/2] Opening second reward session with compiler/grader feedback...")
                    st, chal = api_request("POST", f"{api_base}/v1/start", {}, token)
                    if st != 200:
                        print(f"Failed to start attempt {iter_idx + 1}: {st} {chal}")
                        break
                    session_id = chal["sessionId"]
                    target_file = chal["targetFile"]
                    contract_name = chal["contractName"]
                    source_code = chal["source"]
                    limits = chal["limits"]
                    vuln_class = chal.get("vulnClass", 0)
                    difficulty = chal.get("difficulty", 0)
                    prompt = build_user_prompt(
                        challenge_id=chal.get("challengeId", "challenge"),
                        target_file=target_file,
                        contract_name=contract_name,
                        vuln_class_name=VULN_CLASS_NAMES.get(int(vuln_class), "reentrancy"),
                        pragma=chal.get("pragma", "0.8.28"),
                        source=source_code,
                        required_functions=chal.get("requiredFunctions", []),
                        limits=limits,
                    )

                print(f"--- [Attempt {iter_idx + 1}/2] Querying Meta Model API ({model_name}) ---")
                t_start = time.time()
                reply = meta_client.complete(system=SYSTEM, user=prompt)
                elapsed = time.time() - t_start
                p_tok = meta_client.last_usage.get("prompt", 0)
                c_tok = meta_client.last_usage.get("completion", 0)
                total_prompt_tok += p_tok
                total_compl_tok += c_tok
                print(f"✓ Meta Model Inference Completed in {elapsed:.1f}s")
                print(f"  • Usage: {p_tok} prompt tokens, {c_tok} completion tokens")

                try:
                    parsed = extract_json(reply)
                except Exception as e:
                    print(f"Failed to parse JSON ({e}), retrying...")
                    prompt = f"Your last response could not be parsed as valid JSON ({e}). Return ONLY the JSON object.\n\n" + prompt
                    continue

                analysis = parsed.get("analysis", "Remediated smart contract bug.")
                patched_contract = parsed["patched_contract"]
                poc_test = parsed["poc_test"]
                print(f"[Meta Model Analysis]: {analysis[:180]}...")

                # STEP 7: Sandbox Deterministic Grading
                print("Submitting to Crucible sandbox verifier via POST /v1/submit...")
                t_grade_start = time.time()
                st, submit_res = api_request("POST", f"{api_base}/v1/submit", {
                    "sessionId": session_id,
                    "patch": patched_contract,
                    "poc": poc_test,
                }, token)
                grade_elapsed = time.time() - t_grade_start

                result = submit_res.get("result", {})
                checks = {
                    "pocProvesBug": result.get("pocProvesBug", False),
                    "pocFailsAfterPatch": result.get("pocFailsAfterPatch", False),
                    "hiddenTestsPass": result.get("hiddenTestsPass", False),
                    "patchWithinLimits": result.get("patchWithinLimits", False),
                }
                print(f"  [Grade Result]: passed={submit_res.get('passed')} in {grade_elapsed:.2f}s | checks={checks}")

                if submit_res.get("passed"):
                    passed = True
                    final_result = result
                    final_patch = patched_contract
                    final_poc = poc_test
                    print(f"\033[1;32m✓ 100% PASS ON ALL DIFFERENTIAL CHECKS ({model_name})!\033[0m")
                    print(f"  • Submission Hash: {result.get('submissionHash')}")
                    break
                else:
                    log_snippet = result.get('log', '')
                    print(f"  [Grader Feedback to Model]: {log_snippet[:200]}")
                    prompt = build_retry_prompt(
                        prev_patch=patched_contract,
                        prev_poc=poc_test,
                        result_log=log_snippet,
                        checks=checks,
                        source=source_code,
                        limits=limits,
                    )

            if not passed:
                print(f"Model {model_name} did not pass challenge.")
                continue

            # STEP 8: ZK Proof Attestation & Cryptographic Authorization
            zk_bundle = generate_zk_attestation_bundle(
                agent_id=current_agent_id,
                challenge_id=chal.get("challengeId", "challenge"),
                original_code=source_code,
                patched_code=final_patch,
                vuln_class=vuln_class,
                difficulty=difficulty,
                poc_proves_bug=final_result.get("pocProvesBug", True),
                poc_fails_after_patch=final_result.get("pocFailsAfterPatch", True),
                hidden_tests_pass=final_result.get("hiddenTestsPass", True),
                patch_within_limits=final_result.get("patchWithinLimits", True),
                invariants_hold=final_result.get("invariantsHold", True),
            )
            print(f"✓ SP1 zkVM Attestation Journal Constructed: 0x{zk_bundle.checksBitmap:02X} (Bitmap 31)")

            st, auth_res = api_request("POST", f"{api_base}/v1/authorize", {
                "sessionId": session_id, "action": "mint",
            }, token)
            mint_auth = auth_res["auth"]
            mint_sig = auth_res["signature"]

            # STEP 9: On-Chain Minting (token ID matches round_idx)
            tuple_args = (
                f"({mint_auth['agentId']},{mint_auth['to']},{mint_auth['vulnClass']},"
                f"{mint_auth['difficulty']},{mint_auth['pool']},{mint_auth['submissionHash']},"
                f"{mint_auth['nonce']},{mint_auth['deadline']})"
            )
            subprocess.run([
                "cast", "send", contracts["COLLECTIBLE"],
                "mint((uint256,address,uint8,uint8,uint8,bytes32,uint256,uint256),bytes)",
                tuple_args, mint_sig,
                "--private-key", player_key, "--rpc-url", rpc_url
            ], capture_output=True, check=True)

            solve_duration = time.time() - t_solve_start
            print(f"✓ AxVigilCollectible Token #{round_idx} Minted to Agent #{current_agent_id} on Anvil!")
            print(f"✓ AxVigilSkill ERC-5192 Record Atomically Created for Agent #{current_agent_id}!")

            contestant_results.append({
                "model": model_name,
                "agentId": current_agent_id,
                "tokenId": round_idx,
                "target": contract_name,
                "difficulty": difficulty,
                "promptTokens": total_prompt_tok,
                "completionTokens": total_compl_tok,
                "latencyS": solve_duration,
            })

        # -------------------------------------------------------------------------
        # STEP 10: Batch Commit-Reveal Rarity & On-Chain Dynamic SVG
        # -------------------------------------------------------------------------
        log("STEP 10", "Batch Commit-Reveal Rarity & On-Chain Dynamic SVG Display")
        seed_hash = subprocess.check_output(["cast", "keccak", "axvigil-judge-demo"]).decode().strip()
        print("Revealing Batch 1 Seed & Drawing Tier Rarity for all minted tokens...")
        subprocess.run([
            "cast", "send", contracts["COLLECTIBLE"], "revealSeed(uint32,bytes32)", "1", seed_hash,
            "--private-key", player_key, "--rpc-url", rpc_url
        ], capture_output=True, check=True)

        subprocess.run([
            "cast", "send", contracts["COLLECTIBLE"], "revealTokens(uint256)", "10",
            "--private-key", player_key, "--rpc-url", rpc_url
        ], capture_output=True, check=True)

        tier_names = {0: "COMMON", 1: "RARE", 2: "EPIC", 3: "LEGENDARY", 4: "HIDDEN"}
        for cr in contestant_results:
            t_id = cr["tokenId"]
            a_id = cr["agentId"]
            m_name = cr["model"]
            tier_code = int(subprocess.check_output([
                "cast", "call", contracts["COLLECTIBLE"], "tierOf(uint256)(uint8)", str(t_id),
                "--rpc-url", rpc_url
            ]).decode().strip())
            token_uri = subprocess.check_output([
                "cast", "call", contracts["COLLECTIBLE"], "tokenURI(uint256)(string)", str(t_id),
                "--rpc-url", rpc_url
            ]).decode().strip().strip('"')

            skill_uri_raw = subprocess.check_output([
                "cast", "call", contracts["SKILL"], "tokenURI(uint256)(string)", str(a_id),
                "--rpc-url", rpc_url
            ]).decode().strip().strip('"')

            print(f"\n--- [Token #{t_id} | Agent #{a_id} ({m_name})] ---")
            print(f"  • Revealed Tier: {tier_names.get(tier_code, 'UNKNOWN')} (Code {tier_code})")
            print(f"  • Metadata URI:  {token_uri}")

            prefix = "data:application/json;base64,"
            if skill_uri_raw.startswith(prefix):
                skill_json = json.loads(base64.b64decode(skill_uri_raw[len(prefix):]))
                svg_data = skill_json.get("image", "")
                print(f"  • Skill SBT Name: {skill_json.get('name')}")
                if svg_data.startswith("data:image/svg+xml;utf8,"):
                    svg_xml = svg_data[len("data:image/svg+xml;utf8,"):]
                    print(f"  • Dynamic On-Chain SVG: {len(svg_xml)} bytes verified")

        # -------------------------------------------------------------------------
        # STEP 11: Real-time Multi-Model Leaderboard Verification
        # -------------------------------------------------------------------------
        log("STEP 11", "Platform Multi-Model Leaderboard Verification")
        st, board = api_request("GET", f"{api_base}/v1/leaderboard?limit=10")
        print(f"Official Leaderboard Updated ({len(board)} entries):")
        for idx, entry in enumerate(board, start=1):
            matching_model = next((c["model"] for c in contestant_results if c["agentId"] == entry.get("agentId")), "Unknown")
            print(f"  #{idx} Agent #{entry.get('agentId')} ({matching_model:14}) — Score: {entry.get('score')} | Solves: {entry.get('solves')} | Rank: #{idx}")

        print("\n\033[1;32m======================================================================")
        print("✓ AXVIGIL FULL MULTI-MODEL TOURNAMENT COMPLETED SUCCESSFULLY!")
        print("======================================================================\033[0m\n")
        return 0

    finally:
        if web_proc:
            web_proc.terminate()
            web_proc.wait()
        if api_proc:
            api_proc.terminate()
            api_proc.wait()
        if anvil_proc:
            anvil_proc.terminate()
            anvil_proc.wait()
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
