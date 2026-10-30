#!/usr/bin/env python3
"""Verify a real-incident mother: 20-variant verify-mother plus grader negative controls.

usage (from the repo root, forge on PATH or FORGE set):
    python3 scripts/realbank_verify.py [mothers/bridge-phantom-deposit] [count]

The reference fix and identifier pools live in variantgen (fixes.py / pools.py), so this
only drives the repo's own render + grade code. Expected results for
bridge-phantom-deposit are recorded in docs/realbank/verify_log.txt.
"""
from __future__ import annotations

import os
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

mother_dir = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "mothers" / "bridge-phantom-deposit")
count = sys.argv[2] if len(sys.argv) > 2 else "20"
rc = vg_main(["verify-mother", "--mother", mother_dir, "--count", count])

# Negative controls on seed 0 (bridge-phantom-deposit specific).
forge = os.environ.get("FORGE") or shutil.which("forge")
tmp = Path(tempfile.mkdtemp(prefix="axv-realbank-neg-"))
m = Mother(Path(mother_dir))
ch = render_challenge(m, 0, tmp / "ch")
tgt = ch["targetFile"]
orig = (tmp / "ch/src" / tgt).read_text()
poc = (tmp / "ch/solution/poc/Poc.t.sol").read_text()


def sub(name: str, patched_src: str, expect_pass: bool, label: str = "") -> bool:
    d = tmp / name
    (d / "patched").mkdir(parents=True)
    (d / "poc").mkdir()
    (d / "patched" / tgt).write_text(patched_src)
    (d / "poc/Poc.t.sol").write_text(poc)
    r = grade(tmp / "ch", d, seed=0, forge_bin=forge)
    ok = r.passed == expect_pass
    tag = label or ("ok" if ok else "UNEXPECTED")
    print(f"[{name}] passed={r.passed} proves={r.pocProvesBug} failsAfter={r.pocFailsAfterPatch} "
          f"hidden={r.hiddenTestsPass} limits={r.patchWithinLimits}  expect={expect_pass}  {tag}")
    return ok


results = []
results.append(sub("noop_patch", orig, expect_pass=False))
eager = orig.replace("(data.length == 0 || abi.decode(data, (bool)))",
                     "(data.length == 32 && abi.decode(data, (bool)))")
results.append(sub("overeager_fix_requires_bool", eager, expect_pass=False))
gut = orig.replace('require(amount > 0, "zero amount");\n        ',
                   'require(false, "disabled");\n        ', 1)
results.append(sub("gutted_deposit", gut, expect_pass=False))

# Instance patches that only neutralize the address(0) case must BOTH be rejected:
# the class is "a low-level call succeeds on any codeless address", so any non-zero
# codeless token still phantom-deposits. The codeless-token hidden test rejects both.
#   (1) guard the pull with token != address(0)
zero_only = orig.replace('require(amount > 0, "zero amount");\n',
                         'require(amount > 0, "zero amount");\n        require(token != address(0), "zero token");\n', 1)
results.append(sub("instance_zero_address_guard", zero_only, expect_pass=False))
#   (2) unlist address(0). Removes the one reachable instance but leaves every other
#       codeless token exploitable, so it is an instance patch, not the class fix.
listed = [ln for ln in orig.splitlines() if "[address(0)] = true;" in ln][0]
results.append(sub("instance_unlist_zero", orig.replace(listed + "\n", ""), expect_pass=False))

shutil.rmtree(tmp, ignore_errors=True)
sys.exit(rc or (0 if all(results) else 1))
