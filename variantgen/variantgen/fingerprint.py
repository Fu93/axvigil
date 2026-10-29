"""Structural fingerprint for variant uniqueness.

Comments and whitespace are stripped and every non-keyword identifier and numeric
literal is canonicalized, so two variants that differ ONLY by renaming hash the
same (and one is discarded). Real structural variety — function order, which
distractors were inserted — survives and makes a variant unique. This is the
"AST/bytecode similarity, discard if too alike" rule from the PRD, done cheaply.
"""

from __future__ import annotations

import hashlib
import re

_KEYWORDS = {
    "pragma", "solidity", "import", "from", "contract", "interface", "library", "is",
    "function", "modifier", "event", "error", "struct", "enum", "mapping",
    "public", "external", "internal", "private", "view", "pure", "payable",
    "returns", "return", "memory", "storage", "calldata", "constant", "immutable",
    "require", "revert", "assert", "emit", "new", "if", "else", "for", "while", "do",
    "address", "bool", "string", "bytes", "bytes32", "bytes4",
    "uint", "uint8", "uint32", "uint64", "uint128", "uint256",
    "int", "int256", "msg", "block", "tx", "this", "super", "abi", "keccak256",
    "indexed", "true", "false", "wei", "gwei", "ether", "seconds", "days",
    "SPDX", "License", "Identifier", "MIT",
}

_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|\S")


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


def canonical_tokens(src: str) -> list[str]:
    src = _strip_comments(src)
    out: list[str] = []
    for tok in _TOKEN.findall(src):
        if tok.isdigit():
            out.append("N")
        elif re.match(r"[A-Za-z_]\w*$", tok):
            out.append(tok if tok in _KEYWORDS else "ID")
        else:
            out.append(tok)
    return out


def fingerprint(src: str) -> str:
    toks = canonical_tokens(src)
    return hashlib.sha256(" ".join(toks).encode("utf-8")).hexdigest()[:16]
