"""Canonical AxVigil grade seal used as the NEAR bundle hash.

The submission hash itself is computed by ``axvigil_verifier.keccak`` and is
not recomputed here. This module hashes the grade outcome so a reader can
check the file that was anchored without depending on log lines, paths, or
wall-clock text.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SEAL_FIELDS = (
    "challengeId",
    "seed",
    "vulnClass",
    "difficulty",
    "passed",
    "submissionHash",
    "pocProvesBug",
    "pocFailsAfterPatch",
    "hiddenTestsPass",
    "patchWithinLimits",
    "invariantsHold",
)

SCHEMA = "axvigil-seal-1"


def canonical_json(obj: dict) -> bytes:
    """UTF-8 JSON, sorted keys, no insignificant whitespace, one trailing newline."""
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _require_hash(value: object) -> str:
    if not isinstance(value, str) or len(value) != 66 or not value.startswith("0x"):
        raise ValueError("submissionHash must be 0x plus 64 hex characters")
    hex_part = value[2:]
    if any(c not in "0123456789abcdefABCDEF" for c in hex_part):
        raise ValueError("submissionHash must be 0x plus 64 hex characters")
    return hex_part.lower()


def _require_int(value: object, label: str, upper: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < 0 or (upper is not None and value >= upper):
        raise ValueError(f"{label} out of range")
    return value


def seal_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Build the seal document from a verifier result object.

    Fields other than ``SEAL_FIELDS`` (the grader log, in particular) are not
    part of the bundle hash.
    """
    missing = [name for name in SEAL_FIELDS if name not in result]
    if missing:
        raise ValueError("verifier result is missing " + ", ".join(missing))
    for name in (
        "passed",
        "pocProvesBug",
        "pocFailsAfterPatch",
        "hiddenTestsPass",
        "patchWithinLimits",
        "invariantsHold",
    ):
        if not isinstance(result[name], bool):
            raise ValueError(f"{name} must be a boolean")
    evidence_hash = _require_hash(result["submissionHash"])
    body = {
        "challengeId": result["challengeId"],
        "seed": _require_int(result["seed"], "seed"),
        "vulnClass": _require_int(result["vulnClass"], "vulnClass", 3),
        "difficulty": _require_int(result["difficulty"], "difficulty", 3),
        "passed": result["passed"],
        "submissionHash": "0x" + evidence_hash,
        "pocProvesBug": result["pocProvesBug"],
        "pocFailsAfterPatch": result["pocFailsAfterPatch"],
        "hiddenTestsPass": result["hiddenTestsPass"],
        "patchWithinLimits": result["patchWithinLimits"],
        "invariantsHold": result["invariantsHold"],
    }
    if not isinstance(body["challengeId"], str) or not body["challengeId"]:
        raise ValueError("challengeId must be a non-empty string")
    canonical = canonical_json(body)
    return {
        "schema": SCHEMA,
        "evidence_hash": evidence_hash,
        "bundle_sha256": hashlib.sha256(canonical).hexdigest(),
        "vuln_class": body["vulnClass"],
        "difficulty": body["difficulty"],
        "passed": body["passed"],
        "challenge_id": body["challengeId"],
        "seed": body["seed"],
        "canonical": canonical.decode("utf-8"),
    }


def anchor_args(seal: dict[str, Any], window_seconds: int, claim_pass: bool) -> dict[str, Any]:
    """JSON arguments for ``anchor_evidence``.

    ``claim_pass`` is the false-claim demo. It sends ``passed: true`` while
    leaving ``bundle_sha256`` equal to the failing seal. The contract cannot
    see the seal body. A challenger later anchors that contradiction.
    """
    if seal.get("schema") != SCHEMA:
        raise ValueError("not an axvigil seal")
    if not isinstance(window_seconds, int) or isinstance(window_seconds, bool):
        raise ValueError("window_seconds must be an integer")
    if window_seconds < 1 or window_seconds > 30 * 24 * 60 * 60:
        raise ValueError("window_seconds out of range")
    passed = bool(seal["passed"])
    if not passed and not claim_pass:
        raise ValueError(
            "refusing to anchor a failing grade. "
            "The false-claim demo passes --claim-pass."
        )
    if claim_pass:
        passed = True
    return {
        "evidence_hash": seal["evidence_hash"],
        "bundle_sha256": seal["bundle_sha256"],
        "vuln_class": seal["vuln_class"],
        "difficulty": seal["difficulty"],
        "window_seconds": window_seconds,
        "passed": passed,
    }
