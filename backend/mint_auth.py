#!/usr/bin/env python3
"""Turn a passed verifier result into an AxVigil EIP-712 MintAuth signature.

This module signs authorizations only. It never submits a transaction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data

# Single source of truth for the MintAuth EIP-712 encoding lives in the signer module.
from backend.axvigil_backend.signer import mint_typed_data


def build_typed_data(*, chain_id: int, verifying_contract: str, auth: dict[str, Any]) -> dict[str, Any]:
    return mint_typed_data(chain_id, verifying_contract, auth)


def sign_authorization(private_key: str, typed_data: dict[str, Any]) -> tuple[str, str]:
    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=private_key)
    signature = signed.signature.hex()
    if not signature.startswith("0x"):
        signature = "0x" + signature
    return Account.from_key(private_key).address, signature


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign AxVigil MintAuth from a passed verifier result")
    parser.add_argument("--result", type=Path, required=True, help="verifier JSON result")
    parser.add_argument("--agent-id", type=int, required=True)
    parser.add_argument("--to", required=True, help="recipient address")
    parser.add_argument("--chain-id", type=int, required=True)
    parser.add_argument("--verifying-contract", required=True)
    parser.add_argument("--nonce", type=int, required=True)
    parser.add_argument("--deadline", type=int, required=True)
    parser.add_argument("--difficulty", type=int, default=0)
    parser.add_argument("--pool", type=int, default=0)
    parser.add_argument("--private-key-env", default="AXVIGIL_SIGNER_PRIVATE_KEY")
    args = parser.parse_args()

    private_key = os.environ.get(args.private_key_env)
    if not private_key:
        print(f"missing signer private key environment variable: {args.private_key_env}", file=sys.stderr)
        return 2
    try:
        grading = json.loads(args.result.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read verifier result: {exc}", file=sys.stderr)
        return 2
    if grading.get("challengeId") != "reentrancy-001":
        print("unsupported challenge result", file=sys.stderr)
        return 2
    if grading.get("passed") is not True:
        print("refusing to sign: verifier result is not passed", file=sys.stderr)
        return 1
    submission_hash = grading.get("submissionHash")
    if not isinstance(submission_hash, str) or len(submission_hash) != 66 or not submission_hash.startswith("0x"):
        print("verifier result has no valid submissionHash", file=sys.stderr)
        return 2
    if not (0 <= args.difficulty <= 2 and args.pool in (0, 1)):
        print("difficulty or pool is out of range", file=sys.stderr)
        return 2

    auth = {
        "agentId": args.agent_id,
        "to": args.to,
        "vulnClass": 0,  # REENTRANCY
        "difficulty": args.difficulty,
        "pool": args.pool,
        "submissionHash": submission_hash,
        "nonce": args.nonce,
        "deadline": args.deadline,
    }
    typed_data = build_typed_data(
        chain_id=args.chain_id,
        verifying_contract=args.verifying_contract,
        auth=auth,
    )
    try:
        signer, signature = sign_authorization(private_key, typed_data)
    except Exception as exc:  # noqa: BLE001 - CLI should return a useful error
        print(f"could not sign typed data: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"auth": auth, "signature": signature, "signer": signer, "typedData": typed_data}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
