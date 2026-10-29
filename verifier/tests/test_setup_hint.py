"""Compiler-failure notes must explain a missing solc without quoting hidden tests."""

from axvigil_verifier.forge_runner import (
    compile_failure_note,
    environment_failure,
    solc_setup_hint,
)


def test_offline_solc_hint_names_forge_build():
    raw = "Error: can't install missing solc 0.8.28 in offline mode\n"
    hint = solc_setup_hint(raw)
    assert hint is not None and "forge build" in hint
    note = compile_failure_note(raw, include_error_line=False)
    assert "forge build" in note
    assert "test_" not in note


def test_hidden_suite_omits_the_compiler_line():
    raw = "Error (6933): Expected primary expression.\n --> test/Hidden.t.sol:2:10:\n"
    assert compile_failure_note(raw, include_error_line=False) == ""
    shown = compile_failure_note(
        "Error: failed /tmp/secret/Hidden.t.sol\n", include_error_line=True,
    )
    assert "<path>" in shown
    assert "/tmp" not in shown


def test_environment_failure_detects_setup_and_ignores_a_real_miss():
    assert environment_failure("pocProvesBug: compile failed — the Solidity compiler is not available yet.")
    assert environment_failure("pocProvesBug: forge was not found on PATH.")
    assert not environment_failure("pocProvesBug: 0/1 tests passed")
