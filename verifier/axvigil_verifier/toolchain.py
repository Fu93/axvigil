"""Locate forge and solc, and compute a process-count cap that forge can live under.

Foundry keeps its Solidity compiler in svm (`~/.svm/<version>/solc-<version>`),
not necessarily on `PATH`. Tests and the grader treat that copy as solc.
`RLIMIT_NPROC` is a per-user thread cap, so an absolute limit below the user's
current thread count makes forge fail with "can't spawn worker thread".
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

SOLC_VERSION = "0.8.28"
NPROC_HEADROOM = 512


def forge_executable() -> str | None:
    env = os.environ.get("FORGE")
    if env:
        return env
    return shutil.which("forge")


def _is_exec(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def discover_solc(version: str = SOLC_VERSION) -> str | None:
    """Return a solc binary, preferring SOLC, then PATH, then Foundry's svm cache."""
    env = os.environ.get("SOLC")
    if env:
        return env
    for name in ("solc", f"solc-{version}"):
        found = shutil.which(name)
        if found:
            return found

    home = Path.home()
    candidates = [
        home / ".svm" / version / f"solc-{version}",
        home / ".svm" / version / "solc",
        home / ".foundry" / "solc" / f"solc-{version}",
        home / ".foundry" / "cache" / "solc" / version / f"solc-{version}",
        Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")) / "svm" / version / f"solc-{version}",
    ]
    for path in candidates:
        if _is_exec(path):
            return str(path)
    # svm sometimes nests the binary one directory down.
    roots = [home / ".svm", home / ".foundry"]
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        roots.append(Path(xdg) / "svm")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob(f"**/{'solc-' + version}"):
            if _is_exec(path):
                return str(path)
    return None


def effective_nproc_limit(
    requested: int, live_threads: int, headroom: int = NPROC_HEADROOM,
) -> int | None:
    """Soft RLIMIT_NPROC to apply, or None to leave the limit unset.

    `requested <= 0` disables the cap (AXVIGIL_NPROC_LIMIT=0). Otherwise the cap
    is at least the user's current thread count plus `headroom`, so forge can
    spawn its worker threads on a busy machine, and still bounded.
    """
    if requested <= 0:
        return None
    return max(int(requested), int(live_threads) + int(headroom))


def uid_thread_count() -> int:
    """Threads owned by the current real uid, which is what RLIMIT_NPROC counts."""
    try:
        uid = os.getuid()
    except AttributeError:  # pragma: no cover - non-POSIX
        return 0
    total = 0
    proc = Path("/proc")
    if not proc.is_dir():
        return 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / "status").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        owner = None
        threads = None
        for line in text.splitlines():
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    owner = int(parts[1])
            elif line.startswith("Threads:"):
                parts = line.split()
                if len(parts) >= 2:
                    threads = int(parts[1])
            if owner is not None and threads is not None:
                break
        if owner == uid and threads:
            total += threads
    return total
