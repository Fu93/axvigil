"""Remove NEAR private keys from command output before it is saved."""

from __future__ import annotations

import re

_SECRET_LINE = re.compile(r"(private[ _-]?key|secret[ _-]?key|seed[ _-]?phrase)", re.IGNORECASE)
_PRIVATE_JSON = re.compile(
    r'("(?:private_key|secret_key|secretKey)"\s*:\s*")ed25519:[^"]+(")',
    re.IGNORECASE,
)
_ED25519 = re.compile(r"ed25519:[1-9A-HJ-NP-Za-km-z]+")
_TX_PATTERNS = (
    re.compile(r"Transaction ID:\s*([A-Za-z0-9]+)"),
    re.compile(r"[Tt]ransaction [Hh]ash:\s*([A-Za-z0-9]+)"),
    re.compile(r"nearblocks\.io/txns/([A-Za-z0-9]+)"),
)


def redact(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        line = _PRIVATE_JSON.sub(r"\1ed25519:[redacted]\2", line)
        if _SECRET_LINE.search(line) and "public key" not in line.lower():
            line = _ED25519.sub("ed25519:[redacted]", line)
        kept.append(line)
    return "".join(kept)


def assert_no_secret(text: str) -> None:
    """Reject an unredacted private-key JSON value. Public keys may remain."""
    if re.search(
        r'"(?:private_key|secret_key|secretKey)"\s*:\s*"ed25519:(?!\[redacted\])[^"]+"',
        text,
        re.IGNORECASE,
    ):
        raise SystemExit("refusing to write a private key")


def transaction_id(text: str) -> str | None:
    redacted = redact(text)
    for pattern in _TX_PATTERNS:
        match = pattern.search(redacted)
        if match:
            return match.group(1)
    return None
