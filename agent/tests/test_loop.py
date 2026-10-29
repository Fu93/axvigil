"""Offline loop tests: null model content, retry prompts, and JSON output."""

from __future__ import annotations

import json
from pathlib import Path

from axvigil_agent.model import message_text
from axvigil_agent.prompts import build_retry_prompt, build_user_prompt
from axvigil_agent.solver import solve
from axvigil_agent.__main__ import _outcome_payload


def test_null_content_is_empty_string():
    assert message_text({"content": None}) == ""
    assert message_text({}) == ""
    assert message_text({"content": "ok"}) == "ok"
    assert message_text(None) == ""


def test_user_prompt_states_the_line_budget():
    text = build_user_prompt(
        challenge_id="signature-replay-7", target_file="Vault.sol", contract_name="Vault",
        vuln_class_name="access control", pragma="0.8.28", source="contract Vault {}",
        required_functions=["release"], limits={"maxChangedLines": 6, "maxBytes": 6000},
    )
    assert "at most 6 changed lines" in text
    assert "6000 bytes" in text
    assert "contract Vault {}" in text


def test_unparseable_retry_keeps_the_challenge_source(tmp_path):
    source = "contract Vault { function release() external {} }\n"
    challenge = tmp_path / "chal"
    (challenge / "src").mkdir(parents=True)
    (challenge / "src" / "Vault.sol").write_text(source)
    (challenge / "challenge.json").write_text(json.dumps({
        "challengeId": "demo",
        "targetFile": "Vault.sol",
        "contractName": "Vault",
        "vulnClass": 2,
        "requiredFunctions": ["release"],
        "pragma": "0.8.28",
        "limits": {"maxChangedLines": 6, "maxBytes": 6000},
    }))

    class Recording:
        def __init__(self):
            self.users: list[str] = []

        def complete(self, system: str, user: str) -> str:
            self.users.append(user)
            return "not json at all"

    client = Recording()
    outcome = solve(client, challenge, max_iters=2)
    assert outcome.solved is False
    assert len(client.users) == 2
    assert source.strip() in client.users[1]
    assert "at most 6 changed lines" in client.users[1]


def test_retry_prompt_includes_source_and_limits_not_only_the_failed_patch():
    text = build_retry_prompt(
        prev_patch="contract Vault { }", prev_poc="contract T { }",
        result_log="hiddenTestsPass: 1/2 tests passed",
        checks={"pocProvesBug": True, "hiddenTestsPass": False, "pocFailsAfterPatch": True,
                "patchWithinLimits": True},
        source="contract Vault { function release() external {} }",
        limits={"maxChangedLines": 6, "maxBytes": 4000},
    )
    assert "function release()" in text
    assert "at most 6 changed lines" in text
    assert "test_hiddenName" not in text


def test_json_payload_includes_analysis_and_patch():
    from axvigil_agent.solver import Iteration, SolveOutcome
    outcome = SolveOutcome(
        challenge_id="c", solved=True, solve_seconds=3,
        final_patch="patch", final_poc="poc", final_result={"passed": True},
        iterations=[Iteration(0, "because reentrancy", True, {"pocProvesBug": True}, "log", "0xabc")],
    )
    payload = _outcome_payload(outcome)
    assert payload["iterations"][0]["analysis"] == "because reentrancy"
    assert payload["finalPatch"] == "patch"
    assert payload["finalPoc"] == "poc"
