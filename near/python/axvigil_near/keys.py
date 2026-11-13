"""Write a NEAR ed25519 key file without printing the secret.

The seed comes from OpenSSL's Ed25519 PKCS8 blob (the 32-byte seed is the
last 32 bytes of the private DER on OpenSSL 3). The file mode is 0600.
Stdout receives the public key only.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(text: str) -> bytes:
    if any(char not in _ALPHABET for char in text):
        raise ValueError("invalid base58")
    pad = 0
    for char in text:
        if char == "1":
            pad += 1
        else:
            break
    number = 0
    for char in text:
        number = number * 58 + _ALPHABET.index(char)
    if number == 0:
        raw = b""
    else:
        width = (number.bit_length() + 7) // 8
        raw = number.to_bytes(width, "big")
    return (b"\x00" * pad) + raw


def b58encode(data: bytes) -> str:
    zeros = 0
    for byte in data:
        if byte == 0:
            zeros += 1
        else:
            break
    number = int.from_bytes(data, "big")
    chars: list[str] = []
    while number:
        number, rem = divmod(number, 58)
        chars.append(_ALPHABET[rem])
    encoded = "".join(reversed(chars))
    return ("1" * zeros) + encoded


def _openssl_raw(pem: Path, public: bool) -> bytes:
    cmd = ["openssl", "pkey", "-in", str(pem), "-outform", "DER"]
    if public:
        cmd.insert(2, "-pubout")
    proc = subprocess.run(cmd, check=True, capture_output=True)
    if len(proc.stdout) < 32:
        raise RuntimeError("openssl returned a short Ed25519 key")
    return proc.stdout[-32:]


def write_key_file(account_id: str, path: Path) -> str:
    """Create ``path`` and return the public key (``ed25519:...``)."""
    if not account_id or any(c.isspace() for c in account_id):
        raise ValueError("account id is empty or contains whitespace")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, pem_name = tempfile.mkstemp(prefix="axv-near-", suffix=".pem")
    os.close(fd)
    pem = Path(pem_name)
    try:
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(pem)],
            check=True,
            capture_output=True,
        )
        os.chmod(pem, stat.S_IRUSR | stat.S_IWUSR)
        seed = _openssl_raw(pem, public=False)
        public = _openssl_raw(pem, public=True)
    finally:
        pem.unlink(missing_ok=True)
    public_key = "ed25519:" + b58encode(public)
    # near-cli-rs reads a 64-byte expanded secret: seed || public key.
    secret = "ed25519:" + b58encode(seed + public)
    payload = {
        "account_id": account_id,
        "public_key": public_key,
        "private_key": secret,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(descriptor, (json.dumps(payload) + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return public_key


def expand_key_file(path: Path) -> None:
    """Rewrite a 32-byte seed secret as the 64-byte form near-cli-rs expects."""
    stored = json.loads(path.read_text())
    prefix, encoded = stored["private_key"].split(":", 1)
    if prefix != "ed25519":
        raise ValueError("scoped key is not ed25519")
    raw = b58decode(encoded)
    public = b58decode(stored["public_key"].split(":", 1)[1])
    if len(raw) == 64:
        if raw[32:] != public:
            raise ValueError("expanded secret does not match its public key")
        return
    if len(raw) != 32:
        raise ValueError(f"unexpected secret length {len(raw)}")
    stored["private_key"] = "ed25519:" + b58encode(raw + public)
    descriptor = os.open(path, os.O_WRONLY | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(descriptor, (json.dumps(stored) + "\n").encode("utf-8"))
    finally:
        os.close(descriptor)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
