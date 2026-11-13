import json
import stat
import subprocess
import sys
from pathlib import Path

from axvigil_near.keys import b58decode, b58encode, write_key_file
from axvigil_near.redact import assert_no_secret, redact, transaction_id
from axvigil_near.rpc import access_key_summary, assert_testnet_account, assert_testnet_rpc
from axvigil_near.seal import anchor_args, canonical_json, seal_from_result

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_base58_known_vectors():
    from axvigil_near.keys import b58decode

    assert b58encode(b"") == ""
    assert b58encode(b"\x00") == "1"
    assert b58encode(b"hello") == "Cn8eVZg"
    blob = bytes(range(32))
    assert b58decode(b58encode(blob)) == blob


def test_seal_ignores_the_grader_log_and_pins_the_bundle():
    result = json.loads((FIXTURES / "pass.json").read_text())
    seal = seal_from_result(result)
    changed = dict(result)
    changed["log"] = "different log"
    assert seal_from_result(changed)["bundle_sha256"] == seal["bundle_sha256"]
    assert seal["evidence_hash"] == "a" * 64
    assert seal["passed"] is True
    body = json.loads(seal["canonical"])
    assert list(body) == sorted(body)
    assert canonical_json(body) == seal["canonical"].encode()
    assert seal["bundle_sha256"] == "9c90f3166171bc962269b51f9bdb6940527f544d1b56c9238c37279fbb0988dd"
    fail = seal_from_result(json.loads((FIXTURES / "fail.json").read_text()))
    assert fail["bundle_sha256"] == "f4ef473c073d46c344a1fb125fbf313ed37f7c281d016cfb74bde4d55e94c9e4"


def test_failing_grade_needs_claim_pass_and_does_not_change_the_bundle():
    seal = seal_from_result(json.loads((FIXTURES / "fail.json").read_text()))
    assert seal["passed"] is False
    assert seal["evidence_hash"] == "b" * 64
    try:
        anchor_args(seal, 90, claim_pass=False)
    except ValueError as exc:
        assert "failing grade" in str(exc)
    else:
        raise AssertionError("failing grade was anchored")
    claimed = anchor_args(seal, 90, claim_pass=True)
    assert claimed["passed"] is True
    assert claimed["bundle_sha256"] == seal["bundle_sha256"]
    assert claimed["evidence_hash"] == seal["evidence_hash"]
    assert claimed["window_seconds"] == 90
    rust = (ROOT / "near" / "contract" / "src" / "lib.rs").read_text()
    for key in claimed:
        assert key in rust


def test_bad_submission_hash_rejected():
    result = json.loads((FIXTURES / "pass.json").read_text())
    result["submissionHash"] = "0x1234"
    try:
        seal_from_result(result)
    except ValueError as exc:
        assert "submissionHash" in str(exc)
    else:
        raise AssertionError("short hash was accepted")


def test_rpc_and_account_guards():
    assert assert_testnet_rpc("https://rpc.testnet.near.org")
    for blocked in (
        "https://rpc.mainnet.near.org",
        "http://rpc.testnet.near.org",
        "https://rpc.testnet.near.org.evil.example",
        "https://example.com",
    ):
        try:
            assert_testnet_rpc(blocked)
        except ValueError:
            pass
        else:
            raise AssertionError(blocked)
    assert assert_testnet_account("agent.example.testnet") == "agent.example.testnet"
    for blocked in ("team.near", "owner.mainnet", "not an account", "ABC.testnet"):
        try:
            assert_testnet_account(blocked)
        except ValueError:
            pass
        else:
            raise AssertionError(blocked)


