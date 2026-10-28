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
import time
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
        self.last_usage: dict = {}

    def complete(self, case_id: str, prompt: str) -> str:
        if case_id in self.outputs:
            return self.outputs[case_id]
        return f"stub response for {case_id}"


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat-completions client (stdlib only).

    Retries transient failures (HTTP 429 and 5xx, plus network errors)
    with exponential backoff; other HTTP errors fail immediately with a
    clear message. ``last_usage`` holds the most recent response's
    ``usage`` dict (tokens), or {} when the provider reports none.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        timeout: float = 60.0,
        max_retries: int = 2,
        require_key: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.require_key = require_key
        self.name = f"openai-compatible:{model}"
        self.last_usage: dict = {}

    def complete(self, case_id: str, prompt: str) -> str:
        api_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if not api_key and self.require_key:
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
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=payload, headers=headers, method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode())
                self.last_usage = dict(body.get("usage") or {})
                try:
                    return str(body["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError) as exc:
                    raise ProviderError("provider response had an unexpected shape") from exc
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code not in (429, 500, 502, 503, 504) or attempt == self.max_retries:
                    raise ProviderError(f"provider returned HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt == self.max_retries:
                    raise ProviderError(f"provider request failed: {exc.reason}") from exc
            time.sleep(0.5 * (2 ** attempt))
        raise ProviderError(f"provider request failed after retries: {last_exc}")


class OllamaCompatibleProvider(OpenAICompatibleProvider):
    """Local-model provider speaking the OpenAI-compatible API.

    Defaults to a local Ollama server (http://localhost:11434/v1) and
    does not require an API key. Any OpenAI-compatible local server on
    the same interface works the same way via --base-url.
    """

    def __init__(self, base_url: str = "http://localhost:11434/v1",
                 model: str = "llama3.1", timeout: float = 120.0,
                 max_retries: int = 1):
        super().__init__(base_url=base_url, model=model, api_key_env="",
                         timeout=timeout, max_retries=max_retries, require_key=False)
        self.name = f"ollama:{model}"
