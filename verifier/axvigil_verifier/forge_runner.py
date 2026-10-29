"""Run a single Foundry test file inside a throwaway, offline project.

The grader never trusts submitted code, so every run happens in a fresh temp
directory with the network disabled (``FOUNDRY_OFFLINE=true``), a wall-clock
timeout, and a fixed fuzz seed for reproducibility. forge-std and OpenZeppelin
are remapped to the repo's already-vendored copies (no download).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .toolchain import effective_nproc_limit, uid_thread_count

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover - Windows
    resource = None


def _rlimit_preexec(cpu_s: int, mem_bytes: int, fsize_bytes: int, nproc: int | None):
    """Build a preexec_fn that caps the child's CPU, address space, output file
    size and process count. Defence in depth around untrusted submitted code,
    on top of the wall-clock timeout, ffi=false and no network.

    `nproc` is a UID-wide thread cap. None leaves it unset. Callers must pass a
    value at or above the user's current thread count; a low absolute cap makes
    forge's tokio runtime die with EAGAIN ("can't spawn worker thread").
    """
    if resource is None:
        return None

    def _apply():  # runs in the child between fork and exec
        def _set(res, soft):
            try:
                hard = resource.getrlimit(res)[1]
                cap = soft if hard == resource.RLIM_INFINITY else min(soft, hard)
                resource.setrlimit(res, (cap, hard))
            except (ValueError, OSError):
                pass
        _set(resource.RLIMIT_CPU, cpu_s)
        _set(resource.RLIMIT_FSIZE, fsize_bytes)
        if nproc is not None and hasattr(resource, "RLIMIT_NPROC"):
            _set(resource.RLIMIT_NPROC, nproc)
        # Address space: forge/solc are memory-hungry, so keep this generous and
        # skip it if it would be too low to run the toolchain at all.
        if mem_bytes >= 1 << 30:
            _set(resource.RLIMIT_AS, mem_bytes)

    return _apply

REPO_CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
DEFAULT_FORGE_STD = REPO_CONTRACTS / "lib" / "forge-std" / "src"
DEFAULT_OZ = REPO_CONTRACTS / "lib" / "openzeppelin-contracts" / "contracts"


@dataclass
class RunResult:
    compiled: bool
    timed_out: bool
    tests: dict[str, bool] = field(default_factory=dict)  # "testName()" -> passed
    raw: str = ""

    @property
    def all_passed(self) -> bool:
        return self.compiled and not self.timed_out and bool(self.tests) and all(self.tests.values())

    @property
    def any_passed(self) -> bool:
        return self.compiled and not self.timed_out and any(self.tests.values())


def _foundry_toml(forge_std: Path, oz: Path, solc: str | None) -> str:
    lines = [
        "[profile.default]",
        'src = "src"',
        'test = "test"',
        'out = "out"',
        'libs = []',
        'solc_version = "0.8.28"',
        "optimizer = true",
        "optimizer_runs = 200",
        "ffi = false",
        "fs_permissions = []",
        "remappings = [",
        f'  "forge-std/={forge_std}/",',
        f'  "@openzeppelin/contracts/={oz}/",',
        "]",
        "[fuzz]",
        "runs = 48",
    ]
    if solc:
        lines.append(f'# solc pinned via --use {solc}')
    return "\n".join(lines) + "\n"


def run_test(
    *,
    sources: dict[str, str],
    tests: dict[str, str],
    match_path: str,
    forge_bin: str = "forge",
    solc: str | None = None,
    forge_std: Path = DEFAULT_FORGE_STD,
    oz: Path = DEFAULT_OZ,
    timeout_s: int = 120,
    fuzz_seed: int = 0xA11CE,
    mem_limit_bytes: int = 4 << 30,
    fsize_limit_bytes: int = 256 << 20,
    nproc_limit: int = int(os.environ.get("AXVIGIL_NPROC_LIMIT", "4096")),
) -> RunResult:
    """Compile `sources`+`tests` and run forge tests matching `match_path`.

    sources/tests: {relative filename -> solidity text}. match_path is relative
    to the temp project root (e.g. "test/Poc.t.sol"). Untrusted code runs with
    ffi disabled, no network, a wall-clock timeout and POSIX resource limits.
    """
    workdir = Path(tempfile.mkdtemp(prefix="axv-verify-"))
    try:
        (workdir / "src").mkdir()
        (workdir / "test").mkdir()
        (workdir / "foundry.toml").write_text(_foundry_toml(forge_std, oz, solc))
        for name, text in sources.items():
            dest = workdir / "src" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        for name, text in tests.items():
            dest = workdir / "test" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)

        cmd = [
            forge_bin, "test",
            "--json",
            "--match-path", match_path,
            "--fuzz-seed", str(fuzz_seed),
        ]
        if solc:
            cmd += ["--use", solc]

        env = dict(os.environ)
        env["FOUNDRY_OFFLINE"] = "true"
        env["FOUNDRY_FUZZ_SEED"] = str(fuzz_seed)

        # CPU limit a little above the wall limit so the timeout fires first in
        # the normal case and the CPU cap only catches a runaway process.
        # The nproc cap is raised to the live UID thread count so it cannot sit
        # below the threads this user already has.
        nproc_soft = effective_nproc_limit(nproc_limit, uid_thread_count())
        preexec = _rlimit_preexec(
            cpu_s=timeout_s + 10, mem_bytes=mem_limit_bytes,
            fsize_bytes=fsize_limit_bytes, nproc=nproc_soft,
        )
        # start_new_session puts forge in its own process group so a timeout
        # can kill solc grandchildren, not only the forge parent.
        proc = subprocess.Popen(
            cmd, cwd=workdir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, preexec_fn=preexec, start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            return RunResult(compiled=False, timed_out=True, raw="timeout")

        stdout = stdout or ""
        # Keep the old attribute name used below. stderr is folded into compile failures.
        proc_stderr = stderr or ""
        tests_map = _parse_forge_json(stdout)
        # A compile failure yields no JSON test map and a non-zero exit with a
        # "Compiler run failed" / error marker on stderr or stdout.
        compiled = tests_map is not None
        if not compiled:
            return RunResult(compiled=False, timed_out=False, raw=proc_stderr + stdout)
        return RunResult(compiled=True, timed_out=False, tests=tests_map, raw=stdout)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def solc_setup_hint(raw: str) -> str | None:
    """Explain a missing-compiler failure without echoing forge's raw output."""
    low = (raw or "").lower()
    if "solc" in low and (
        "offline mode" in low or "not installed" in low or "can't install" in low or "cannot install" in low
    ):
        return (
            "the Solidity compiler is not available yet. From the repo run "
            "`cd contracts && forge build` once while online so Foundry can download solc, "
            "then grade again. Grading itself stays offline"
        )
    return None


