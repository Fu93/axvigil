"""Deterministic evidence bundles for a graded submission.

The bundle is canonical JSON plus the patch, PoC, rendered source, and grader
log. Its CIDv1 (raw, sha2-256) is computed locally. Pinning is optional: set
IPFS_PIN_URL to POST the manifest; a pin failure does not fail the grade.

The variant seed is inside the bundle, because recomputing submissionHash
requires it. It is not a separate API field. seedCommitment is the keccak of
the seed's 8-byte big-endian encoding, so a reader can check the seed that
was published matches the commitment made at grade time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("axvigil")

# v1 bundles have the four original checks. v2 adds invariantsHold and the
# pinned fuzz schedule. Readers still accept v1: the new fields are compared
# only when the bundle records them.
BUNDLE_VERSION = 2
PROFILE_FIELDS = ("fuzzSeed", "fuzzRuns", "invariantRuns", "invariantDepth", "applied")

VERIFIER_FILES = (
    "grader.py",
    "keccak.py",
    "forge_runner.py",
    "toolchain.py",
    "model.py",
)


def canonical_json(obj: dict) -> bytes:
    """UTF-8 JSON with sorted keys and no insignificant whitespace."""
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def cid_v1_raw_sha256(data: bytes) -> str:
    """CIDv1, raw codec (0x55), sha2-256, base32 multibase (prefix ``b``)."""
    digest = hashlib.sha256(data).digest()
    multihash = bytes([0x12, 0x20]) + digest
    cid_bytes = bytes([0x01, 0x55]) + multihash
    # base64.b32encode is uppercase and padded. IPFS base32 is lowercase, unpadded.
    import base64
    text = base64.b32encode(cid_bytes).decode("ascii").rstrip("=").lower()
    return "b" + text


def seed_commitment(seed: int) -> str:
    """keccak256 of the seed as uint64 big-endian. Not the NFT seed and not the submission hash."""
    try:
        from axvigil_verifier.keccak import keccak256
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "verifier"))
        from axvigil_verifier.keccak import keccak256
    return "0x" + keccak256(int(seed).to_bytes(8, "big")).hex()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_tree(root: Path, names: list[str] | None = None) -> str:
    """sha256 of named files, or of every file under root, in path order."""
    h = hashlib.sha256()
    if names is None:
        files = sorted(p for p in root.rglob("*") if p.is_file())
    else:
        files = [root / name for name in names]
    for path in files:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes() if path.is_file() else b"")
        h.update(b"\0")
    return h.hexdigest()


def mother_content_hash(mother_dir: Path) -> str:
    return hash_tree(mother_dir)


def verifier_version_hash(verifier_pkg: Path) -> str:
    h = hashlib.sha256()
    for name in VERIFIER_FILES:
        path = verifier_pkg / name
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        if path.is_file():
            h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def repo_commit(repo_root: Path) -> str | None:
    """HEAD sha, with ``-dirty`` when the worktree has staged, unstaged, or untracked files."""
    try:
        head = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        ).strip()
        if not head:
            return None
        status = subprocess.check_output(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        )
        return head + ("-dirty" if status.strip() else "")
    except (subprocess.SubprocessError, OSError):
        return None


def toolchain_versions(forge_bin: str) -> dict:
    forge = "unknown"
    try:
        text = subprocess.check_output(
            [forge_bin, "--version"], text=True, timeout=10, stderr=subprocess.STDOUT,
        )
        forge = text.strip().splitlines()[0] if text.strip() else "unknown"
    except (subprocess.SubprocessError, OSError):
        pass
    return {
        "forge": forge,
        "solc": "0.8.28 via forge solc_version (SOLC pins a binary only when set)",
    }


def _pin(url: str, token: str | None, cid: str, body: bytes) -> str | None:
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Axvigil-Cid": cid,
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return f"pinned {resp.status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("evidence pin failed: %s", exc)
        return None


def invariant_profile_from_checks(checks: dict) -> dict:
    """Normalize the schedule stored on a grade into the bundle's profile object."""
    raw = checks.get("invariantProfile")
    if not isinstance(raw, dict):
        raw = {
            "fuzzSeed": checks.get("invariantFuzzSeed", 0),
            "fuzzRuns": checks.get("invariantFuzzRuns", 0),
            "invariantRuns": checks.get("invariantRuns", 0),
            "invariantDepth": checks.get("invariantDepth", 0),
            "applied": checks.get("invariantApplied", False),
        }
    return {
        "fuzzSeed": int(raw.get("fuzzSeed") or 0),
        "fuzzRuns": int(raw.get("fuzzRuns") or 0),
        "invariantRuns": int(raw.get("invariantRuns") or 0),
        "invariantDepth": int(raw.get("invariantDepth") or 0),
        "applied": bool(raw.get("applied")),
    }