def test_write_key_keeps_the_secret_off_stdout(tmp_path):
    path = tmp_path / "scoped.json"
    public = write_key_file("agent.example.testnet", path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
    stored = json.loads(path.read_text())
    assert stored["public_key"] == public
    assert stored["private_key"].startswith("ed25519:")
    assert stored["private_key"] != public
    secret_raw = b58decode(stored["private_key"].split(":", 1)[1])
    public_raw = b58decode(public.split(":", 1)[1])
    assert len(secret_raw) == 64
    assert secret_raw[32:] == public_raw
    assert public.startswith("ed25519:")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "axvigil_near",
            "write-key",
            "--account",
            "agent.example.testnet",
            "--out",
            str(tmp_path / "cli.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    secret = json.loads((tmp_path / "cli.json").read_text())["private_key"]
    assert secret not in proc.stdout
    assert secret not in proc.stderr
    assert proc.stdout.strip() == json.loads((tmp_path / "cli.json").read_text())["public_key"]


def test_redact_strips_private_key_and_keeps_public_key():
    public = "ed25519:publickeyexamplevalue111111111111111111111111111111"
    raw = "\n".join(
        [
            f"Public key: {public}",
            '{"private_key": "ed25519:SECRETVALUE111111111111111111111111111111111111"}',
            "Transaction ID: ABCDEFGH1234567890",
            "https://testnet.nearblocks.io/txns/ABCDEFGH1234567890",
        ]
    )
    cleaned = redact(raw)
    assert "SECRETVALUE" not in cleaned
    assert public in cleaned
    assert_no_secret(cleaned)
    assert transaction_id(raw) == "ABCDEFGH1234567890"
    try:
        assert_no_secret(raw)
    except SystemExit:
        pass
    else:
        raise AssertionError("unredacted log was accepted")


def test_published_testnet_seals_match_the_deployment_record():
    seals = ROOT / "docs" / "near" / "seals"
    deployment = json.loads((ROOT / "docs" / "near" / "deployment.json").read_text())
    view = json.loads((ROOT / "docs" / "near" / "view.json").read_text())
    honest = json.loads((seals / "honest-seal.json").read_text())
    bad = json.loads((seals / "bad-seal.json").read_text())
    assert honest["passed"] is True
    assert bad["passed"] is False
    assert hashlib_sha(seals / "honest.canonical.json") == honest["bundle_sha256"]
    assert hashlib_sha(seals / "bad.canonical.json") == bad["bundle_sha256"]
    assert deployment["honest_evidence_hash"] == honest["evidence_hash"]
    assert deployment["bad_bundle_sha256"] == bad["bundle_sha256"]
    assert deployment["network"] == "testnet"
    assert deployment["contract"].endswith(".testnet")
    assert view["honest"]["status"] == "Final"
    assert view["bad"]["status"] == "Revoked"
    assert view["reputation"]["finalized"] == 1
    assert view["reputation"]["revoked"] == 1
    assert view["reputation"]["is_valid"] is True
    claimed = json.loads((seals / "bad-anchor-args.json").read_text())
    assert claimed["passed"] is True
    assert claimed["bundle_sha256"] == bad["bundle_sha256"]
    assert "private_key" not in (ROOT / "docs" / "near" / "deployment.json").read_text()


def hashlib_sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_demo_script_is_testnet_only():
    script = (ROOT / "near" / "scripts" / "demo_testnet.sh").read_text()
    assert "I_UNDERSTAND_THIS_SENDS_TESTNET_TX" in script
    assert "network-config testnet" in script
    assert "network-config mainnet" not in script
    assert "sign-with-plaintext-private-key" not in script
    assert "anchor_evidence" in script
    assert "--claim-pass" in script
    assert "ready_at_ns" in script
    assert "mainnet" in script  # the refusal text


def test_function_call_key_summary_keeps_the_method_list():
    summary = access_key_summary({
        "permission": {
            "FunctionCall": {
                "allowance": "1",
                "method_names": ["anchor_evidence"],
                "receiver_id": "axvigil-rec-8735edcb.testnet",
            }
        }
    })
    assert summary["kind"] == "function_call"
    assert summary["method_names"] == ["anchor_evidence"]
    assert access_key_summary({"permission": "FullAccess"})["kind"] == "full_access"
