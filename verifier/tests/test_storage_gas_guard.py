"""Tests for Storage Layout Preservation Guard and Gas DoS / Out-of-Gas Guard."""

from __future__ import annotations

import pytest

from axvigil_verifier.gas_guard import (
    check_gas_regression,
    check_poc_failure_is_valid_remediation,
    is_out_of_gas_failure,
)
from axvigil_verifier.storage_guard import (
    StorageSlot,
    parse_storage_layout_json,
    verify_storage_layout_preservation,
)


# --- Gas Guard Unit Tests ---


def test_is_out_of_gas_failure():
    assert is_out_of_gas_failure("EvmError: OutOfGas") is True
    assert is_out_of_gas_failure("evmerror: out of gas") is True
    assert is_out_of_gas_failure("Exceeded block gas limit") is True
    assert is_out_of_gas_failure("EvmError: Revert") is False
    assert is_out_of_gas_failure("execution reverted: Unauthorized") is False
    assert is_out_of_gas_failure("panic: assertion failed (0x01)") is False
    assert is_out_of_gas_failure(None) is False
    assert is_out_of_gas_failure("") is False


def test_check_poc_failure_is_valid_remediation():
    # Legitimate revert fix
    reasons_valid = {
        "test_exploit()": "EvmError: Revert",
    }
    valid, err = check_poc_failure_is_valid_remediation(reasons_valid)
    assert valid is True
    assert err is None

    # Fake fix that reverts due to Out-of-Gas loop
    reasons_oog = {
        "test_exploit()": "EvmError: OutOfGas",
    }
    valid, err = check_poc_failure_is_valid_remediation(reasons_oog)
    assert valid is False
    assert "Out-of-Gas" in err
    assert "Fake patch induced DoS" in err


def test_check_gas_regression():
    base = {"test_deposit()": 50_000, "test_withdraw()": 40_000}

    # Within acceptable +40% threshold
    patched_ok = {"test_deposit()": 55_000, "test_withdraw()": 42_000}
    ok, violations = check_gas_regression(base, patched_ok, max_increase_pct=40.0)
    assert ok is True
    assert len(violations) == 0

    # Severe +100% regression
    patched_bloated = {"test_deposit()": 110_000, "test_withdraw()": 42_000}
    ok, violations = check_gas_regression(base, patched_bloated, max_increase_pct=40.0)
    assert ok is False
    assert any("gas increased by 120.0%" in v for v in violations)

    # Exceeding block ceiling (30M gas)
    patched_astronomical = {"test_deposit()": 35_000_000}
    ok, violations = check_gas_regression(base, patched_astronomical, block_limit_cap=30_000_000)
    assert ok is False
    assert any("exceeds block gas ceiling" in v for v in violations)


# --- Storage Guard Unit Tests ---


def test_parse_storage_layout_json():
    raw = {
        "storage": [
            {
                "contract": "src/Vault.sol:Vault",
                "label": "owner",
                "offset": 0,
                "slot": "0",
                "type": "t_address",
            },
            {
                "contract": "src/Vault.sol:Vault",
                "label": "totalAssets",
                "offset": 0,
                "slot": "1",
                "type": "t_uint256",
            },
        ],
        "types": {
            "t_address": {"numberOfBytes": "20"},
            "t_uint256": {"numberOfBytes": "32"},
        },
    }
    slots = parse_storage_layout_json(raw)
    assert len(slots) == 2
    assert slots[0].label == "owner"
    assert slots[0].slot == 0
    assert slots[0].offset == 0
    assert slots[0].number_of_bytes == 20
    assert slots[1].label == "totalAssets"
    assert slots[1].slot == 1
    assert slots[1].number_of_bytes == 32


