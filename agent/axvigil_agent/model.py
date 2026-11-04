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
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
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
        max_attempts = 3
        backoff = 2.0
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                # Reasoning models can return content=null when the reply is cut off.
                # Hand the solver an empty string so it takes the unparseable-retry path
                # instead of crashing on None.strip(). Token counts stay on `last_usage`
                # (zero when the provider omits `usage`). The API key is not logged.
                self.last_usage = usage_from_response(data)
                return message_text(data["choices"][0]["message"])
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise
        if last_exc:
            raise last_exc
        return ""

    def complete_turn(self, messages: list[dict], *, tools: list[dict] | None = None) -> ModelTurn:
        """One chat completion, optionally with OpenAI `tools`.

        The Meta base URL speaks the OpenAI chat-completions shape, including
        the `tools` field. Whether a given Muse Spark build returns `tool_calls`
        is selected by the caller: pass `tools` for that format, or omit them
        and read a JSON action from the text. The API key is not logged.
        """
        payload: dict = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
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
        self.last_usage = usage_from_response(data)
        message = data["choices"][0]["message"]
        return parse_assistant_message(message)

    def __repr__(self) -> str:
        return f"MetaModelClient(model={self.model!r}, base_url={self.base_url!r})"


@dataclass
class ToolCall:
    """One function call from an assistant turn. ``error`` is set when the call is malformed."""

    id: str
    name: str
    arguments: dict | None
    error: str | None = None


@dataclass
class ModelTurn:
    """A chat completion as the agent loop sees it.

    ``message`` is the assistant object to append when the next request must
    echo tool_calls (OpenAI format). ``text`` is the plain content.
    """

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: dict = field(default_factory=dict)


def parse_assistant_message(message: object) -> ModelTurn:
    """Split an OpenAI-style assistant message into text and tool calls.

    A tool call whose ``arguments`` are not a JSON object is kept, with
    ``error`` set, so the loop can record it instead of crashing.
    """
    if not isinstance(message, dict):
        return ModelTurn(text="", message={"role": "assistant", "content": ""})
    text = message_text(message)
    calls: list[ToolCall] = []
    raw_calls = message.get("tool_calls") or []
    if isinstance(raw_calls, list):
        for index, item in enumerate(raw_calls):
            calls.append(_parse_one_tool_call(item, index))
    echoed = {"role": "assistant", "content": text or None}
    if calls and isinstance(raw_calls, list):
        echoed["tool_calls"] = raw_calls
    return ModelTurn(text=text, tool_calls=calls, message=echoed)


def _parse_one_tool_call(item: object, index: int) -> ToolCall:
    call_id = f"call_{index}"
    if not isinstance(item, dict):
        return ToolCall(call_id, "", None, "malformed tool call")
    if item.get("id"):
        call_id = str(item["id"])
    function = item.get("function") if isinstance(item.get("function"), dict) else {}
    name = str(function.get("name") or item.get("name") or "")
    raw_args = function.get("arguments", item.get("arguments"))
    if not name:
        return ToolCall(call_id, "", None, "malformed tool call")
    if raw_args is None or raw_args == "":
        return ToolCall(call_id, name, {})
    if isinstance(raw_args, dict):
        return ToolCall(call_id, name, raw_args)
    if not isinstance(raw_args, str):
        return ToolCall(call_id, name, None, "arguments are not JSON")
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError:
        return ToolCall(call_id, name, None, "arguments are not JSON")
    if not isinstance(parsed, dict):
        return ToolCall(call_id, name, None, "arguments are not a JSON object")
    return ToolCall(call_id, name, parsed)


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
