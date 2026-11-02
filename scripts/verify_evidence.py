#!/usr/bin/env python3
"""Recompute a graded submission from an evidence bundle.

    python3 scripts/verify_evidence.py path/to/manifest.json
    python3 scripts/verify_evidence.py path/to/manifest.json --hash-only

Checks:
  1. manifest.json bytes hash to the CID in the sibling cid.txt, when present
  2. submissionHash == keccak(AXV1 || challengeId || seed || patch || poc)
  3. seedCommitment matches the seed
  4. unless --hash-only, re-render the mother at that seed and re-run the grader

The hidden tests come from the repo's mother templates, which are public in
git and are not part of the session payload the agent received.
Exit 0 when every check that ran matches the bundle.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "variantgen"))

from axvigil_backend.evidence import (  # noqa: E402
    canonical_json,
    cid_v1_raw_sha256,
    load_manifest,
    recompute_submission_hash,
    seed_commitment,
)


def _grade(manifest: dict) -> dict:
    from axvigil_verifier.grader import grade
    from variantgen.render import Mother, render_challenge

    mother_dir = ROOT / "mothers" / manifest["motherId"]
    if not (mother_dir / "mother.json").is_file():
        raise SystemExit(f"mother not in this repo: {manifest['motherId']}")
    tmp = Path(tempfile.mkdtemp(prefix="axv-evidence-"))
    rendered = tmp / "challenge"
    render_challenge(Mother(mother_dir), int(manifest["seed"]), rendered)
    sub = tmp / "sub"
    target = rendered.joinpath("challenge.json")
    import json
    meta = json.loads(target.read_text())
    (sub / "patched").mkdir(parents=True)
    (sub / "poc").mkdir()
    (sub / "patched" / meta["targetFile"]).write_text(manifest["patch"])
    (sub / "poc" / "Poc.t.sol").write_text(manifest["poc"])
    res = grade(rendered, sub, seed=int(manifest["seed"]))
    return {
        "passed": res.passed,
        "pocProvesBug": res.pocProvesBug,
        "pocFailsAfterPatch": res.pocFailsAfterPatch,
        "hiddenTestsPass": res.hiddenTestsPass,
        "patchWithinLimits": res.patchWithinLimits,
        "log": res.log,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Recompute an AxVigil evidence bundle")
    p.add_argument("manifest", type=Path)
    p.add_argument("--hash-only", action="store_true", help="skip the forge re-grade")
    args = p.parse_args(argv)

    manifest, raw = load_manifest(args.manifest)
    ok = True

    cid_file = args.manifest.parent / "cid.txt"
    cid = cid_v1_raw_sha256(canonical_json(manifest))
    # The file on disk is already canonical if we wrote it. Re-hash the raw bytes too.
    cid_raw = cid_v1_raw_sha256(raw)
    print(f"cid (canonical): {cid}")
    print(f"cid (file bytes): {cid_raw}")
    if cid_file.is_file():
        recorded = cid_file.read_text().strip()
        match = recorded in (cid, cid_raw)
        print(f"cid.txt match: {match} ({recorded})")
        ok = ok and match

    recomputed = recompute_submission_hash(manifest)
    recorded_hash = manifest.get("submissionHash")
    hash_ok = recomputed == recorded_hash
    print(f"submissionHash match: {hash_ok}")
    print(f"  bundle:     {recorded_hash}")
    print(f"  recomputed: {recomputed}")
    ok = ok and hash_ok

    commit_ok = manifest.get("seedCommitment") == seed_commitment(int(manifest["seed"]))
    print(f"seedCommitment match: {commit_ok}")
    ok = ok and commit_ok

    if not args.hash_only:
        grade = _grade(manifest)
        checks = manifest.get("checks") or {}
        for key in ("passed", "pocProvesBug", "pocFailsAfterPatch", "hiddenTestsPass", "patchWithinLimits"):
            same = bool(checks.get(key)) == bool(grade[key])
            print(f"{key}: bundle={checks.get(key)} rerun={grade[key]} match={same}")
            ok = ok and same
        if not ok:
            print(grade["log"])

    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