def first_compiler_error(raw: str) -> str | None:
    """First forge Error line, with filesystem paths removed."""
    for line in (raw or "").splitlines():
        text = line.strip()
        if text.startswith("Error"):
            text = re.sub(r"(?:[A-Za-z]:)?(?:/|\\)[^\s:]+", "<path>", text)
            return text[:200]
    return None


def compile_failure_note(raw: str, *, include_error_line: bool) -> str:
    """Suffix for a `compile failed` log line. Hidden tests omit the compiler line."""
    hint = solc_setup_hint(raw)
    if hint:
        return " — " + hint
    if not include_error_line:
        return ""
    line = first_compiler_error(raw)
    return f" — {line}" if line else ""


def environment_failure(log: str) -> bool:
    """True when grading never ran (missing forge or solc), not when a patch failed."""
    low = (log or "").lower()
    return "solidity compiler is not available" in low or "forge was not found" in low


def _parse_forge_json(stdout: str) -> dict[str, bool] | None:
    """Extract {testName: passed} from `forge test --json` output.

    Returns None if no parseable test JSON was produced (e.g. compile error).
    """
    # forge may print non-JSON lines; find the JSON object line(s).
    obj = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if obj is None:
        try:
            obj = json.loads(stdout)
        except json.JSONDecodeError:
            return None
    results: dict[str, bool] = {}
    for _suite, data in obj.items():
        tr = data.get("test_results") if isinstance(data, dict) else None
        if not isinstance(tr, dict):
            continue
        for test_name, info in tr.items():
            status = info.get("status") if isinstance(info, dict) else None
            results[test_name] = (status == "Success")
    return results if results else None
