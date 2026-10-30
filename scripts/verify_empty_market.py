#!/usr/bin/env python3
"""Verify the empty-market-inflation mother: 20-variant verify-mother plus grader
negative controls (bad patches that must be rejected).

usage (from the repo root, forge on PATH or FORGE set):
    python3 scripts/verify_empty_market.py [count]

The reference fix and identifier pools live in variantgen (fixes.py / pools.py); this
drives the repo's own render + grade code. Expected results are recorded in
docs/realbank/verify_empty_market_log.txt.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "variantgen"))
sys.path.insert(0, str(REPO / "verifier"))

from variantgen.__main__ import main as vg_main  # noqa: E402
from variantgen.render import Mother, render_challenge  # noqa: E402
from axvigil_verifier.grader import grade  # noqa: E402

mother_dir = str(REPO / "mothers" / "empty-market-inflation")
count = sys.argv[1] if len(sys.argv) > 1 else "20"
rc = vg_main(["verify-mother", "--mother", mother_dir, "--count", count])

forge = os.environ.get("FORGE") or shutil.which("forge")
tmp = Path(tempfile.mkdtemp(prefix="axv-emi-neg-"))
m = Mother(Path(mother_dir))
ch = render_challenge(m, 0, tmp / "ch")
tgt = ch["targetFile"]
orig = (tmp / "ch/src" / tgt).read_text()
poc = (tmp / "ch/solution/poc/Poc.t.sol").read_text()


def sub(name: str, patched_src: str, expect_pass: bool) -> bool:
    d = tmp / name
    (d / "patched").mkdir(parents=True)
    (d / "poc").mkdir()
    (d / "patched" / tgt).write_text(patched_src)
    (d / "poc/Poc.t.sol").write_text(poc)
    r = grade(tmp / "ch", d, seed=0, forge_bin=forge)
    ok = r.passed == expect_pass
    print(f"[{name}] passed={r.passed} proves={r.pocProvesBug} failsAfter={r.pocFailsAfterPatch} "
          f"hidden={r.hiddenTestsPass} limits={r.patchWithinLimits}  expect={expect_pass}  "
          f"{'ok' if ok else 'UNEXPECTED'}")
    return ok


results = []
# no-op: the untouched vulnerable source must fail (PoC still drains it).
results.append(sub("noop_patch", orig, expect_pass=False))

# require(shares > 0): a partial patch that only blocks zero-share deposits. It does not
# make the pool donation-resistant, so a real deposit after a donation is still skewed and
# lost — rejected by the differential and the donation-invariant hidden test.
shares_line = re.search(r"\n([ \t]*shares = [^\n]*\n)", orig)
if shares_line:
    guarded = orig[: shares_line.end(1)] + \
        re.match(r"[ \t]*", shares_line.group(1)).group(0) + 'require(shares > 0, "zero shares");\n' + \
        orig[shares_line.end(1):]
    results.append(sub("instance_require_shares_gt0", guarded, expect_pass=False))
else:
    print("[instance_require_shares_gt0] SKIP: could not locate the shares assignment")
    results.append(False)

# gutted: disable the deposit entirely. Breaks functional behaviour -> rejected.
gut = orig.replace('require(assets > 0, "zero assets");\n',
                   'require(assets > 0, "zero assets");\n        require(false, "disabled");\n', 1)
results.append(sub("gutted_deposit", gut, expect_pass=False))

shutil.rmtree(tmp, ignore_errors=True)
sys.exit(rc or (0 if all(results) else 1))
