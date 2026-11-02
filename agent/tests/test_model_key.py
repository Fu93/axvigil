"""META_API_KEY is the repo name; MODEL_API_KEY is the documented alias."""

import pytest

from axvigil_agent.model import MetaModelClient


def test_model_api_key_is_accepted_alias(monkeypatch):
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "alias-key")
    assert MetaModelClient().api_key == "alias-key"


def test_meta_api_key_wins_over_alias(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "primary")
    monkeypatch.setenv("MODEL_API_KEY", "alias")
    assert MetaModelClient().api_key == "primary"


def test_http_timeout_defaults_to_300_seconds(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.delenv("META_MAX_TOKENS", raising=False)
    assert MetaModelClient().timeout_s == 300
    assert MetaModelClient(timeout_s=10).timeout_s == 10


def test_unset_max_tokens_is_omitted(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.delenv("META_MAX_TOKENS", raising=False)
    body = MetaModelClient().completion_payload("sys", "user")
    assert "max_tokens" not in body
    monkeypatch.setenv("META_MAX_TOKENS", "  ")
    assert "max_tokens" not in MetaModelClient().completion_payload("sys", "user")


def test_meta_max_tokens_is_sent(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("META_MAX_TOKENS", "4096")
    body = MetaModelClient().completion_payload("sys", "user")
    assert body["max_tokens"] == 4096
    # An explicit argument wins over the environment.
    override = MetaModelClient(max_tokens=128).completion_payload("sys", "user")
    assert override["max_tokens"] == 128


def test_bad_meta_max_tokens_is_rejected(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("META_MAX_TOKENS", "lots")
    with pytest.raises(ValueError):
        MetaModelClient()
    monkeypatch.setenv("META_MAX_TOKENS", "0")
    with pytest.raises(ValueError):
        MetaModelClient()


def test_missing_key_names_both_variables(monkeypatch):
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as raised:
        MetaModelClient()
    text = str(raised.value)
    assert "META_API_KEY" in text and "MODEL_API_KEY" in text
    assert "--oracle" in text
