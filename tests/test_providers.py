import json

import pytest

from prompt_eval.providers import OpenAICompatibleProvider, ProviderError, StubProvider


def test_stub_provider_by_id_and_fallback():
    p = StubProvider({"a": "hello"})
    assert p.complete("a", "prompt") == "hello"
    assert "b" in p.complete("b", "prompt")


def test_openai_provider_missing_key(monkeypatch):
    monkeypatch.delenv("MY_TEST_KEY", raising=False)
    p = OpenAICompatibleProvider("https://example.invalid/v1", "m", api_key_env="MY_TEST_KEY")
    with pytest.raises(ProviderError, match="MY_TEST_KEY"):
        p.complete("x", "hi")


def test_openai_provider_parses_response(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "not-a-real-key")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "hi there"}}]}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp())
    p = OpenAICompatibleProvider("https://example.invalid/v1", "m", api_key_env="MY_TEST_KEY")
    assert p.complete("x", "hi") == "hi there"


def test_openai_provider_bad_shape(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "not-a-real-key")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"choices": []}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp())
    p = OpenAICompatibleProvider("https://example.invalid/v1", "m", api_key_env="MY_TEST_KEY")
    with pytest.raises(ProviderError):
        p.complete("x", "hi")
