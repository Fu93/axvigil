"""Pure-Python keccak-256 and the canonical AxVigil submission hash.

Zero dependencies on purpose: the grader must produce the *same* submissionHash
as the backend signer and the on-chain check, on any machine, with no network and
no pip install. keccak-256 (not SHA3-256) is what Solidity's ``keccak256`` uses.

The canonical submission encoding is length-prefixed so no two distinct
(challengeId, seed, patch, poc) tuples can collide by concatenation ambiguity:

    keccak256(
        b"AXV1"
        || u32be(len(challengeId_utf8)) || challengeId_utf8
        || u64be(seed)
        || u32be(len(patch_canon))      || patch_canon
        || u32be(len(poc_canon))        || poc_canon
    )

patch_canon / poc_canon are the source bytes normalized to LF line endings with
trailing whitespace stripped per line and a single trailing newline, so cosmetic
reformatting does not change the hash while semantic content does.
"""

from __future__ import annotations

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1


def _rotl(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _MASK


def _keccak_f(state: list[list[int]]) -> None:
    for rnd in range(24):
        # theta
        c = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x][y] ^= d[x]
        # rho + pi
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rotl(state[x][y], _ROT[x][y])
        # chi
        for x in range(5):
            for y in range(5):
                state[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y])
        # iota
        state[0][0] ^= _RC[rnd]


def keccak256(data: bytes) -> bytes:
    """keccak-256 digest (32 bytes), matching Solidity's keccak256."""
    rate = 136  # 1088 bits for keccak-256
    # pad10*1 with keccak domain suffix 0x01
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != 0:
        padded.append(0x00)
    padded[-1] ^= 0x80

    state = [[0] * 5 for _ in range(5)]
    for off in range(0, len(padded), rate):
        block = padded[off:off + rate]
        for i in range(rate // 8):
            lane = int.from_bytes(block[i * 8:i * 8 + 8], "little")
            state[i % 5][i // 5] ^= lane
        _keccak_f(state)

    out = bytearray()
    for i in range(4):  # 4 lanes = 32 bytes, all within the first rate block
        out += state[i % 5][i // 5].to_bytes(8, "little")
    return bytes(out)


def canonicalize_source(text: str) -> bytes:
    """Normalize source so cosmetic diffs don't change the hash."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stripped = [ln.rstrip() for ln in lines]
    while stripped and stripped[-1] == "":
        stripped.pop()
    return ("\n".join(stripped) + "\n").encode("utf-8")


def _u32be(n: int) -> bytes:
    return int(n).to_bytes(4, "big")


def _u64be(n: int) -> bytes:
    return int(n).to_bytes(8, "big")


def submission_hash(challenge_id: str, seed: int, patch: str, poc: str) -> bytes:
    cid = challenge_id.encode("utf-8")
    p = canonicalize_source(patch)
    q = canonicalize_source(poc)
    blob = b"AXV1" + _u32be(len(cid)) + cid + _u64be(seed) + _u32be(len(p)) + p + _u32be(len(q)) + q
    return keccak256(blob)
