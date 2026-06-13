import unittest

import app.llm.client as client
from app.llm.providers import (
    AnthropicProvider,
    OpenAICompatibleProvider,
    get_provider,
    supported_providers,
)
from app.profiles.models import LLMProfileConfig


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    """Captures the request and returns a canned provider-shaped response."""

    def __init__(self, capture, response):
        self._capture = capture
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, headers=None):
        self._capture["url"] = url
        self._capture["payload"] = json
        self._capture["headers"] = headers
        return self._response

    def get(self, url, headers=None):
        self._capture["url"] = url
        return self._response


class _FakeHttpx:
    TimeoutException = RuntimeError

    def __init__(self, capture, response):
        self._capture = capture
        self._response = response

    def Client(self, timeout=None):
        return _FakeClient(self._capture, self._response)


class ProviderRegistryAR9Tests(unittest.TestCase):
    def test_registry_resolves_providers_by_name(self):
        for name in ("openai", "ollama", "vllm", "azure_openai", "openai_compatible"):
            self.assertIsInstance(get_provider(name), OpenAICompatibleProvider)
        self.assertIsInstance(get_provider("anthropic"), AnthropicProvider)
        self.assertIn("anthropic", supported_providers())

    def test_unknown_provider_raises(self):
        with self.assertRaisesRegex(ValueError, "Unknown LLM provider"):
            get_provider("definitely-not-a-provider")

    def test_openai_payload_requests_json_object_when_supported(self):
        provider = OpenAICompatibleProvider()
        llm = LLMProfileConfig(provider="openai", model="gpt-4o-mini")
        payload = provider.build_payload(llm, "sys", "user", json_mode=True, temperature=0.0, max_tokens=128)
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["model"], "gpt-4o-mini")

    def test_anthropic_uses_messages_shape_and_api_key_header(self):
        provider = AnthropicProvider()
        llm = LLMProfileConfig(provider="anthropic", model="claude-haiku-4-5-20251001", api_key="sk-test")
        headers = provider.headers(llm, {"Content-Type": "application/json", "Authorization": "Bearer sk-test"})
        self.assertEqual(headers["x-api-key"], "sk-test")
        self.assertNotIn("Authorization", headers)
        self.assertIn("anthropic-version", headers)
        payload = provider.build_payload(llm, "sys", "user", json_mode=True, temperature=0.0, max_tokens=256)
        self.assertEqual(payload["system"], "sys")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "user"}])


class TwoProviderAnswerContractAR9Tests(unittest.TestCase):
    """AR9 DoD: switching to a non-Ollama endpoint is only a profile change; the
    same generate_answer contract holds against two provider shapes."""

    def setUp(self):
        self._orig_httpx = client._get_httpx
        self.addCleanup(lambda: setattr(client, "_get_httpx", self._orig_httpx))
        self._orig_resolver = None

    def _pin_llm(self, llm):
        import app.profiles.resolver as resolver

        original = resolver.get_effective_llm
        resolver.get_effective_llm = lambda: llm
        self.addCleanup(lambda: setattr(resolver, "get_effective_llm", original))

    def test_openai_compatible_answer(self):
        capture: dict = {}
        response = _FakeResponse({"choices": [{"message": {"content": '{"answer":"ok [S1]","citations":["S1"]}'}}]})
        client._get_httpx = lambda: _FakeHttpx(capture, response)
        self._pin_llm(LLMProfileConfig(provider="openai", model="gpt-4o-mini", base_url="https://api.openai.example", api_key="sk-x", structured_output_mode="native_json"))
        result = client.generate_answer("sys", "user")
        self.assertTrue(result["success"])
        self.assertIn('"answer"', result["content"])
        self.assertTrue(capture["url"].endswith("/v1/chat/completions"))
        self.assertEqual(capture["payload"]["response_format"], {"type": "json_object"})

    def test_anthropic_answer_same_contract(self):
        capture: dict = {}
        response = _FakeResponse({"content": [{"type": "text", "text": '{"answer":"ok [S1]","citations":["S1"]}'}]})
        client._get_httpx = lambda: _FakeHttpx(capture, response)
        self._pin_llm(LLMProfileConfig(provider="anthropic", model="claude-haiku-4-5-20251001", base_url="https://api.anthropic.example", api_key="sk-y"))
        result = client.generate_answer("sys", "user")
        self.assertTrue(result["success"])
        self.assertIn('"answer"', result["content"])
        self.assertTrue(capture["url"].endswith("/v1/messages"))
        self.assertEqual(capture["headers"]["x-api-key"], "sk-y")
        # Anthropic has no native json_object flag — must not be sent.
        self.assertNotIn("response_format", capture["payload"])

    def test_transform_text_is_provider_dispatched(self):
        capture: dict = {}
        response = _FakeResponse({"choices": [{"message": {"content": "rewritten query"}}]})
        client._get_httpx = lambda: _FakeHttpx(capture, response)
        self._pin_llm(LLMProfileConfig(provider="vllm", model="mistral", base_url="http://vllm.local:8000"))
        result = client.generate_transform_text("sys", "user", timeout_s=1.0)
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], "rewritten query")
        # Transform never requests JSON object mode.
        self.assertNotIn("response_format", capture["payload"])


if __name__ == "__main__":
    unittest.main()
