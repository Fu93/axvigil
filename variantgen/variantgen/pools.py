"""Identifier pools and distractor functions for seed-driven variant generation.

Renaming defeats "the model memorized the public mother's answer"; the distractor
functions and function reordering defeat "the model pattern-matched the file shape".
Distractor bodies are intentionally STRUCTURALLY distinct (different statement
shapes), so choosing a different distractor set changes the structural fingerprint,
not just identifier names.
"""

from __future__ import annotations

# Candidate names, grouped by the role a placeholder plays. The mother's
# `identifiers` map points each sentinel (e.g. "fzzWithdraw") at one of these pools.
POOLS: dict[str, list[str]] = {
    "contract": ["Vault", "Bank", "Treasury", "Reserve", "Ledger", "Pool", "Escrow", "Safe", "Depository", "Coffer"],
    "verb_deposit": ["deposit", "fund", "topUp", "addFunds", "supply", "stake", "credit", "load"],
    "verb_withdraw": ["withdraw", "cashOut", "redeem", "claim", "pull", "exit", "take", "unstake"],
    "verb_total": ["totalAssets", "totalHeld", "poolBalance", "reserves", "assetsUnder", "held", "liquidity"],
    "verb_set": ["setPrice", "updatePrice", "poke", "sync", "refresh", "retune", "recalibrate"],
    "verb_admin": ["setOwner", "transferAdmin", "assignManager", "handover", "reassign", "delegateRole"],
    "noun_balance": ["balanceOf", "deposits", "shares", "credits", "holdings", "ledgerOf", "stakeOf", "fundsOf"],
    "noun_owner": ["owner", "admin", "manager", "governor", "custodian", "operator", "steward"],
    "noun_amount": ["amount", "value", "sum", "qty", "wad", "take", "portion"],
    "noun_ok": ["ok", "sent", "success", "done", "paid", "cleared"],
    "noun_price": ["price", "rate", "spot", "quote", "px", "mark"],
    "noun_token": ["token", "asset", "coin", "unit", "reserveToken", "collateral"],
    # price-manipulation mother
    "verb_borrow": ["borrow", "drawDown", "takeLoan", "open", "leverage"],
    "verb_repay": ["repay", "payBack", "settle", "closeLoan", "reduceDebt"],
    "verb_swap": ["swap", "trade", "rebalance", "moveMarket", "shiftReserves"],
    "fn_spot": ["spotPrice", "instantPrice", "poolPrice", "livePrice", "markSpot"],
    "fn_safe": ["safePrice", "oraclePrice", "twapPrice", "anchorPrice", "refQuote"],
    "noun_collateral": ["collateralOf", "depositedOf", "lockedOf", "marginOf", "postedOf"],
    "noun_debt": ["debtOf", "owedBy", "borrowedOf", "loanOf", "liabilityOf"],
    "noun_rbase": ["reserveBase", "baseReserve", "poolBase", "baseLiq", "baseAmt"],
    "noun_rquote": ["reserveQuote", "quoteReserve", "poolQuote", "quoteLiq", "quoteAmt"],
    "noun_ref": ["refPrice", "anchorMark", "oracleMark", "pegPrice", "trustedPrice"],
    # access-control mother
    "verb_admin_set": ["setOwner", "transferOwnership", "assignAdmin", "handover", "reassignOwner"],
    "verb_sweep": ["sweep", "drain", "rescueFunds", "withdrawAll", "collect"],
    "verb_config": ["setFee", "configure", "tune", "setParam", "adjust"],
}

# Structurally-distinct harmless functions. {name} is replaced with a unique id.
# Each has a different statement shape so distractor choice affects the fingerprint.
DISTRACTORS: list[str] = [
    "    uint256 public {name}Counter;\n"
    "    function {name}() external {{ {name}Counter += 1; }}",

    "    function {name}(uint256 a, uint256 b) external pure returns (uint256) {{ return a + b; }}",

    "    mapping(address => uint256) public {name}Seen;\n"
    "    function {name}() external {{ {name}Seen[msg.sender] = block.number; }}",

    "    event {name}Ping(address indexed who);\n"
    "    function {name}() external {{ emit {name}Ping(msg.sender); }}",

    "    function {name}(uint256 x) external pure returns (uint256) {{ return x * x; }}",

    "    uint256 private {name}Nonce;\n"
    "    function {name}() external returns (uint256) {{ return ++{name}Nonce; }}",

    "    function {name}(address a) external view returns (bool) {{ return a == msg.sender; }}",

    "    string public constant {name}Tag = \"axvigil\";\n"
    "    function {name}() external pure returns (bytes32) {{ return keccak256(bytes({name}Tag)); }}",
]

DISTRACTOR_NAMES: list[str] = [
    "aux", "meta", "probe", "beacon", "tally", "scribe", "warden", "relay",
    "oracleHint", "pinger", "marker", "ticker", "sentry", "notary",
]
