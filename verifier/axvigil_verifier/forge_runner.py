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

from .storage_guard import StorageSlot, extract_storage_layout_from_project
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
    reasons: dict[str, str | None] = field(default_factory=dict)  # "testName()" -> failure reason
    gas_used: dict[str, int | None] = field(default_factory=dict)  # "testName()" -> gas units
    storage_layout: list[StorageSlot] | None = None
    raw: str = ""

    @property
    def all_passed(self) -> bool:
        return self.compiled and not self.timed_out and bool(self.tests) and all(self.tests.values())

    @property
    def any_passed(self) -> bool:
        return self.compiled and not self.timed_out and any(self.tests.values())


def _foundry_toml(
    forge_std: Path,
    oz: Path,
    solc: str | None,
    *,
    fuzz_runs: int = 48,
    invariant_runs: int = 32,
    invariant_depth: int = 15,
) -> str:
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
        f"runs = {int(fuzz_runs)}",
        "max_test_rejects = 65536",
        "[invariant]",
        f"runs = {int(invariant_runs)}",
        f"depth = {int(invariant_depth)}",
        "fail_on_revert = false",
    ]
    if solc:
        lines.append(f'# solc pinned via --use {solc}')
    return "\n".join(lines) + "\n"


def forge_test_command(
    forge_bin: str, match_path: str, solc: str | None, fuzz_seed: int,
) -> list[str]:
    """forge test argv. A missing solc path is not an error: omit ``--use`` and
    forge runs the compiler from ``solc_version`` (its own svm copy)."""
    cmd = [
        forge_bin, "test",
        "--json",
        "--match-path", match_path,
        "--fuzz-seed", str(fuzz_seed),
    ]
    if solc:
        cmd += ["--use", solc]
    return cmd


def _sandbox_mode() -> str:
    mode = os.environ.get("AXVIGIL_SANDBOX", "subprocess").strip().lower()
    if mode not in ("subprocess", "docker"):
        raise ValueError("AXVIGIL_SANDBOX must be docker or subprocess")
    return mode


def docker_run_command(inputs: Path, match_path: str, fuzz_seed: int) -> list[str]:
    """Locked-down `docker run` for one forge test.

    The image root is read-only, the network is off, the process is uid 1000,
    and the writable workdir is a tmpfs. The host project is mounted read-only.
    """
    image = os.environ.get("AXVIGIL_DOCKER_IMAGE", "axvigil-sandbox:1.8.7")
    memory = os.environ.get("AXVIGIL_DOCKER_MEMORY", "1g")
    cpus = os.environ.get("AXVIGIL_DOCKER_CPUS", "1")
    pids = os.environ.get("AXVIGIL_DOCKER_PIDS", "128")
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--read-only",
        "--user", "1000:1000",
        "--memory", memory,
        "--cpus", cpus,
        "--pids-limit", pids,
        "--tmpfs", "/work:rw,exec,size=256m",
        "--tmpfs", "/tmp:rw,size=64m",
        "-v", f"{inputs}:/inputs:ro",
        # The generated foundry.toml uses absolute remappings to the vendored
        # libraries. Mount those exact host paths read-only so Docker mode does
        # not silently fall back to an unresolvable host-only path.
        "-v", f"{DEFAULT_FORGE_STD}:{DEFAULT_FORGE_STD}:ro",
        "-v", f"{DEFAULT_OZ}:{DEFAULT_OZ}:ro",
        "-e", "FOUNDRY_OFFLINE=true",
        image,
        "--match-path", match_path,
        "--fuzz-seed", str(fuzz_seed),
    ]


