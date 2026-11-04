"""Storage layout preservation verifier.

Guarantees that smart-contract patches do not corrupt EVM storage layout,
preventing storage slot collisions, accidental variable displacement, or
destructive layout alterations critical to upgradeable proxies and inherited contracts.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class StorageSlot:
    contract: str
    label: str
    offset: int
    slot: int
    type_name: str
    number_of_bytes: int = 32
    members_signature: str = ""


def normalize_type_key(k: str) -> str:
    """Normalize solc AST node IDs from struct/enum/type names (e.g. t_struct(Foo)1234_storage -> t_struct(Foo)_storage)."""
    return re.sub(r"((?:t_)?(?:struct|enum|contract|userDefinedValueType)\([^)]+\))(\d+)(_storage)?", r"\1\3", k)


def _compute_type_signature(type_key: str, types_info: dict, visited: set | None = None) -> str:
    """Recursively computes canonical signature for any Solc storage type.
    Handles nested structs, mappings, arrays, and elementary types.
    """
    if visited is None:
        visited = set()
    norm_key = normalize_type_key(type_key)
    if norm_key in visited:
        return norm_key
    visited.add(norm_key)

    type_meta = types_info.get(type_key, {})
    if not type_meta:
        return norm_key

    # Handle structs
    members = type_meta.get("members")
    if members:
        member_sigs = []
        for m in members:
            lbl = m.get("label", "")
            off = m.get("offset", 0)
            slot = m.get("slot", 0)
            m_type = m.get("type", "")
            m_sig = _compute_type_signature(m_type, types_info, visited.copy())
            member_sigs.append(f"{lbl}:{off}:{slot}:({m_sig})")
        return f"struct({';'.join(member_sigs)})"

    # Handle mappings
    if "key" in type_meta and "value" in type_meta:
        k_sig = _compute_type_signature(type_meta["key"], types_info, visited.copy())
        v_sig = _compute_type_signature(type_meta["value"], types_info, visited.copy())
        return f"mapping({k_sig}=>{v_sig})"

    # Handle arrays
    if "base" in type_meta:
        b_sig = _compute_type_signature(type_meta["base"], types_info, visited.copy())
        n_bytes = type_meta.get("numberOfBytes")
        if n_bytes:
            return f"array({b_sig},{n_bytes})"
        return f"array({b_sig})"

    return norm_key


def _compute_members_sig(type_meta: dict, types_info: dict | None = None) -> str:
    if types_info:
        t_key = next((k for k, v in types_info.items() if v == type_meta), "")
        if t_key:
            return _compute_type_signature(t_key, types_info)
    members = type_meta.get("members", [])
    if not members:
        return ""
    parts = []
    for m in members:
        lbl = m.get("label", "")
        off = m.get("offset", 0)
        slot = m.get("slot", 0)
        tkey = normalize_type_key(m.get("type", ""))
        parts.append(f"{lbl}:{off}:{slot}:{tkey}")
    return ";".join(parts)


def parse_storage_layout_json(raw: str | dict) -> List[StorageSlot]:
    """Parse JSON output from `forge inspect <Contract> storage-layout --json`."""
    if isinstance(raw, str):
        data = json.loads(raw)
    else:
        data = raw

    storage_entries = data.get("storage", [])
    types_info = data.get("types", {})

    slots: List[StorageSlot] = []
    for item in storage_entries:
        type_key = item.get("type", "")
        type_meta = types_info.get(type_key, {})
        n_bytes = int(type_meta.get("numberOfBytes", 32)) if type_meta else 32
        m_sig = _compute_type_signature(type_key, types_info) if type_meta else ""

        slots.append(
            StorageSlot(
                contract=item.get("contract", ""),
                label=item.get("label", ""),
                offset=int(item.get("offset", 0)),
                slot=int(item.get("slot", 0)),
                type_name=type_key,
                number_of_bytes=n_bytes,
                members_signature=m_sig,
            )
        )
    return slots


def extract_storage_layout_from_project(
    forge_bin: str,
    project_dir: Path | str,
    contract_name: str,
    *,
    solc: Optional[str] = None,
    timeout_s: int = 60,
) -> Optional[List[StorageSlot]]:
    """Execute `forge inspect <contract_name> storage-layout --json` in project_dir."""
    cmd = [forge_bin, "inspect", contract_name, "storage-layout", "--json"]
    if solc:
        cmd += ["--use", solc]

    try:
        proc = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return parse_storage_layout_json(proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def verify_storage_layout_preservation(
    original_slots: List[StorageSlot],
    patched_slots: List[StorageSlot],
) -> Tuple[bool, List[str]]:
    """Verify that a patch preserves existing storage variable slots, offsets, and types.

    Rules enforced:
      1. Zero-Deletion: Every variable in original contract must exist in patched contract.
      2. Zero-Shift: Original variable slot and byte-offset must be identical.
      3. Type Integrity: Original variable type must not mutate (e.g. uint256 -> uint128).
      4. Safe Append: New state variables must not occupy or overwrite existing slots.

    Returns:
        (preserved, list_of_violations)
    """
    violations: List[str] = []

    def slot_key(s: StorageSlot) -> str:
        return f"{s.contract}:{s.label}" if s.contract else s.label

    orig_map: Dict[str, StorageSlot] = {slot_key(s): s for s in original_slots}
    patched_map: Dict[str, StorageSlot] = {slot_key(s): s for s in patched_slots}

    # 1. Check all original variables are preserved exactly
    for key, orig_s in orig_map.items():
        if key not in patched_map:
            violations.append(
                f"Storage variable '{orig_s.label}' was removed in patch (expected slot {orig_s.slot}, offset {orig_s.offset})"
            )
            continue

        patched_s = patched_map[key]
        if orig_s.slot != patched_s.slot:
            violations.append(
                f"Storage collision on '{orig_s.label}': slot changed from {orig_s.slot} to {patched_s.slot}"
            )
        elif orig_s.offset != patched_s.offset:
            violations.append(
                f"Storage byte-offset corrupted on '{orig_s.label}': offset changed from {orig_s.offset} to {patched_s.offset}"
            )

        if normalize_type_key(orig_s.type_name) != normalize_type_key(patched_s.type_name):
            violations.append(
                f"Storage type mutation on '{orig_s.label}': type changed from {orig_s.type_name} to {patched_s.type_name}"
            )
        elif orig_s.members_signature and patched_s.members_signature and orig_s.members_signature != patched_s.members_signature:
            violations.append(
                f"Storage struct member mutation on '{orig_s.label}': members changed from {orig_s.members_signature} to {patched_s.members_signature}"
            )

    # 2. Check that any newly added variables do not overwrite or collide into original slots
    if original_slots:
        occupied_locations = {(s.slot, s.offset) for s in original_slots}
        occupied_slots: set[int] = set()
        for s in original_slots:
            n_slots = max(1, (s.number_of_bytes + 31) // 32)
            for i in range(s.slot, s.slot + n_slots):
                occupied_slots.add(i)
        max_orig_slot = max(occupied_slots) if occupied_slots else 0

        for key, patched_s in patched_map.items():
            if key not in orig_map:
                n_slots = max(1, (patched_s.number_of_bytes + 31) // 32)
                new_slots = set(range(patched_s.slot, patched_s.slot + n_slots))
                colliding = new_slots.intersection(occupied_slots)
                if (patched_s.slot, patched_s.offset) in occupied_locations:
                    violations.append(
                        f"New variable '{patched_s.label}' collides into existing slot {patched_s.slot}:{patched_s.offset}"
                    )
                elif colliding:
                    violations.append(
                        f"New variable '{patched_s.label}' spans across existing occupied slot(s) {sorted(colliding)}"
                    )
                elif patched_s.slot < max_orig_slot:
                    violations.append(
                        f"New variable '{patched_s.label}' inserted before existing slot {max_orig_slot} (at slot {patched_s.slot})"
                    )

    passed = len(violations) == 0
    return (passed, violations)
