"""Model clients for the solver loop.

`ModelClient` is the interface the solver depends on. Two implementations:

  MetaModelClient  calls the Meta Model API (OpenAI-compatible chat/completions
                   shape; base URL, model and key are configurable). This is what
                   runs in the demo with a real key.
  ScriptedClient   returns canned responses in order — used to exercise the loop
                   (including the retry path) offline, with no key and no network.

A response is always the raw assistant text; parsing into patch+PoC lives in the
solver so every client goes through the same extraction.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol


class ModelClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


class ClientStop(Exception):
    """The client cannot serve another completion. The solve loop stops and keeps
    any attempts already graded. The arena raises this when the request cap is hit."""

    def __init__(self, reason: str = "stopped"):
        super().__init__(reason)
        self.reason = reason


def usage_from_response(data: object) -> dict:
    """OpenAI-style usage, normalised to prompt/completion counts. Missing usage is zero."""
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {"prompt": 0, "completion": 0}

    def num(key: str) -> int:
        try:
            return int(usage.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    return {"prompt": num("prompt_tokens"), "completion": num("completion_tokens")}


def checked_max_tokens(value: int | None) -> int | None:
    """A positive completion cap, or None when the request should not set one."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_tokens must be a positive integer, or unset for no client limit")
    return value


def max_tokens_from_env() -> int | None:
    """META_MAX_TOKENS. Unset or empty means the request omits max_tokens."""
    raw = os.environ.get("META_MAX_TOKENS")
    if raw is None or raw.strip() == "":
        return None
    try:
        parsed = int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            "META_MAX_TOKENS must be a positive integer, or unset for no client limit"
        ) from exc
    return checked_max_tokens(parsed)


class MetaModelClient:
    """Meta Model API client (OpenAI-compatible /chat/completions).

    The HTTP timeout defaults to 300s. ``META_MAX_TOKENS``, when set to a
    positive integer, is sent as ``max_tokens``; unset means no client cap.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: int = 300,
        max_tokens: int | None = None,
        temperature: float = 0.2,
    ):
        # META_API_KEY is this repo's name. MODEL_API_KEY is accepted because some
        # Meta quickstarts export that name instead.
        self.api_key = api_key or os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY") or ""
        self.base_url = (base_url or os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")).rstrip("/")
        self.model = model or os.environ.get("META_MODEL", "muse-spark-1.1")
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.last_usage = {"prompt": 0, "completion": 0}
        # An explicit argument wins. None reads META_MAX_TOKENS (unset = no cap).
        self.max_tokens = checked_max_tokens(max_tokens) if max_tokens is not None else max_tokens_from_env()
        if not self.api_key:
            raise RuntimeError(
                "No model API key. Set META_API_KEY (this repo's name) or MODEL_API_KEY "
                "(accepted alias). For an offline demo, re-run with --oracle."
            )

    def completion_payload(self, system: str, user: str) -> dict:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        return payload

    def complete(self, system: str, user: str) -> str:
        payload = self.completion_payload(system, user)
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Reasoning models can return content=null when the reply is cut off.
        # Hand the solver an empty string so it takes the unparseable-retry path
        # instead of crashing on None.strip(). Token counts stay on `last_usage`
        # (zero when the provider omits `usage`). The API key is not logged.
        self.last_usage = usage_from_response(data)
        return message_text(data["choices"][0]["message"])

    def __repr__(self) -> str:
        return f"MetaModelClient(model={self.model!r}, base_url={self.base_url!r})"


def message_text(message: object) -> str:
    """Assistant text from a chat message. Missing or null content is ""."""
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    return ""


class ScriptedClient:
    """Returns the given responses in order; repeats the last one if exhausted.

    Lets the solver loop run end-to-end offline. Pass a failing response first and
    a correct one second to demonstrate the feedback/retry path.
    """

    def __init__(self, responses: list[str]):
        if not responses:
            raise ValueError("ScriptedClient needs at least one response")
        self._responses = responses
        self._i = 0

    def complete(self, system: str, user: str) -> str:
        r = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return r