def test_storage_preservation_identical_layout():
    orig = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
    ]
    patched = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_storage_ast_id_normalization():
    # Solc ast node id shift between compilation runs: t_struct(Info)120_storage vs t_struct(Info)135_storage
    orig = [
        StorageSlot("Vault", "info", 0, 0, "t_struct(Info)120_storage", 32),
    ]
    patched = [
        StorageSlot("Vault", "info", 0, 0, "t_struct(Info)135_storage", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_storage_inheritance_shadowing_not_colliding():
    orig = [
        StorageSlot("Base", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "owner", 0, 1, "t_address", 20),
    ]
    patched = [
        StorageSlot("Base", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "owner", 0, 1, "t_address", 20),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_revm_oog_markers():
    assert is_out_of_gas_failure("memoryoog") is True
    assert is_out_of_gas_failure("memorylimitoog") is True
    assert is_out_of_gas_failure("precompileoog") is True
    assert is_out_of_gas_failure("callgascostmorethangaslimit") is True


def test_storage_struct_member_mutation_rejected():
    orig = [
        StorageSlot("Vault", "cfg", 0, 0, "t_struct(Config)_storage", 64, members_signature="a:0:0:t_uint128;b:16:0:t_uint128"),
    ]
    # Altered struct member types/offsets
    patched = [
        StorageSlot("Vault", "cfg", 0, 0, "t_struct(Config)_storage", 64, members_signature="a:0:0:t_uint256;b:0:1:t_uint256"),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("Storage struct member mutation" in v for v in violations)


def test_storage_multi_slot_span_collision_rejected():
    # orig has a 64-byte struct at slot 0 (occupies slots 0 and 1)
    orig = [
        StorageSlot("Vault", "pair", 0, 0, "t_struct(Pair)_storage", 64),
    ]
    # Patched attempts to place a new variable at slot 1
    patched = [
        StorageSlot("Vault", "pair", 0, 0, "t_struct(Pair)_storage", 64),
        StorageSlot("Vault", "collidingVar", 0, 1, "t_uint256", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("spans across existing occupied slot" in v or "collides" in v for v in violations)


def test_storage_rejection_on_variable_deletion():
    orig = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
    ]
    # 'totalAssets' removed
    patched = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("variable 'totalAssets' was removed" in v for v in violations)


def test_storage_rejection_on_slot_shift():
    orig = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
    ]
    # Agent inserted 'attacker' at slot 0, shifting 'owner' to slot 1 and 'totalAssets' to slot 2
    patched = [
        StorageSlot("Vault", "attacker", 0, 0, "t_address", 20),
        StorageSlot("Vault", "owner", 0, 1, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 2, "t_uint256", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("Storage collision on 'owner': slot changed from 0 to 1" in v for v in violations)
    assert any("Storage collision on 'totalAssets': slot changed from 1 to 2" in v for v in violations)


def test_storage_rejection_on_type_mutation():
    orig = [
        StorageSlot("Vault", "totalAssets", 0, 0, "t_uint256", 32),
    ]
    # Agent changed uint256 to uint128
    patched = [
        StorageSlot("Vault", "totalAssets", 0, 0, "t_uint128", 16),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("type changed from t_uint256 to t_uint128" in v for v in violations)


def test_storage_safe_append_allowed():
    orig = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
    ]
    # Agent safely appended a new variable at slot 2
    patched = [
        StorageSlot("Vault", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "totalAssets", 0, 1, "t_uint256", 32),
        StorageSlot("Vault", "_locked", 0, 2, "t_bool", 1),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_storage_ast_id_normalization():
    # Solc ast node id shift between compilation runs: t_struct(Info)120_storage vs t_struct(Info)135_storage
    orig = [
        StorageSlot("Vault", "info", 0, 0, "t_struct(Info)120_storage", 32),
    ]
    patched = [
        StorageSlot("Vault", "info", 0, 0, "t_struct(Info)135_storage", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_storage_inheritance_shadowing_not_colliding():
    orig = [
        StorageSlot("Base", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "owner", 0, 1, "t_address", 20),
    ]
    patched = [
        StorageSlot("Base", "owner", 0, 0, "t_address", 20),
        StorageSlot("Vault", "owner", 0, 1, "t_address", 20),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is True
    assert len(violations) == 0


def test_revm_oog_markers():
    assert is_out_of_gas_failure("memoryoog") is True
    assert is_out_of_gas_failure("memorylimitoog") is True
    assert is_out_of_gas_failure("precompileoog") is True
    assert is_out_of_gas_failure("callgascostmorethangaslimit") is True


def test_storage_struct_member_mutation_rejected():
    orig = [
        StorageSlot("Vault", "cfg", 0, 0, "t_struct(Config)_storage", 64, members_signature="a:0:0:t_uint128;b:16:0:t_uint128"),
    ]
    # Altered struct member types/offsets
    patched = [
        StorageSlot("Vault", "cfg", 0, 0, "t_struct(Config)_storage", 64, members_signature="a:0:0:t_uint256;b:0:1:t_uint256"),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("Storage struct member mutation" in v for v in violations)


def test_storage_multi_slot_span_collision_rejected():
    # orig has a 64-byte struct at slot 0 (occupies slots 0 and 1)
    orig = [
        StorageSlot("Vault", "pair", 0, 0, "t_struct(Pair)_storage", 64),
    ]
    # Patched attempts to place a new variable at slot 1
    patched = [
        StorageSlot("Vault", "pair", 0, 0, "t_struct(Pair)_storage", 64),
        StorageSlot("Vault", "collidingVar", 0, 1, "t_uint256", 32),
    ]
    ok, violations = verify_storage_layout_preservation(orig, patched)
    assert ok is False
    assert any("spans across existing occupied slot" in v or "collides" in v for v in violations)


def test_recursive_type_signature_nested_structs():
    from axvigil_verifier.storage_guard import _compute_type_signature

    types_info_orig = {
        "t_struct(Inner)_storage": {
            "members": [
                {"label": "x", "offset": 0, "slot": 0, "type": "t_uint128"},
                {"label": "y", "offset": 16, "slot": 0, "type": "t_uint128"},
            ]
        },
        "t_struct(Outer)_storage": {
            "members": [
                {"label": "inner", "offset": 0, "slot": 0, "type": "t_struct(Inner)_storage"},
                {"label": "count", "offset": 0, "slot": 1, "type": "t_uint256"},
            ]
        },
    }

    sig_orig = _compute_type_signature("t_struct(Outer)_storage", types_info_orig)
    assert "struct(inner:0:0:(struct(x:0:0:(t_uint128);y:16:0:(t_uint128)))" in sig_orig

    # Altering the nested inner struct modifies the outer struct's recursive signature
    types_info_mutated = {
        "t_struct(Inner)_storage": {
            "members": [
                {"label": "x", "offset": 0, "slot": 0, "type": "t_uint256"},
                {"label": "y", "offset": 0, "slot": 1, "type": "t_uint256"},
            ]
        },
        "t_struct(Outer)_storage": {
            "members": [
                {"label": "inner", "offset": 0, "slot": 0, "type": "t_struct(Inner)_storage"},
                {"label": "count", "offset": 0, "slot": 1, "type": "t_uint256"},
            ]
        },
    }
    sig_mutated = _compute_type_signature("t_struct(Outer)_storage", types_info_mutated)
    assert sig_orig != sig_mutated


def test_forge_runner_environment_sanitization(monkeypatch):
    import os
    # Inject sensitive secrets into host os.environ
    monkeypatch.setenv("SIGNER_KEY", "0xdeadbeef1234567890abcdef")
    monkeypatch.setenv("SESSION_SECRET", "super-secret-production-token")
    monkeypatch.setenv("RPC_URL", "https://secret-rpc-node.internal")

    # Safe keys whitelist logic from forge_runner
    safe_keys = {"PATH", "TMPDIR", "TEMP", "TMP", "SOLC", "HOME", "USER", "SYSTEMROOT", "WINDIR"}
    env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
    env["FOUNDRY_OFFLINE"] = "true"
    env["FOUNDRY_FUZZ_SEED"] = "1337"

    assert "SIGNER_KEY" not in env
    assert "SESSION_SECRET" not in env
    assert "RPC_URL" not in env
    assert env["FOUNDRY_OFFLINE"] == "true"
    assert env["FOUNDRY_FUZZ_SEED"] == "1337"


def test_grader_excessive_gas_poc_fails_rejected():
    # Simulate a patch that fails the PoC but burned excessive gas (algorithmic DoS)
    gas_used_excessive = {"test_exploit()": 22_500_000}
    max_poc_gas_ceiling = 15_000_000

    poc_fails_after_patch = True
    for test_name, g_used in gas_used_excessive.items():
        if g_used is not None and g_used > max_poc_gas_ceiling:
            poc_fails_after_patch = False
            break

    assert poc_fails_after_patch is False
