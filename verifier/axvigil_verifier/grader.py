"""Grade one submission against one challenge.

The judgement is four independent, deterministic checks:

  pocProvesBug        the submitted PoC *passes* against the ORIGINAL contract
                      (it genuinely triggers the vulnerability)
  pocFailsAfterPatch  the same PoC *fails* against the PATCHED contract
                      (the patch actually closes the hole the PoC used)
  hiddenTestsPass     the hidden functional tests pass against the PATCHED
                      contract (the patch did not break intended behaviour)
  patchWithinLimits   the patch is a real fix, not a rewrite or a gutting:
                      bounded changed lines / bytes, and the target contract
                      and its public interface still exist

passed = all four. A patch that deletes the function the PoC calls cannot win:
it fails patchWithinLimits (interface removed) or hiddenTestsPass.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .forge_runner import run_test, RunResult
from .keccak import submission_hash
from .model import GradeResult

# Shown when hidden tests fail. Names the failure mode without naming the tests
# or the intended fix, so a retry can shrink an over-wide patch.
HIDDEN_FAIL_HINT = "patch changed intended behaviour; keep the fix minimal"


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

    def _run(label: str, sources: dict[str, str], tests: dict[str, str], match: str) -> RunResult:
        r = run_test(
            sources=sources, tests=tests, match_path=match,
            forge_bin=forge_bin, solc=solc, timeout_s=timeout_s,
        )
        if r.timed_out:
            log.append(f"{label}: TIMEOUT after {timeout_s}s")
        elif not r.compiled:
            log.append(f"{label}: compile failed")
        elif label == "hiddenTestsPass":
            # Hidden test names are the challenge's answer key. The agent sees
            # this log on retry, so report only the counts, plus a hint when the
            # patch broke intended behaviour.
            passed_n = sum(r.tests.values())
            total_n = len(r.tests)
            line = f"{label}: {passed_n}/{total_n} tests passed"
            if passed_n != total_n:
                line += ". " + HIDDEN_FAIL_HINT
            log.append(line)
        else:
            log.append(f"{label}: {sum(r.tests.values())}/{len(r.tests)} tests passed {r.tests}")
        return r

    # 1. PoC proves the bug on the ORIGINAL contract.
    r1 = _run("pocProvesBug", original_sources, {poc_name: poc_text}, f"test/{poc_name}")
    poc_proves_bug = r1.all_passed

    # 2. The same PoC FAILS on the PATCHED contract (and the patch compiles).
    r2 = _run("pocFailsAfterPatch", patched_sources, {poc_name: poc_text}, f"test/{poc_name}")
    # Every PoC test must fail after the patch. "At least one failed" let a
    # submission keep the exploit working and add a decoy test that the patch
    # breaks, which still counted as closing the bug.
    poc_fails_after_patch = (
        r2.compiled and not r2.timed_out and bool(r2.tests) and not r2.any_passed
    )

    # 3. Hidden functional tests pass on the PATCHED contract.
    r3 = _run("hiddenTestsPass", patched_sources, {hidden_name: hidden_test}, f"test/{hidden_name}")
    hidden_tests_pass = r3.all_passed

    # 4. Patch is a bounded, honest fix.
    changed = _changed_lines(original_sources[target_file], patched_target)
    nbytes = len(patched_target.encode("utf-8"))
    iface_ok, missing = _interface_preserved(patched_target, contract_name, required_selectors)
    within_lines = changed <= max_changed
    within_bytes = nbytes <= max_bytes
    patch_within_limits = within_lines and within_bytes and iface_ok
    log.append(
        f"patchWithinLimits: changedLines={changed}/{max_changed} bytes={nbytes}/{max_bytes} "
        f"interface={'ok' if iface_ok else 'MISSING ' + ','.join(missing)}"
    )

    passed = poc_proves_bug and poc_fails_after_patch and hidden_tests_pass and patch_within_limits

    return GradeResult(
        challengeId=challenge_id,
        seed=seed,
        vulnClass=vuln_class,
        difficulty=difficulty,
        pocProvesBug=poc_proves_bug,
        pocFailsAfterPatch=poc_fails_after_patch,
        hiddenTestsPass=hidden_tests_pass,
        patchWithinLimits=patch_within_limits,
        passed=passed,
        solveSeconds=solve_seconds,
        submissionHash=sub_hash,
        log=" | ".join(log),
    )