def _run_in_docker(workdir: Path, match_path: str, fuzz_seed: int, timeout_s: int) -> RunResult:
    cmd = docker_run_command(workdir, match_path, fuzz_seed)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(compiled=False, timed_out=True, raw="timeout")
    except FileNotFoundError:
        return RunResult(compiled=False, timed_out=False, raw="docker was not found")
    stdout = proc.stdout or ""
    details = _parse_forge_json_details(stdout)
    if details is None:
        raw = (proc.stderr or "") + stdout
        if not raw.strip():
            raw = f"docker sandbox exited with status {proc.returncode} without output"
        return RunResult(compiled=False, timed_out=False, raw=raw)
    tests_map, reasons_map, gas_map = details
    return RunResult(
        compiled=True,
        timed_out=False,
        tests=tests_map,
        reasons=reasons_map,
        gas_used=gas_map,
        raw=stdout,
    )


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
    fuzz_runs: int = 48,
    invariant_runs: int = 32,
    invariant_depth: int = 15,
    mem_limit_bytes: int = 4 << 30,
    fsize_limit_bytes: int = 256 << 20,
    nproc_limit: int = int(os.environ.get("AXVIGIL_NPROC_LIMIT", "4096")),
    inspect_contract: str | None = None,
) -> RunResult:
    """Compile `sources`+`tests` and run forge tests matching `match_path`.

    sources/tests: {relative filename -> solidity text}. match_path is relative
    to the temp project root (e.g. "test/Poc.t.sol"). Untrusted code runs with
    ffi disabled, no network, a wall-clock timeout and POSIX resource limits.
    """
    workdir = Path(tempfile.mkdtemp(prefix="axv-verify-"))
    try:
        # Docker runs as uid 1000, while mkdtemp defaults to 0700 for the host
        # user. Make only the directory traversable; the mounted input remains
        # read-only and generated files retain normal non-writable-to-container
        # ownership semantics.
        workdir.chmod(0o755)
        (workdir / "src").mkdir()
        (workdir / "test").mkdir()
        (workdir / "foundry.toml").write_text(_foundry_toml(
            forge_std, oz, solc,
            fuzz_runs=fuzz_runs,
            invariant_runs=invariant_runs,
            invariant_depth=invariant_depth,
        ))
        for name, text in sources.items():
            dest = workdir / "src" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        for name, text in tests.items():
            dest = workdir / "test" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)

        if _sandbox_mode() == "docker":
            return _run_in_docker(workdir, match_path, fuzz_seed, timeout_s)

        cmd = forge_test_command(forge_bin, match_path, solc, fuzz_seed)

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
        details = _parse_forge_json_details(stdout)
        compiled = details is not None
        if not compiled:
            return RunResult(compiled=False, timed_out=False, raw=proc_stderr + stdout)
        tests_map, reasons_map, gas_map = details
        storage_layout: list[StorageSlot] | None = None
        if inspect_contract:
            storage_layout = extract_storage_layout_from_project(
                forge_bin, workdir, inspect_contract, solc=solc, timeout_s=min(timeout_s, 30)
            )
        return RunResult(
            compiled=True,
            timed_out=False,
            tests=tests_map,
            reasons=reasons_map,
            gas_used=gas_map,
            storage_layout=storage_layout,
            raw=stdout,
        )
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
    """First forge compiler error line, with filesystem paths removed."""
    fallback: str | None = None
    for line in (raw or "").splitlines():
        text = line.strip()
        if re.match(r"(?:error|fatal)\b", text, re.IGNORECASE):
            text = re.sub(r"(?:[A-Za-z]:)?(?:/|\\)[^\s:]+", "<path>", text)
            return text[:200]
        if fallback is None and re.search(r"(?:error|failed|denied|permission)", text, re.IGNORECASE):
            fallback = text
    if fallback:
        fallback = re.sub(r"(?:[A-Za-z]:)?(?:/|\\)[^\s:]+", "<path>", fallback)
        return fallback[:200]
    return None


def compile_failure_note(raw: str, *, include_error_line: bool) -> str:
    """Suffix for a `compile failed` log line. Hidden tests omit the compiler line."""
    hint = solc_setup_hint(raw)
    if hint:
        return " — " + hint
    if not include_error_line:
        return ""
    line = first_compiler_error(raw)
    if line is None:
        lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
        line = lines[-1][:200] if lines else None
    return f" — {line}" if line else ""


def environment_failure(log: str) -> bool:
    """True when grading never ran (missing forge or solc), not when a patch failed."""
    low = (log or "").lower()
    return "solidity compiler is not available" in low or "forge was not found" in low


def _parse_forge_json_details(
    stdout: str,
) -> tuple[dict[str, bool], dict[str, str | None], dict[str, int | None]] | None:
    """Extract (tests, reasons, gas_used) from `forge test --json` output.

    Returns None if no parseable test JSON was produced (e.g. compile error).
    """
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
    if not isinstance(obj, dict):
        return None

    results: dict[str, bool] = {}
    reasons: dict[str, str | None] = {}
    gas_map: dict[str, int | None] = {}

    for _suite, data in obj.items():
        tr = data.get("test_results") if isinstance(data, dict) else None
        if not isinstance(tr, dict):
            continue
        for test_name, info in tr.items():
            if not isinstance(info, dict):
                continue
            status = info.get("status")
            passed = (status == "Success")
            results[test_name] = passed
            reasons[test_name] = info.get("reason")

            kind = info.get("kind")
            gas: int | None = None
            if isinstance(kind, dict):
                if "Unit" in kind and isinstance(kind["Unit"], dict):
                    gas = kind["Unit"].get("gas")
                elif "Fuzz" in kind and isinstance(kind["Fuzz"], dict):
                    gas = kind["Fuzz"].get("mean_gas")
            elif isinstance(info.get("gas"), int):
                gas = info["gas"]
            gas_map[test_name] = gas

    if not results:
        return None
    return results, reasons, gas_map


def _parse_forge_json(stdout: str) -> dict[str, bool] | None:
    """Extract {testName: passed} from `forge test --json` output.

    Returns None if no parseable test JSON was produced (e.g. compile error).
    """
    details = _parse_forge_json_details(stdout)
    return details[0] if details is not None else None
