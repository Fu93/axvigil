"""Reference fixes, applied to the *rendered* (concrete) source so the diff stays
minimal regardless of renaming, distractor insertion or function reordering.

Each fix takes the rendered vulnerable source + the render context and returns the
patched source. It must change only the vulnerable lines (so patchWithinLimits
holds) and preserve the contract name and public interface.
"""

from __future__ import annotations

import re


def _ids(ctx: dict) -> dict:
    return ctx["ids"]


def fix_reentrancy_cei(src: str, ctx: dict) -> str:
    """Checks-effects-interactions: move the balance-zeroing assignment to before
    the external call."""
    ids = _ids(ctx)
    bal = ids["vzzBal"]
    amt = ids["lzzAmt"]
    ok = ids["lzzOk"]

    call_block = (
        rf"(?P<call>[ \t]*\(bool {re.escape(ok)},\) = msg\.sender\.call\{{value: {re.escape(amt)}\}}\(\"\"\);\n"
        rf"[ \t]*require\({re.escape(ok)}, \"[^\"]*\"\);\n)"
    )
    zero_line = rf"(?P<zero>[ \t]*{re.escape(bal)}\[msg\.sender\] = 0;\n)"
    # vulnerable order: call_block, (optional blank lines), zero_line
    pattern = re.compile(call_block + r"(?P<gap>[ \t]*\n)*" + zero_line)
    m = pattern.search(src)
    if not m:
        raise ValueError("reentrancy fix: could not locate the vulnerable call/zero sequence")
    # checks-effects-interactions: zero first, then the external call
    replacement = m.group("zero") + m.group("call")
    return src[: m.start()] + replacement + src[m.end():]


def fix_access_control(src: str, ctx: dict) -> str:
    """Add the missing owner check to the privileged admin function."""
    ids = _ids(ctx)
    owner = ids["vzzOwner"]
    admin_fn = ids["fzzAdmin"]

    # Insert `require(msg.sender == <owner>, "not owner");` as the first statement
    # of the admin function body.
    pat = re.compile(
        rf"(function {re.escape(admin_fn)}\([^)]*\)[^{{]*\{{\n)"
    )
    m = pat.search(src)
    if not m:
        raise ValueError("access-control fix: could not locate the admin function")
    indent = "        "
    guard = f'{indent}require(msg.sender == {owner}, "not owner");\n'
    return src[: m.end()] + guard + src[m.end():]


def fix_price_twap(src: str, ctx: dict) -> str:
    """Replace the spot-price read with the contract's manipulation-resistant
    reference price (a sentinel helper the mother already defines)."""
    ids = _ids(ctx)
    spot_fn = ids["fzzSpot"]
    safe_fn = ids["fzzSafe"]

    # The vulnerable valuation calls the spot price; route it through the safe
    # reference price instead. Rewrite CALL sites only, never the definition
    # (`function <spot>(`), via a negative lookbehind on "function ".
    pattern = re.compile(rf"(?<!function ){re.escape(spot_fn)}\(\)")
    if not pattern.search(src):
        raise ValueError("price fix: could not locate the spot-price call site")
    return pattern.sub(f"{safe_fn}()", src)


def fix_sig_replay(src: str, ctx: dict) -> str:
    """Mark each voucher digest as spent after the signature check, so a signed
    voucher can't be replayed. The vulnerable source does not mention a spent-flag;
    the fix adds the mapping and the guard, and nothing else."""
    ids = _ids(ctx)
    used = ids["vzzUsed"]
    digest = ids["lzzDigest"]
    signer = ids["vzzSigner"]

    if re.search(rf"\b{re.escape(used)}\b", src) is None:
        anchor = re.compile(rf"(^[ \t]*address public {re.escape(signer)};\n)", re.M)
        state = anchor.search(src)
        if not state:
            raise ValueError("sig-replay fix: could not locate the signer state variable")
        mapping_line = f"    mapping(bytes32 => bool) public {used};\n"
        src = src[: state.end()] + mapping_line + src[state.end():]

    pat = re.compile(
        rf"([ \t]*require\(ecrecover\({re.escape(digest)}, v, r, s\) == {re.escape(signer)}, \"[^\"]*\"\);\n)"
    )
    m = pat.search(src)
    if not m:
        raise ValueError("sig-replay fix: could not locate the signature check")
    indent = re.match(r"[ \t]*", m.group(1)).group(0)
    guard = (
        f'{indent}require(!{used}[{digest}], "voucher already used");\n'
        f'{indent}{used}[{digest}] = true;\n'
    )
    return src[: m.end()] + guard + src[m.end():]


def fix_bridge_phantom_deposit(src: str, ctx: dict) -> str:
    """Real incident (Qubit QBridge, Jan 2022). A low-level call to an address with no
    code "succeeds" with empty return data, so the bridge credits a deposit that never
    moved any tokens. Refuse codeless tokens in the pull helper (the OpenZeppelin
    SafeERC20 / Address.functionCall behaviour)."""
    pull = _ids(ctx)["fzzPull"]
    m = re.search(rf"(function {re.escape(pull)}\([^)]*\)[^{{]*\{{\n)", src)
    if not m:
        raise ValueError("bridge fix: could not locate the pull helper")
    guard = '        require(token.code.length > 0, "token has no code");\n'
    return src[: m.end()] + guard + src[m.end():]


def fix_share_inflation(src: str, ctx: dict) -> str:
    """Real incident (Hundred Finance / Sonne, Compound-fork empty markets). The vault
    prices shares off its live asset balance, so a direct transfer (donation) inflates
    the share price and rounds later deposits down. Value the pool by the assets actually
    deposited through the vault (a donation-resistant book helper the mother defines)
    instead of the live balance. Rewrite CALL sites only, not the definition."""
    ids = _ids(ctx)
    live_fn = ids["fzzPoolValue"]
    book_fn = ids["fzzBookValue"]
    pattern = re.compile(rf"(?<!function ){re.escape(live_fn)}\(\)")
    if not pattern.search(src):
        raise ValueError("share-inflation fix: could not locate the live-value call site")
    return pattern.sub(f"{book_fn}()", src)


FIXES = {
    "reentrancy_cei": fix_reentrancy_cei,
    "access_control": fix_access_control,
    "price_twap": fix_price_twap,
    "sig_replay": fix_sig_replay,
    "bridge_phantom_deposit": fix_bridge_phantom_deposit,
    "share_inflation": fix_share_inflation,
}
