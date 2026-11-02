#!/usr/bin/env python3
"""Reveal a commit-reveal batch, then recompute tier and artId from chain data.

    # Read-only. No key. Compares already-revealed tokens to a local replay.
    RPC_URL=https://bsc-testnet-rpc.publicnode.com \\
    AXVIGIL_COLLECTIBLE=0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658 \\
    python3 scripts/reveal_and_recompute.py --dry-run

    # Check a local seed against the committed hash, still without sending.
    SEED_FILE=/path/to/batch2.seed BATCH_ID=2 \\
    python3 scripts/reveal_and_recompute.py --dry-run

    # Operator, later, from a machine that holds the owner key:
    OWNER_KEY=0x... SEED_FILE=/path/to/batch2.seed BATCH_ID=2 \\
    python3 scripts/reveal_and_recompute.py

Batch 2 on the original collectible is already revealed. Its seed is public
on chain and recorded in deployments/bsc-testnet-97.json. This script does
not contain a key. Use it to recompute that batch, or to reveal a later batch
from a seed file that stays out of git.

Recompute walks token ids in order. A token whose batch seed is not on chain
and was not supplied with SEED_FILE is reported as not yet recomputable.
tokenURI before reveal is the unrevealed URI; after reveal it is baseURI + artId.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from axvigil_backend.rarity_replay import replay  # noqa: E402

DEFAULT_COLLECTIBLE = "0x06580BFc1626f7DD3d7B841FD304e6f2B23e4658"


def cast(args: list[str]) -> str:
    proc = subprocess.run(
        ["cast", *args], check=True, text=True, capture_output=True,
    )
    return proc.stdout.strip()


def call(rpc: str, to: str, sig: str, *params: str) -> str:
    return cast(["call", to, sig, *params, "--rpc-url", rpc])


def keccak_packed_bytes32(seed: str) -> str:
    """keccak256(abi.encodePacked(bytes32)). `cast keccak` hashes the raw 32 bytes."""
    raw = seed[2:] if seed.startswith("0x") else seed
    if len(raw) != 64:
        raise SystemExit("seed must be a 32-byte hex value")
    return cast(["keccak", "0x" + raw])


def load_seed(path: str | None) -> str | None:
    if not path:
        return None
    text = Path(path).read_text().strip().split()[0]
    if not text.startswith("0x"):
        text = "0x" + text
    return text


def _cast_fields(raw: str) -> list[str]:
    """One decoded field per line. Drop cast's `[2e4]` annotation and quotes."""
    fields = []
    for line in raw.splitlines():
        text = line.strip()
        if not text or text in {"(", ")"}:
            continue
        if " [" in text:
            text = text.split(" [", 1)[0].strip()
        fields.append(text.strip().strip('"'))
    return fields


def parse_token(raw: str) -> dict:
    parts = _cast_fields(raw)
    if len(parts) < 8:
        raise SystemExit(f"could not parse tokenData: {raw}")
    return {
        "vulnClass": int(parts[0], 0),
        "difficulty": int(parts[1], 0),
        "pool": int(parts[2], 0),
        "tier": int(parts[3], 0),
        "revealed": parts[4].lower() == "true",
        "batchId": int(parts[5], 0),
        "artId": int(parts[6], 0),
        "entropy": parts[7],
    }


def parse_batch(raw: str) -> dict:
    parts = _cast_fields(raw)
    if len(parts) < 3:
        raise SystemExit(f"could not parse batches(): {raw}")
    return {"seedHash": parts[0], "seed": parts[1], "revealed": parts[2].lower() == "true"}


