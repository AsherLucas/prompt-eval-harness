"""Provider adapters.

StubProvider is for offline demos, tests, and CI: it returns a canned
output per case id, or the case's ``stub_output`` field. It never calls
a network.

OpenAICompatibleProvider talks to any OpenAI-compatible
``/chat/completions`` endpoint over stdlib urllib. The API key is read
from an environment variable at call time, is never hardcoded, and is
never logged -- only the fact that a key was missing is reported.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class Provider(Protocol):
    name: str

    def complete(self, case_id: str, prompt: str) -> str: ...


class StubProvider:
    """Return canned outputs, keyed by case id."""

    name = "stub"

    def __init__(self, outputs: dict[str, str] | None = None):
        self.outputs = dict(outputs or {})

    def complete(self, case_id: str, prompt: str) -> str:
        if case_id in self.outputs:
            return self.outputs[case_id]
        return f"stub response for {case_id}"


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat-completions client (stdlib only)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.name = f"openai-compatible:{model}"

    def complete(self, case_id: str, prompt: str) -> str:
        api_key = os.environ.get(self.api_key_env, "")
        if not api_key:
            raise ProviderError(
                f"environment variable {self.api_key_env} is not set; "
                "set it (do not paste a key into a case file or log) "
                "or use --provider stub for offline runs"
            )
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"provider returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"provider request failed: {exc.reason}") from exc
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("provider response had an unexpected shape") from exc
