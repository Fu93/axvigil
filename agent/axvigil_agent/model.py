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


class MetaModelClient:
    """Meta Model API client (OpenAI-compatible /chat/completions)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: int = 120,
    ):
        self.api_key = api_key or os.environ.get("META_API_KEY", "")
        self.base_url = (base_url or os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")).rstrip("/")
        self.model = model or os.environ.get("META_MODEL", "muse-spark-1.1")
        self.timeout_s = timeout_s
        if not self.api_key:
            raise RuntimeError("META_API_KEY not set")

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
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
        return data["choices"][0]["message"]["content"]


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
