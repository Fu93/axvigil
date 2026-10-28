"""Thin bridge to the verifier package: writes a submission to a temp dir and grades it."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from .config import Settings


def _ensure_verifier_on_path(verifier_dir: Path) -> None:
    p = str(verifier_dir)
    if p not in sys.path:
        sys.path.insert(0, p)


def grade_submission(
    settings: Settings, *, challenge_id: str, seed: int, target_file: str,
    patch: str, poc: str, solve_seconds: int | None,
):
    """Materialize {patched/<target>, poc/Poc.t.sol} and grade it. Returns a GradeResult."""
    _ensure_verifier_on_path(settings.verifier_dir)
    from verifier.grader import grade  # noqa: E402

    challenge_dir = settings.challenges_dir / challenge_id
    if not challenge_dir.is_dir():
        raise FileNotFoundError(f"unknown challenge: {challenge_id}")

    tmp = Path(tempfile.mkdtemp(prefix="axv-sub-"))
    try:
        (tmp / "patched").mkdir()
        (tmp / "poc").mkdir()
        (tmp / "patched" / target_file).write_text(patch)
        (tmp / "poc" / "Poc.t.sol").write_text(poc)
        return grade(
            challenge_dir, tmp, seed=seed, solve_seconds=solve_seconds,
            forge_bin=settings.forge_bin, solc=settings.solc_bin,
            timeout_s=settings.grade_timeout_s,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def challenge_meta(settings: Settings, challenge_id: str) -> dict:
    import json
    path = settings.challenges_dir / challenge_id / "challenge.json"
    return json.loads(path.read_text())


def list_challenges(settings: Settings) -> list[dict]:
    import json
    out = []
    if not settings.challenges_dir.is_dir():
        return out
    for d in sorted(settings.challenges_dir.iterdir()):
        meta_path = d / "challenge.json"
        if meta_path.is_file():
            m = json.loads(meta_path.read_text())
            out.append({
                "challengeId": m["challengeId"], "vulnClass": m["vulnClass"],
                "difficulty": m["difficulty"], "title": m.get("title", ""),
                "summary": m.get("summary", ""),
            })
    return out