def bundle_grade_matches(manifest: dict, grade: dict) -> list[tuple[str, bool]]:
    """Compare a bundle to a fresh grade.

    v1 manifests (no invariantsHold key) keep the original four checks plus
    `passed`. v2 manifests also compare invariantsHold and the fuzz schedule,
    so a re-grade that used a different seed or depth does not verify.
    """
    checks = manifest.get("checks") or {}
    version = int(manifest.get("bundleVersion") or 1)
    keys = ["passed", "pocProvesBug", "pocFailsAfterPatch", "hiddenTestsPass", "patchWithinLimits"]
    if version >= 2 or "invariantsHold" in checks:
        keys.append("invariantsHold")
    rows: list[tuple[str, bool]] = []
    for key in keys:
        rows.append((key, bool(checks.get(key)) == bool(grade.get(key))))
    recorded = manifest.get("invariantProfile")
    if version >= 2 or isinstance(recorded, dict):
        actual = grade.get("invariantProfile") or {}
        recorded = recorded or {}
        for field in PROFILE_FIELDS:
            if field == "applied":
                same = bool(recorded.get(field)) == bool(actual.get(field))
            else:
                same = int(recorded.get(field) or 0) == int(actual.get(field) or 0)
            rows.append((f"invariantProfile.{field}", same))
    return rows


def write_bundle(
    evidence_dir: Path,
    *,
    challenge_id: str,
    mother_id: str,
    mother_dir: Path,
    seed: int,
    source: str,
    patch: str,
    poc: str,
    grader_log: str,
    checks: dict,
    submission_hash: str,
    forge_bin: str,
    verifier_pkg: Path,
    repo_root: Path,
    pin_url: str | None = None,
    pin_token: str | None = None,
) -> dict:
    """Write the bundle and return the public fields (cid, seedCommitment, paths)."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    dest = evidence_dir / submission_hash
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "source.sol").write_text(source)
    (dest / "patch.sol").write_text(patch)
    (dest / "poc.t.sol").write_text(poc)
    (dest / "grader.log").write_text(grader_log)

    files = {
        "source.sol": sha256_bytes(source.encode("utf-8")),
        "patch.sol": sha256_bytes(patch.encode("utf-8")),
        "poc.t.sol": sha256_bytes(poc.encode("utf-8")),
        "grader.log": sha256_bytes(grader_log.encode("utf-8")),
    }
    profile = invariant_profile_from_checks(checks)
    hold = checks["invariantsHold"] if "invariantsHold" in checks else False
    manifest = {
        "bundleVersion": BUNDLE_VERSION,
        "challengeId": challenge_id,
        "motherId": mother_id,
        "motherHash": mother_content_hash(mother_dir),
        "repoCommit": repo_commit(repo_root),
        "seed": int(seed),
        "seedCommitment": seed_commitment(seed),
        "sourceSha256": files["source.sol"],
        "patch": patch,
        "poc": poc,
        "fileSha256": files,
        "toolchain": toolchain_versions(forge_bin),
        "verifierVersionHash": verifier_version_hash(verifier_pkg),
        "graderLog": grader_log,
        "invariantProfile": profile,
        "checks": {
            "pocProvesBug": bool(checks.get("pocProvesBug")),
            "pocFailsAfterPatch": bool(checks.get("pocFailsAfterPatch")),
            "hiddenTestsPass": bool(checks.get("hiddenTestsPass")),
            "patchWithinLimits": bool(checks.get("patchWithinLimits")),
            "invariantsHold": bool(hold),
            "passed": bool(checks.get("passed")),
        },
        "submissionHash": submission_hash,
        "onChain": {
            "tie": "Minted.submissionHash",
            "note": "The collectible metadata does not carry this hash. The Minted event does.",
        },
    }
    raw = canonical_json(manifest)
    (dest / "manifest.json").write_bytes(raw)
    cid = cid_v1_raw_sha256(raw)
    (dest / "cid.txt").write_text(cid + "\n")
    pin_status = None
    if pin_url:
        pin_status = _pin(pin_url, pin_token, cid, raw)
    return {
        "evidenceCid": cid,
        "seedCommitment": manifest["seedCommitment"],
        "evidenceDir": str(dest),
        "pinStatus": pin_status,
    }


def load_manifest(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def recompute_submission_hash(manifest: dict) -> str:
    from axvigil_verifier.keccak import submission_hash
    digest = submission_hash(
        manifest["challengeId"], int(manifest["seed"]), manifest["patch"], manifest["poc"],
    )
    return "0x" + digest.hex()
