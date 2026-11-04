"""Grade one submission against one challenge.

The judgement is five independent, deterministic checks:

  pocProvesBug        the submitted PoC *passes* against the ORIGINAL contract
                      (it genuinely triggers the vulnerability)
  pocFailsAfterPatch  the same PoC *fails* against the PATCHED contract
                      (the patch actually closes the hole the PoC used)
  hiddenTestsPass     the hidden functional tests pass against the PATCHED
                      contract (the patch did not break intended behaviour)
  patchWithinLimits   the patch is a real fix, not a rewrite or a gutting:
                      bounded changed lines / bytes, and the target contract
                      and its public interface still exist
  invariantsHold      the mother's Foundry fuzz and invariant tests pass on
                      the PATCHED contract, at the pinned seed / runs / depth.
                      Challenges with no invariant suite record the check as
                      not applied and do not fail the grade for its absence.

passed = all five (the fifth is vacuously true only when the challenge has
no suite). A patch that deletes the function the PoC calls cannot win:
it fails patchWithinLimits (interface removed) or hiddenTestsPass.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .forge_runner import compile_failure_note, run_test, RunResult
from .gas_guard import check_poc_failure_is_valid_remediation
from .invariant_profile import (
    FUZZ_RUNS,
    FUZZ_SEED,
    INVARIANT_DEPTH,
    INVARIANT_RUNS,
    profile as invariant_profile,
)
from .keccak import submission_hash
from .model import GradeResult
from .storage_guard import (
    extract_storage_layout_from_project,
    parse_storage_layout_json,
    verify_storage_layout_preservation,
)

# Shown when hidden tests fail. Both failure modes are named, and neither the
# hidden tests nor the intended fix are. A retry must not be told to shrink the
# patch: an incomplete class fix fails these tests the same way a rewrite does.
HIDDEN_FAIL_HINT = (
    "hidden tests failed: either intended behaviour changed, or the fix does not "
    "fully cover the vulnerability class (consider other inputs/edge cases that "
    "reach the same bug)"
)

INVARIANT_FAIL_HINT = (
    "fuzz or invariant tests failed: the patch breaks a property the unit tests "
    "did not cover (accounting, access, or replay) under other inputs"
)


class ChallengeError(Exception):
    pass


def _read(p: Path) -> str:
    if not p.is_file():
        raise ChallengeError(f"missing file: {p}")
    return p.read_text()


def _load_sources(src_dir: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(src_dir.glob("*.sol"))}


def _changed_lines(a: str, b: str) -> int:
    a_lines = a.replace("\r\n", "\n").split("\n")
    b_lines = b.replace("\r\n", "\n").split("\n")
    diff = difflib.unified_diff(a_lines, b_lines, lineterm="", n=0)
    count = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def _interface_preserved(patched: str, contract_name: str, required_selectors: list[str]) -> tuple[bool, list[str]]:
    """The patched file must still declare the target contract and every
    required external/public function name (anti-gut)."""
    missing: list[str] = []
    if not re.search(rf"\bcontract\s+{re.escape(contract_name)}\b", patched):
        missing.append(f"contract {contract_name}")
    for fn in required_selectors:
        if not re.search(rf"\bfunction\s+{re.escape(fn)}\b", patched):
            missing.append(f"function {fn}")
    return (not missing, missing)


def check_poc_decoy_probes(poc_text: str) -> tuple[bool, str | None]:
    """Detect whether a submitted PoC attempts anti-cheat bypass via EVM bytecode introspection.

    A valid security PoC exercises contract functions and state invariants, not
    low-level bytecode size/hash inspections (.code.length, extcodesize, extcodehash, .codehash)
    that artificially pass or fail depending on whether bytecode changed.
    """
    suspicious_patterns = [
        (r"\.code\.length\b", "bytecode length inspection (.code.length)"),
        (r"\.code\b", "bytecode inspection (.code)"),
        (r"\bextcodesize\b", "assembly extcodesize inspection"),
        (r"\bextcodehash\b", "assembly extcodehash inspection"),
        (r"\bextcodecopy\b", "assembly extcodecopy inspection"),
        (r"\.codehash\b", "bytecode hash inspection (.codehash)"),
        (r"type\s*\([^)]+\)\.runtimeCode", "runtimeCode bytecode introspection"),
        (r"type\s*\([^)]+\)\.creationCode", "creationCode bytecode introspection"),
        (r"\bvm\.getCode\b", "cheatcode vm.getCode bytecode inspection"),
        (r"\bvm\.getDeployedCode\b", "cheatcode vm.getDeployedCode inspection"),
    ]
    for pattern, desc in suspicious_patterns:
        if re.search(pattern, poc_text, re.IGNORECASE):
            return False, f"Decoy PoC rejected: contains bytecode introspection '{desc}'"
    return True, None


def grade(
    challenge_dir: str | Path,
    submission_dir: str | Path,
    *,
    seed: int = 0,
    solve_seconds: int | None = None,
    forge_bin: str = "forge",
    solc: str | None = None,
    timeout_s: int = 120,
) -> GradeResult:
    challenge_dir = Path(challenge_dir)
    submission_dir = Path(submission_dir)

    meta = json.loads(_read(challenge_dir / "challenge.json"))
    challenge_id = meta["challengeId"]
    vuln_class = int(meta["vulnClass"])
    difficulty = int(meta["difficulty"])
    target_file = meta["targetFile"]
    contract_name = meta["contractName"]
    hidden_name = meta["hiddenTests"]
    limits = meta.get("limits", {})
    max_changed = int(limits.get("maxChangedLines", 60))
    max_bytes = int(limits.get("maxBytes", 8000))
    required_selectors = meta.get("requiredFunctions", [])

    original_sources = _load_sources(challenge_dir / "src")
    if target_file not in original_sources:
        raise ChallengeError(f"targetFile {target_file} not in challenge src/")
    hidden_test = _read(challenge_dir / "test" / hidden_name)

    patched_target = _read(submission_dir / "patched" / target_file)
    poc_files = sorted((submission_dir / "poc").glob("*.t.sol"))
    if not poc_files:
        raise ChallengeError("submission has no poc/*.t.sol")
    poc_name = poc_files[0].name
    poc_text = poc_files[0].read_text()

    patched_sources = dict(original_sources)
    patched_sources[target_file] = patched_target

    sub_hash = "0x" + submission_hash(challenge_id, seed, patched_target, poc_text).hex()

    log: list[str] = []

    def _run(
        label: str,
        sources: dict[str, str],
        tests: dict[str, str],
        match: str,
        *,
        fuzz_runs: int = 48,
        invariant_runs: int = 32,
        invariant_depth: int = 15,
        fuzz_seed: int = FUZZ_SEED,
        inspect_contract: str | None = None,
    ) -> RunResult:
        try:
            r = run_test(
                sources=sources, tests=tests, match_path=match,
                forge_bin=forge_bin, solc=solc, timeout_s=timeout_s,
                fuzz_seed=fuzz_seed, fuzz_runs=fuzz_runs,
                invariant_runs=invariant_runs, invariant_depth=invariant_depth,
                inspect_contract=inspect_contract,
            )
        except FileNotFoundError:
            log.append(
                f"{label}: forge was not found on PATH. Install Foundry "
                "(https://book.getfoundry.sh/getting-started/installation) and retry."
            )
            return RunResult(compiled=False, timed_out=False, raw="forge was not found")
        if r.timed_out:
            log.append(f"{label}: TIMEOUT after {timeout_s}s")
        elif not r.compiled:
            # Hidden and invariant compiler output can quote that suite. Keep it generic.
            # A missing solc is named for every label; it is not a test name.
            quiet = label in ("hiddenTestsPass", "invariantsHold")
            note = compile_failure_note(r.raw, include_error_line=not quiet)
            log.append(f"{label}: compile failed{note}")
        elif label == "hiddenTestsPass":
            # Hidden test names are the challenge's answer key. The agent sees
            # this log on retry, so report only the counts, plus a hint that the
            # patch may have changed behaviour or left the bug class only partly closed.
            passed_n = sum(r.tests.values())
            total_n = len(r.tests)
            line = f"{label}: {passed_n}/{total_n} tests passed"
            if passed_n != total_n:
                line += ". " + HIDDEN_FAIL_HINT
            log.append(line)
        elif label == "invariantsHold":
            passed_n = sum(r.tests.values())
            total_n = len(r.tests)
            line = (
                f"{label}: {passed_n}/{total_n} tests passed "
                f"seed={fuzz_seed} fuzzRuns={fuzz_runs} "
                f"invariantRuns={invariant_runs} depth={invariant_depth}"
            )
            if passed_n != total_n:
                line += ". " + INVARIANT_FAIL_HINT
            log.append(line)
        else:
            log.append(f"{label}: {sum(r.tests.values())}/{len(r.tests)} tests passed {r.tests}")
        return r

    # Check for decoy PoC bytecode probing anti-cheat bypass
    poc_decoy_ok, decoy_err = check_poc_decoy_probes(poc_text)
    if not poc_decoy_ok:
        log.append(f"pocProvesBug: {decoy_err}")
        poc_proves_bug = False
        r1 = RunResult(compiled=True, timed_out=False, tests={}, raw=decoy_err or "")
    else:
        # 1. PoC proves the bug on the ORIGINAL contract.
        r1 = _run("pocProvesBug", original_sources, {poc_name: poc_text}, f"test/{poc_name}", inspect_contract=contract_name)
        poc_proves_bug = r1.all_passed

    # 2. The same PoC FAILS on the PATCHED contract (and the patch compiles).
    r2 = _run("pocFailsAfterPatch", patched_sources, {poc_name: poc_text}, f"test/{poc_name}", inspect_contract=contract_name)
    # Every PoC test must fail after the patch. "At least one failed" let a
    # submission keep the exploit working and add a decoy test that the patch
    # breaks, which still counted as closing the bug.
    poc_fails_after_patch = (
        r2.compiled and not r2.timed_out and bool(r2.tests) and not r2.any_passed
    )
    if poc_fails_after_patch:
        # Check if the failure was merely a broken harness/setup rather than exploit neutralization
        setup_reverted = any(
            reason and "setup() reverted" in reason.lower()
            for reason in r2.reasons.values()
        ) or ("setup() reverted" in r2.raw.lower())
        if setup_reverted:
            poc_fails_after_patch = False
            log.append("pocFailsAfterPatch: setUp() reverted in test harness")
        else:
            valid_remediation, oog_err = check_poc_failure_is_valid_remediation(r2.reasons)
            if not valid_remediation:
                poc_fails_after_patch = False
                log.append(f"pocFailsAfterPatch: {oog_err}")

    # 3. Hidden functional tests pass on the PATCHED contract.
    r3 = _run("hiddenTestsPass", patched_sources, {hidden_name: hidden_test}, f"test/{hidden_name}")
    hidden_tests_pass = r3.all_passed

    # 4. Patch is a bounded, honest fix.
    changed = _changed_lines(original_sources[target_file], patched_target)
    nbytes = len(patched_target.encode("utf-8"))
    iface_ok, missing = _interface_preserved(patched_target, contract_name, required_selectors)
    within_lines = changed <= max_changed
    within_bytes = nbytes <= max_bytes

    storage_ok = True
    storage_violations: list[str] = []
    
    # Priority 1: Dynamic storage layout inspection from compiled contract bytecode
    if r1.storage_layout is not None and r2.storage_layout is not None and iface_ok:
        storage_ok, storage_violations = verify_storage_layout_preservation(
            r1.storage_layout, r2.storage_layout
        )
    # Priority 2: Static layout fallback if specified in metadata
    elif meta.get("checkStorageLayout", False) and iface_ok:
        orig_layout_raw = meta.get("originalStorageLayout")
        patched_layout_raw = meta.get("patchedStorageLayout")
        if orig_layout_raw and patched_layout_raw:
            orig_slots = parse_storage_layout_json(orig_layout_raw)
            patched_slots = parse_storage_layout_json(patched_layout_raw)
            storage_ok, storage_violations = verify_storage_layout_preservation(orig_slots, patched_slots)

    patch_within_limits = within_lines and within_bytes and iface_ok and storage_ok
    storage_note = ""
    if r1.storage_layout is not None or meta.get("checkStorageLayout", False):
        storage_note = f" storage={'ok' if storage_ok else 'CORRUPTED ' + '; '.join(storage_violations)}"
    log.append(
        f"patchWithinLimits: changedLines={changed}/{max_changed} bytes={nbytes}/{max_bytes} "
        f"interface={'ok' if iface_ok else 'MISSING ' + ','.join(missing)}{storage_note}"
    )

    # 5. Fuzz + invariant tests on the PATCHED contract, at the pinned schedule.
    #    Static challenges (the reentrancy-001 mint demo) have no suite: the
    #    check is recorded as not applied and does not change `passed`.
    invariant_name = meta.get("invariantTests") or ""
    schedule = invariant_profile(applied=bool(invariant_name))
    if not invariant_name:
        invariants_hold = True
        log.append(
            "invariantsHold: not configured "
            f"seed={schedule['fuzzSeed']} fuzzRuns={schedule['fuzzRuns']} "
            f"invariantRuns={schedule['invariantRuns']} depth={schedule['invariantDepth']}"
        )
    else:
        invariant_test = _read(challenge_dir / "test" / invariant_name)
        r4 = _run(
            "invariantsHold",
            patched_sources,
            {invariant_name: invariant_test},
            f"test/{invariant_name}",
            fuzz_runs=FUZZ_RUNS,
            invariant_runs=INVARIANT_RUNS,
            invariant_depth=INVARIANT_DEPTH,
            fuzz_seed=FUZZ_SEED,
        )
        invariants_hold = r4.all_passed

    passed = (
        poc_proves_bug and poc_fails_after_patch and hidden_tests_pass
        and patch_within_limits and invariants_hold
    )

    return GradeResult(
        challengeId=challenge_id,
        seed=seed,
        vulnClass=vuln_class,
        difficulty=difficulty,
        pocProvesBug=poc_proves_bug,
        pocFailsAfterPatch=poc_fails_after_patch,
        hiddenTestsPass=hidden_tests_pass,
        patchWithinLimits=patch_within_limits,
        invariantsHold=invariants_hold,
        invariantFuzzSeed=int(schedule["fuzzSeed"]),
        invariantFuzzRuns=int(schedule["fuzzRuns"]),
        invariantRuns=int(schedule["invariantRuns"]),
        invariantDepth=int(schedule["invariantDepth"]),
        invariantApplied=bool(schedule["applied"]),
        passed=passed,
        solveSeconds=solve_seconds,
        submissionHash=sub_hash,
        log=" | ".join(log),
    )
