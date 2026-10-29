"""Prompt construction for the solver loop."""

from __future__ import annotations

SYSTEM = """You are AxVigil, an autonomous smart-contract security agent operating in a \
whitehat sandbox. You are given a single Solidity contract that contains exactly one \
intended vulnerability (reentrancy, price manipulation, or access control). Your job:

1. Find the vulnerability.
2. Produce a MINIMAL patch of the target file that fixes it WITHOUT changing the \
contract name or removing any public/external function in its interface, and without \
breaking legitimate behaviour.
3. Produce a Foundry proof-of-concept test that PASSES against the original \
(vulnerable) contract and FAILS against your patched one — i.e. it demonstrates the \
exploit, so a trivial always-pass test earns nothing.

Return ONLY a single JSON object, no prose outside it, with exactly these keys:
  "analysis":         short explanation of the bug and the fix
  "patched_contract": the FULL patched source of the target file
  "poc_test":         the FULL source of a Foundry test file

The PoC test file must import the target via "../src/<TargetFile>" and compile under \
the challenge's pragma. Keep the patch as small as possible."""


def build_user_prompt(
    *, challenge_id: str, target_file: str, contract_name: str, vuln_class_name: str,
    pragma: str, source: str, required_functions: list[str],
) -> str:
    funcs = ", ".join(required_functions) if required_functions else "(none specified)"
    return f"""Challenge: {challenge_id}
Target file: {target_file}   (contract {contract_name}, pragma {pragma})
Suspected class: {vuln_class_name}
Public functions that must remain: {funcs}

Source of {target_file}:
```solidity
{source}
```

Return the JSON object described in the system message."""


def build_retry_prompt(*, prev_patch: str, prev_poc: str, result_log: str, checks: dict) -> str:
    failed = [k for k, v in checks.items() if not v]
    return f"""Your previous submission did NOT pass. Failed checks: {failed}

Grader log:
{result_log}

What each check means:
- pocProvesBug: your PoC must PASS on the ORIGINAL contract (actually trigger the bug).
- pocFailsAfterPatch: your PoC must FAIL on your PATCHED contract (the fix must close it).
- hiddenTestsPass: hidden functional tests must still pass on your patched contract.
- patchWithinLimits: keep the diff small; do not rename the contract or delete interface functions.

Your previous patched_contract:
```solidity
{prev_patch}
```

Your previous poc_test:
```solidity
{prev_poc}
```

Fix the failing checks and return the full JSON object again."""
