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
