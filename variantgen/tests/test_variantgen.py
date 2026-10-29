"""Variant generator tests.

The fast tests (no forge) check determinism, uniqueness and that the reference
fix is a small, interface-preserving diff. The forge test grades a couple of
rendered variants per mother end-to-end and fails if forge is not installed.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pytest

from variantgen.fingerprint import fingerprint
from variantgen.render import Mother, build_context, render_src, render_challenge
from variantgen.__main__ import _unique_variants

REPO_ROOT = Path(__file__).resolve().parents[2]
MOTHERS = [p for p in sorted((REPO_ROOT / "mothers").iterdir()) if (p / "mother.json").is_file()]

import sys
sys.path.insert(0, str(REPO_ROOT / "verifier"))
from axvigil_verifier.toolchain import discover_solc, forge_executable  # noqa: E402

_forge = forge_executable()
_solc = discover_solc()


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_render_is_deterministic(mdir):
    m = Mother(mdir)
    a = render_src(m, build_context(m, 123))
    b = render_src(m, build_context(m, 123))
    assert a == b, "same seed must render identically"


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_twenty_unique_variants(mdir):
    m = Mother(mdir)
    fps = [fp for _seed, fp in _unique_variants(m, 20)]
    assert len(fps) == 20
    assert len(set(fps)) == 20, "fingerprints must be distinct"


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_reference_fix_is_small_and_preserves_interface(mdir, tmp_path):
    m = Mother(mdir)
    ch = render_challenge(m, 5, tmp_path)
    target = ch["targetFile"]
    src = (tmp_path / "src" / target).read_text()
    patched = (tmp_path / "solution" / "patched" / target).read_text()

    assert src != patched, "the fix must change something"
    # interface preserved: contract + required functions still present
    assert re.search(rf"\bcontract\s+{re.escape(ch['contractName'])}\b", patched)
    for fn in ch["requiredFunctions"]:
        assert re.search(rf"\bfunction\s+{re.escape(fn)}\b", patched), f"{fn} removed by fix"

    # changed lines within the mother's declared limit
    import difflib
    changed = sum(
        1 for ln in difflib.unified_diff(src.splitlines(), patched.splitlines(), lineterm="", n=0)
        if (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---"))
    )
    assert changed <= ch["limits"]["maxChangedLines"], f"fix too large: {changed} lines"


def test_identifiers_are_renamed_across_seeds(tmp_path):
    # Different seeds should choose different contract names, proving renaming varies.
    m = Mother(MOTHERS[0])
    names = {render_challenge(m, s, tmp_path / f"s{s}")["contractName"] for s in range(8)}
    assert len(names) >= 3, "contract name should vary across seeds"


@pytest.mark.parametrize("mdir", MOTHERS, ids=lambda p: p.name)
def test_rendered_variants_grade_as_solved(mdir, tmp_path):
    if not _forge:
        pytest.fail("forge is required. Install foundry; solc is discovered from svm if needed.")
    import sys
    sys.path.insert(0, str(REPO_ROOT / "verifier"))
    from axvigil_verifier.grader import grade

    m = Mother(mdir)
    seeds = [s for s, _ in _unique_variants(m, 2)]
    for seed in seeds:
        vdir = tmp_path / f"{m.mother_id}-{seed}"
        render_challenge(m, seed, vdir)
        res = grade(vdir, vdir / "solution", seed=seed, forge_bin=_forge, solc=_solc, timeout_s=120)
        assert res.passed, f"{m.mother_id} seed {seed}: {res.log}"
