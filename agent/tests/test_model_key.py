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


def test_missing_key_names_both_variables(monkeypatch):
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as raised:
        MetaModelClient()
    text = str(raised.value)
    assert "META_API_KEY" in text and "MODEL_API_KEY" in text
    assert "--oracle" in text
