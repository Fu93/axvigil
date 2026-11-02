#!/usr/bin/env python3
"""One local validator HTTP process.

    VALIDATOR_KEY=0x... PORT=9101 CHAIN_ID=97 \\
    VERIFYING_CONTRACT=0x... \\
    python3 scripts/run_validators.py

POST /sign  JSON {"manifest": {...}, "auth": {...}}
The process re-grades the bundle with the repo grader when RECHECK=1 (default).
Set RECHECK=0 only for a wiring demo that skips forge; a real mint must leave it on.

Three processes: scripts/run_three_validators.sh
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "verifier"))
sys.path.insert(0, str(ROOT / "variantgen"))

from axvigil_backend.validators import GradeRefused, LocalValidator  # noqa: E402


def _live_grade(manifest: dict) -> dict:
    from axvigil_verifier.grader import grade
    from variantgen.render import Mother, render_challenge
    import tempfile

    mother_dir = ROOT / "mothers" / manifest["motherId"]
    tmp = Path(tempfile.mkdtemp(prefix="axv-validator-"))
    rendered = tmp / "challenge"
    render_challenge(Mother(mother_dir), int(manifest["seed"]), rendered)
    sub = tmp / "sub"
    meta = json.loads((rendered / "challenge.json").read_text())
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
        "invariantsHold": res.invariantsHold,
        "invariantProfile": {
            "fuzzSeed": res.invariantFuzzSeed,
            "fuzzRuns": res.invariantFuzzRuns,
            "invariantRuns": res.invariantRuns,
            "invariantDepth": res.invariantDepth,
            "applied": res.invariantApplied,
        },
    }


def main() -> None:
    key = os.environ["VALIDATOR_KEY"]
    port = int(os.environ.get("PORT", "9101"))
    chain_id = int(os.environ.get("CHAIN_ID", "97"))
    verifying = os.environ["VERIFYING_CONTRACT"]
    recheck = os.environ.get("RECHECK", "1") != "0"
    validator = LocalValidator(key, chain_id, verifying)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path != "/sign":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            grade_fn = _live_grade if recheck else (lambda _m: {"passed": True})
            try:
                out = validator.consider(body["manifest"], body["auth"], grade_fn)
                raw = json.dumps(out).encode("utf-8")
                self.send_response(200)
            except GradeRefused as exc:
                raw = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s\n" % (fmt % args))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
