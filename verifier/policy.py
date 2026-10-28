import difflib
import re
from eth_utils import keccak

MAX_BYTES = 24000
MAX_CHANGED_LINES = 80


def validate(original: str, patch: str, poc: str):
    for source in (patch, poc):
        if not source or len(source.encode()) > MAX_BYTES:
            raise ValueError("Source must contain 1..24000 bytes")
        # No imports, compiler callbacks, external sources, or Foundry filesystem/ffi access.
        if re.search(r"\bimport\b", source):
            raise ValueError("Submit self-contained Solidity without imports")
    changed = sum(
        1
        for x in difflib.ndiff(original.splitlines(), patch.splitlines())
        if x.startswith(("+ ", "- "))
    )
    if changed > MAX_CHANGED_LINES:
        raise ValueError(f"Patch exceeds {MAX_CHANGED_LINES} changed lines")
    return changed


def submission_hash(patch, poc):
    import json

    return (
        "0x"
        + keccak(
            text=json.dumps(
                {"patch": patch, "poc": poc}, sort_keys=True, separators=(",", ":")
            )
        ).hex()
    )