def rand_for(seed: str, entropy: str) -> int:
    # keccak256(abi.encode(bytes32, bytes32)) — abi.encode pads each word to 32 bytes.
    encoded = cast(["abi-encode", "f(bytes32,bytes32)", seed, entropy])
    digest = cast(["keccak", encoded])
    return int(digest, 16)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Reveal a batch seed and recompute tiers")
    p.add_argument("--dry-run", action="store_true", help="read chain state; do not send")
    p.add_argument("--batch-id", type=int, default=int(os.environ.get("BATCH_ID", "0")))
    args = p.parse_args(argv)

    rpc = os.environ.get("RPC_URL") or os.environ.get("BSC_TESTNET_RPC")
    if not rpc:
        raise SystemExit("Set RPC_URL")
    nft = os.environ.get("AXVIGIL_COLLECTIBLE", DEFAULT_COLLECTIBLE)
    seed = load_seed(os.environ.get("SEED_FILE"))
    batch_id = args.batch_id

    if batch_id and seed:
        committed = parse_batch(call(rpc, nft, "batches(uint32)(bytes32,bytes32,bool)", str(batch_id)))
        got = keccak_packed_bytes32(seed)
        print(f"batch {batch_id} seedHash match: {got.lower() == committed['seedHash'].lower()}")
        print(f"  committed: {committed['seedHash']}")
        print(f"  seedHash:  {got}")
        if not args.dry_run:
            owner = os.environ.get("OWNER_KEY")
            if not owner:
                raise SystemExit("Set OWNER_KEY to broadcast, or pass --dry-run")
            gas = os.environ.get("GAS_PRICE", "1000000000")
            legacy = ["--legacy", "--gas-price", gas]
            if not committed["revealed"]:
                print(cast([
                    "send", nft, "revealSeed(uint32,bytes32)", str(batch_id), seed,
                    "--private-key", owner, "--rpc-url", rpc, *legacy,
                ]))
            minted = int(call(rpc, nft, "totalMinted()(uint256)"), 0)
            print(cast([
                "send", nft, "revealTokens(uint256)", str(minted),
                "--private-key", owner, "--rpc-url", rpc, *legacy,
            ]))
        elif not committed["revealed"]:
            print("DRY-RUN: revealSeed was not sent. Batch seed is not on chain yet.")

    def chain_string(sig: str, *params: str) -> str:
        fields = _cast_fields(call(rpc, nft, sig, *params))
        return fields[0] if fields else ""

    total = int(call(rpc, nft, "totalMinted()(uint256)"), 0)
    base = chain_string("baseURI()(string)")
    unrevealed = chain_string("unrevealedURI()(string)")
    print(f"totalMinted: {total}")
    print(f"baseURI: {base!r}  unrevealedURI: {unrevealed!r}")

    tokens = []
    chain_rows = []
    seeds: dict[int, str] = {}
    if batch_id and seed:
        seeds[batch_id] = seed
    for token_id in range(1, total + 1):
        data = parse_token(call(
            rpc, nft,
            "tokenData(uint256)(uint8,uint8,uint8,uint8,bool,uint32,uint32,bytes32)",
            str(token_id),
        ))
        uri = chain_string("tokenURI(uint256)(string)", str(token_id))
        chain_rows.append({**data, "id": token_id, "tokenURI": uri})
        if data["batchId"] not in seeds:
            batch = parse_batch(call(
                rpc, nft, "batches(uint32)(bytes32,bytes32,bool)", str(data["batchId"]),
            ))
            if batch["revealed"] and int(batch["seed"], 16) != 0:
                seeds[data["batchId"]] = batch["seed"]
        if data["batchId"] not in seeds:
            print(f"token {token_id}: batch {data['batchId']} seed unknown; skip recompute")
            continue
        tokens.append({
            "id": token_id,
            "pool": data["pool"],
            "vulnClass": data["vulnClass"],
            "rand": rand_for(seeds[data["batchId"]], data["entropy"]),
        })

    replayed = {row["id"]: row for row in replay(tokens)}
    mismatches = 0
    for row in chain_rows:
        got = replayed.get(row["id"])
        if got is None:
            continue
        if not row["revealed"]:
            print(f"token {row['id']}: not revealed on chain yet; replay tier={got['tier']} artId={got['artId']} uri={row['tokenURI']}")
            if row["tokenURI"] != unrevealed:
                print("  tokenURI is not the unrevealed URI")
                mismatches += 1
            continue
        expected_uri = f"{base}{got['artId']}"
        same = row["tier"] == got["tier"] and row["artId"] == got["artId"] and row["tokenURI"] == expected_uri
        print(
            f"token {row['id']}: chain tier={row['tier']} artId={row['artId']} "
            f"replay tier={got['tier']} artId={got['artId']} match={same}"
        )
        if not same:
            mismatches += 1
    print(json.dumps({"checked": len(replayed), "mismatches": mismatches}))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
