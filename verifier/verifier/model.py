"""The grading result, serialized exactly as SPEC.md prescribes."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class GradeResult:
    challengeId: str
    seed: int
    vulnClass: int
    difficulty: int
    pocProvesBug: bool
    pocFailsAfterPatch: bool
    hiddenTestsPass: bool
    patchWithinLimits: bool
    passed: bool
    solveSeconds: int | None
    submissionHash: str  # 0x-prefixed 32-byte keccak
    log: str

    def to_json(self) -> dict:
        return asdict(self)
