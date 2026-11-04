"""Gas DoS and Out-of-Gas exploit guard.

Detects fake remediation where a patch induces an Out-of-Gas loop or severe
resource exhaustion, making tests fail due to EVM resource limits rather than
a genuine security check (e.g. require/revert).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class GasAuditResult:
    poc_valid_remediation: bool
    gas_regression_detected: bool
    rejection_reason: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def is_out_of_gas_failure(reason: Optional[str]) -> bool:
    """Return True if the failure reason indicates Out-of-Gas or resource exhaustion."""
    if not reason:
        return False
    low = reason.strip().lower()
    oog_markers = [
        "outofgas",
        "out of gas",
        "evmerror: outofgas",
        "evmerror: out of gas",
        "evmerror: gaslimitexceeded",
        "exceeded block gas limit",
        "intrinsic gas too low",
        "invalidfeopcode",
        "memorylimitexceeded",
        "memoryoog",
        "memorylimitoog",
        "precompileoog",
        "callgascostmorethangaslimit",
        "stack overflow",
        "max call depth exceeded",
        "execution reverted: out of gas",
    ]
    return any(marker in low for marker in oog_markers)


def check_poc_failure_is_valid_remediation(
    reasons: Dict[str, Optional[str]],
) -> Tuple[bool, Optional[str]]:
    """Verify that a failing PoC on a patched contract failed for a legitimate reason.
    
    If the PoC failed due to an Out-of-Gas error or infinite loop, reject it as a fake fix.
    """
    for test_name, reason in reasons.items():
        if is_out_of_gas_failure(reason):
            return (
                False,
                f"PoC {test_name} failed with Out-of-Gas ({reason}). "
                "Fake patch induced DoS/resource exhaustion rather than closing the vulnerability.",
            )
    return (True, None)


def check_gas_regression(
    baseline_gas: Dict[str, Optional[int]],
    patched_gas: Dict[str, Optional[int]],
    *,
    max_increase_pct: float = 40.0,
    min_absolute_delta: int = 25_000,
    block_limit_cap: int = 30_000_000,
) -> Tuple[bool, List[str]]:
    """Check for unacceptable gas regression between baseline and patched contract runs.

    Args:
        baseline_gas: Mapping of test names to baseline gas consumed.
        patched_gas: Mapping of test names to patched gas consumed.
        max_increase_pct: Maximum allowed percentage increase in gas usage (default 40%).
        min_absolute_delta: Minimum gas delta required to trigger a percentage violation.
        block_limit_cap: Absolute gas ceiling per transaction/test (default 30M EVM block cap).

    Returns:
        (passed, list_of_violations)
    """
    violations: List[str] = []

    for test_name, p_gas in patched_gas.items():
        if p_gas is None:
            continue

        if p_gas > block_limit_cap:
            violations.append(
                f"{test_name} gas usage {p_gas:,} exceeds block gas ceiling {block_limit_cap:,}"
            )
            continue

        base_gas = baseline_gas.get(test_name)
        if base_gas and base_gas > 0:
            delta = p_gas - base_gas
            pct_change = (delta / base_gas) * 100.0
            if pct_change > max_increase_pct and delta > min_absolute_delta:
                violations.append(
                    f"{test_name} gas increased by {pct_change:.1f}% "
                    f"({base_gas:,} -> {p_gas:,}, max allowed +{max_increase_pct:.0f}%)"
                )

    passed = len(violations) == 0
    return (passed, violations)
