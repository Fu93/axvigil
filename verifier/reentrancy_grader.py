#!/usr/bin/env python3
"""Deterministic AxVigil challenge grader for the reentrancy demo.

The grader runs the submitted PoC against the vulnerable baseline, applies the
submitted patch, then requires the PoC to fail and hidden tests to pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_PATCH_BYTES = 24_000
MAX_PATCH_LINES = 120


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout


def keccak256(data: bytes) -> str:
    try:
        from Crypto.Hash import keccak  # type: ignore
    except ImportError as exc:
        raise SystemExit("Missing dependency: install pycryptodome to compute submissionHash") from exc
    digest = keccak.new(digest_bits=256)
    digest.update(data)
    return "0x" + digest.hexdigest()


def result(**values: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "challengeId": "reentrancy-001",
        "seed": 0,
        "vulnClass": 0,
        "difficulty": 0,
        "pocProvesBug": False,
        "pocFailsAfterPatch": False,
        "hiddenTestsPass": False,
        "patchWithinLimits": False,
        "passed": False,
        "solveSeconds": None,
        "submissionHash": "0x" + "00" * 32,
        "log": "",
    }
    defaults.update(values)
    return defaults


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade an AxVigil reentrancy challenge submission")
    parser.add_argument("--challenge", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--poc", type=Path, required=True)
    parser.add_argument("--forge", default="forge")
    parser.add_argument("--json", action="store_true", help="emit only the result JSON")
    args = parser.parse_args()

    challenge = args.challenge.resolve()
    patch_path = args.patch.resolve()
    poc_path = args.poc.resolve()
    required = [challenge / "src/Vault.sol", challenge / "test/Hidden.t.sol"]
    if not all(path.is_file() for path in required):
        output = result(log="challenge is missing required fixture files")
        print(json.dumps(output, indent=2))
        return 2
    if not patch_path.is_file() or not poc_path.is_file():
        output = result(log="patch or PoC file does not exist")
        print(json.dumps(output, indent=2))
        return 2

    patch_bytes = patch_path.read_bytes()
    poc_bytes = poc_path.read_bytes()
    canonical = b"AXVIGIL\n" + patch_bytes.replace(b"\r\n", b"\n") + b"\n---POC---\n" + poc_bytes.replace(b"\r\n", b"\n")
    submission_hash = keccak256(canonical)
    patch_lines = patch_bytes.count(b"\n") + (0 if patch_bytes.endswith(b"\n") else 1)
    within_limits = len(patch_bytes) <= MAX_PATCH_BYTES and patch_lines <= MAX_PATCH_LINES
    if not within_limits:
        output = result(patchWithinLimits=False, submissionHash=submission_hash, log="patch exceeds size or line limits")
        print(json.dumps(output, indent=2))
        return 1

    forge_code, _ = run([args.forge, "--version"], challenge)
    if forge_code != 0:
        output = result(patchWithinLimits=True, submissionHash=submission_hash, log="forge is not installed or unavailable")
        print(json.dumps(output, indent=2))
        return 2

    with tempfile.TemporaryDirectory(prefix="axvigil-grade-") as temp_name:
        work = Path(temp_name) / "challenge"
        shutil.copytree(challenge, work)
        # forge-std is supplied by the repository's Foundry submodule.
        repo_lib = Path(__file__).resolve().parents[1] / "contracts/lib"
        if repo_lib.is_dir():
            try:
                (work / "lib").symlink_to(repo_lib, target_is_directory=True)
            except OSError:
                # Windows may deny directory symlinks without Developer Mode or elevation.
                # Copying the pinned submodules preserves deterministic grading semantics.
                shutil.copytree(repo_lib, work / "lib")
        submitted_poc = work / "test/SubmittedPoC.t.sol"
        submitted_poc.write_bytes(poc_bytes)

        init_code, init_log = run(["git", "init", "-q"], work)
        if init_code != 0:
            output = result(patchWithinLimits=True, submissionHash=submission_hash, log=init_log)
            print(json.dumps(output, indent=2))
            return 2
        run(["git", "add", "."], work)

        before_code, before_log = run([args.forge, "test", "--match-path", "test/SubmittedPoC.t.sol"], work)
        poc_proves_bug = before_code == 0

        check_code, check_log = run(["git", "apply", "--check", str(patch_path)], work)
        if check_code != 0:
            output = result(
                pocProvesBug=poc_proves_bug,
                patchWithinLimits=True,
                submissionHash=submission_hash,
                log=(before_log + "\npatch rejected:\n" + check_log)[-12000:],
            )
            print(json.dumps(output, indent=2))
            return 1
        apply_code, apply_log = run(["git", "apply", str(patch_path)], work)
        if apply_code != 0:
            output = result(pocProvesBug=poc_proves_bug, patchWithinLimits=True, submissionHash=submission_hash, log=apply_log)
            print(json.dumps(output, indent=2))
            return 1

        after_code, after_log = run([args.forge, "test", "--match-path", "test/SubmittedPoC.t.sol"], work)
        hidden_code, hidden_log = run([args.forge, "test", "--match-path", "test/Hidden.t.sol"], work)
        poc_fails_after_patch = after_code != 0
        hidden_passes = hidden_code == 0
        passed = poc_proves_bug and poc_fails_after_patch and hidden_passes
        logs = "\n".join([
            "[baseline PoC]", before_log,
            "[patched PoC; expected failure]", after_log,
            "[hidden tests]", hidden_log,
        ])
        output = result(
            pocProvesBug=poc_proves_bug,
            pocFailsAfterPatch=poc_fails_after_patch,
            hiddenTestsPass=hidden_passes,
            patchWithinLimits=True,
            passed=passed,
            submissionHash=submission_hash,
            log=logs[-12000:],
        )
        print(json.dumps(output, indent=2))
        return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
