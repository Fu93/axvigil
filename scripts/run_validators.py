#!/usr/bin/env python3
"""One local validator HTTP process.

    VALIDATOR_KEY=0x... PORT=9101 CHAIN_ID=97 \\
    VERIFYING_CONTRACT=0x... \\
    python3 scripts/run_validators.py

POST /sign  JSON {"manifest": {...}, "auth": {...}}
POST /challenge  JSON {"tokenId": 1, "manifest": {...}}
The process re-grades the bundle with the repo grader when RECHECK=1 (default).
Set RECHECK=0 only for a wiring demo that skips forge; a real mint must leave it on.
CHALLENGE_CONTRACT is the challenge book address (EIP-712 verifying contract for
ChallengeVerdict). AXV_ALLOW_TEST_GRADE=1 honours manifest.axvTestGradePassed;
leave it unset on a production validator.

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

from axvigil_backend.evidence import canonical_json  # noqa: E402
from axvigil_backend.validators import GradeRefused, LocalValidator, challenge_grade  # noqa: E402


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
    out = {
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
    cex = manifest.get("counterexample")
    if out["passed"] and isinstance(cex, str) and "function test" in cex:
        if _counterexample_hits(manifest, rendered, meta):
            out["passed"] = False
            out["reason"] = "counterexample"
            out["counterexampleHit"] = True
    return out


def _counterexample_hits(manifest: dict, rendered: Path, meta: dict) -> bool:
    """A counterexample Foundry test that passes against the patch still reaches the bug."""
    from axvigil_verifier.forge_runner import run_test

    sources = {p.name: p.read_text() for p in sorted((rendered / "src").glob("*.sol"))}
    target = meta["targetFile"]
    sources[target] = manifest["patch"]
    result = run_test(
        sources=sources,
        tests={"Counterexample.t.sol": manifest["counterexample"]},
        match_path="test/Counterexample.t.sol",
        timeout_s=120,
    )
    return bool(result.any_passed)


def _grade(manifest: dict, *, recheck: bool, allow_test: bool) -> dict:
    return challenge_grade(manifest, _live_grade, recheck=recheck, allow_test_grade=allow_test)


def main() -> None:
    key = os.environ["VALIDATOR_KEY"]
    port = int(os.environ.get("PORT", "9101"))
    chain_id = int(os.environ.get("CHAIN_ID", "97"))
    verifying = os.environ["VERIFYING_CONTRACT"]
    recheck = os.environ.get("RECHECK", "1") != "0"
    allow_test = os.environ.get("AXV_ALLOW_TEST_GRADE") == "1"
    challenge_contract = os.environ.get("CHALLENGE_CONTRACT", "")
    validator = LocalValidator(key, chain_id, verifying, challenge_contract)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            if length > 262144:
                self.send_error(413)
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            try:
                if self.path == "/sign":
                    out = validator.consider(
                        body["manifest"], body["auth"], lambda m: _grade(m, recheck=recheck, allow_test=allow_test)
                    )
                elif self.path == "/challenge":
                    manifest = body["manifest"]
                    evidence = canonical_json(manifest)
                    out = validator.consider_challenge(
                        int(body["tokenId"]),
                        manifest,
                        lambda m: _grade(m, recheck=recheck, allow_test=allow_test),
                        evidence,
                    )
                else:
                    self.send_error(404)
                    return
                self._json(200, out)
            except GradeRefused as exc:
                self._json(403, {"error": str(exc)})
            except (KeyError, TypeError, ValueError) as exc:
                self._json(400, {"error": str(exc)})

        def _json(self, status: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s\n" % (fmt % args))

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
