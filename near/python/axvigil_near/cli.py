"""Offline commands. Broadcasting is ``near/scripts/demo_testnet.sh``."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .keys import write_key_file
from .redact import assert_no_secret, redact, transaction_id
from .rpc import DEFAULT_RPC, assert_testnet_account, assert_testnet_rpc, call_view
from .seal import anchor_args, seal_from_result


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "verifier" / "axvigil_verifier").is_dir():
            return parent
    raise SystemExit("axvigil_near must live inside the AxVigil repository")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return value


def _run_verifier(challenge: Path, patch: Path, poc: Path, seed: int) -> dict[str, Any]:
    root = repo_root()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(root / "verifier"), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    cmd = [
        sys.executable,
        "-m",
        "axvigil_verifier",
        "grade",
        "--challenge",
        str(challenge),
        "--patch",
        str(patch),
        "--poc",
        str(poc),
        "--seed",
        str(seed),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode not in (0, 1):
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode or 1)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"verifier did not print JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise SystemExit("verifier JSON is not an object")
    return result


def grade_unfixed(challenge: Path, poc: Path, seed: int) -> dict[str, Any]:
    """Grade the challenge's own vulnerable source as if it were the patch."""
    root = repo_root()
    sys.path.insert(0, str(root / "verifier"))
    from axvigil_verifier.grader import grade
    from axvigil_verifier.toolchain import discover_solc, forge_executable

    meta = json.loads((challenge / "challenge.json").read_text())
    target = meta["targetFile"]
    tmp = Path(tempfile.mkdtemp(prefix="axv-unfixed-"))
    try:
        submission = tmp / "submission"
        (submission / "patched").mkdir(parents=True)
        (submission / "poc").mkdir()
        shutil.copy(challenge / "src" / target, submission / "patched" / target)
        shutil.copy(poc, submission / "poc" / "Poc.t.sol")
        result = grade(
            challenge,
            submission,
            seed=seed,
            forge_bin=forge_executable() or "forge",
            solc=discover_solc(),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return result.to_json()


def _write_or_print(document: object, out: Path | None) -> None:
    text = json.dumps(document, indent=2) + "\n"
    assert_no_secret(text)
    if out is None:
        sys.stdout.write(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


def _cmd_seal(args: argparse.Namespace) -> int:
    if args.result:
        result = _load_json(Path(args.result))
    else:
        result = _run_verifier(Path(args.challenge), Path(args.patch), Path(args.poc), args.seed)
    seal = seal_from_result(result)
    _write_or_print(seal, Path(args.out) if args.out else None)
    return 0


def _cmd_seal_unfixed(args: argparse.Namespace) -> int:
    result = grade_unfixed(Path(args.challenge), Path(args.poc), args.seed)
    seal = seal_from_result(result)
    if seal["passed"]:
        raise SystemExit("unfixed challenge passed; refusing to treat it as the bad record")
    _write_or_print(seal, Path(args.out) if args.out else None)
    return 0


def _cmd_anchor_args(args: argparse.Namespace) -> int:
    seal = _load_json(Path(args.seal))
    try:
        payload = anchor_args(seal, args.window_seconds, args.claim_pass)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.claim_pass and not seal.get("passed"):
        sys.stderr.write(
            "claim-pass: contract args say passed=true; "
            "bundle_sha256 is still the failing seal\n"
        )
    _write_or_print(payload, Path(args.out) if args.out else None)
    return 0


def _cmd_write_key(args: argparse.Namespace) -> int:
    public = write_key_file(args.account, Path(args.out))
    stored = json.loads(Path(args.out).read_text())
    if stored["private_key"] == public or stored["private_key"] in public:
        raise SystemExit("refusing to print the secret key")
    sys.stdout.write(public + "\n")
    return 0


def _cmd_redact(args: argparse.Namespace) -> int:
    text = Path(args.path).read_text() if args.path else sys.stdin.read()
    cleaned = redact(text)
    assert_no_secret(cleaned)
    if args.tx:
        found = transaction_id(text)
        if not found:
            raise SystemExit("no transaction id in command output")
        sys.stdout.write(found + "\n")
        return 0
    sys.stdout.write(cleaned)
    return 0


def _cmd_view(args: argparse.Namespace) -> int:
    rpc = assert_testnet_rpc(args.rpc)
    if args.deployment:
        deployment = _load_json(Path(args.deployment))
        contract = assert_testnet_account(deployment["contract"])
        agent = assert_testnet_account(deployment["agent"])
        report = {
            "contract": contract,
            "spec": call_view(rpc, contract, "spec", {}),
            "reputation": call_view(rpc, contract, "get_reputation", {"account": agent}),
            "honest": call_view(
                rpc,
                contract,
                "get_record",
                {"evidence_hash": deployment["honest_evidence_hash"]},
            ),
            "bad": call_view(
                rpc,
                contract,
                "get_record",
                {"evidence_hash": deployment["bad_evidence_hash"]},
            ),
        }
        _write_or_print(report, None)
        return 0
    contract = assert_testnet_account(args.contract)
    if args.agent:
        value = call_view(
            rpc,
            contract,
            "get_reputation",
            {"account": assert_testnet_account(args.agent)},
        )
    elif args.record:
        value = call_view(rpc, contract, "get_record", {"evidence_hash": args.record})
    else:
        value = call_view(rpc, contract, "get_config", {})
    _write_or_print(value, None)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="axvigil_near")
    sub = parser.add_subparsers(dest="cmd", required=True)

    seal = sub.add_parser("seal", help="seal a verifier result JSON, or run the verifier")
    seal.add_argument("--result", help="existing verifier result JSON")
    seal.add_argument("--challenge")
    seal.add_argument("--patch")
    seal.add_argument("--poc")
    seal.add_argument("--seed", type=int, default=0)
    seal.add_argument("--out")
    seal.set_defaults(func=_cmd_seal)

    unfixed = sub.add_parser("seal-unfixed", help="seal a grade of the unfixed challenge source")
    unfixed.add_argument("--challenge", required=True)
    unfixed.add_argument("--poc", required=True)
    unfixed.add_argument("--seed", type=int, default=0)
    unfixed.add_argument("--out")
    unfixed.set_defaults(func=_cmd_seal_unfixed)

    args_cmd = sub.add_parser("anchor-args", help="print anchor_evidence JSON arguments")
    args_cmd.add_argument("--seal", required=True)
    args_cmd.add_argument("--window-seconds", type=int, required=True)
    args_cmd.add_argument("--claim-pass", action="store_true")
    args_cmd.add_argument("--out")
    args_cmd.set_defaults(func=_cmd_anchor_args)

    key = sub.add_parser("write-key", help="write a 0600 key file and print the public key")
    key.add_argument("--account", required=True)
    key.add_argument("--out", required=True)
    key.set_defaults(func=_cmd_write_key)

    red = sub.add_parser("redact", help="redact private keys from a log")
    red.add_argument("path", nargs="?")
    red.add_argument("--tx", action="store_true", help="print the transaction id instead")
    red.set_defaults(func=_cmd_redact)

    view = sub.add_parser("view", help="read the testnet contract")
    view.add_argument("--rpc", default=DEFAULT_RPC)
    view.add_argument("--deployment")
    view.add_argument("--contract")
    view.add_argument("--agent")
    view.add_argument("--record")
    view.set_defaults(func=_cmd_view)

    parsed = parser.parse_args(argv)
    if parsed.cmd == "seal" and not parsed.result:
        if not (parsed.challenge and parsed.patch and parsed.poc):
            parser.error("seal needs --result or --challenge, --patch, and --poc")
    if parsed.cmd == "view" and not parsed.deployment and not parsed.contract:
        parser.error("view needs --deployment or --contract")
    try:
        return parsed.func(parsed)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
