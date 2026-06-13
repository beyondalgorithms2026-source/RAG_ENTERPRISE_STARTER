"""Pluggable LLM provider registry (AR9).

The audit found `llm/client.py` supported exactly two providers (`ollama`,
`ollama_cloud`) with payload shapes inlined in `generate_answer`; the
`LLMProfileConfig.provider` field implied a pluggability that did not exist.
Each provider here encapsulates its endpoint, request shape, JSON-mode handling,
and response extraction so that switching to a sanctioned enterprise endpoint
(OpenAI, Azure OpenAI, vLLM, Anthropic) is a profile change, not a code edit.

The strict-JSON answer contract, repair passes, and approved-model registry are
unchanged: providers only move bytes; `app.core_rag.answering` still parses,
validates, repairs, and enforces citations on whatever text comes back.
"""
from typing import Any


class LLMProvider:
    name = "base"
    # Whether this provider/model can request native JSON object output. When
    # False the provider is effectively prompt-JSON-only and the answering layer
    # extracts JSON from free text (the GPT-OSS deterministic path).
    supports_native_json = False

    def chat_url(self, base: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def models_url(self, base: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def headers(self, llm, base_headers: dict) -> dict:
        return base_headers

    def build_payload(self, llm, system_prompt: str, user_prompt: str, *, json_mode: bool, temperature: float, max_tokens: Any) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def extract_content(self, data: dict) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def verify_models(self, data: dict, model: str) -> bool:
        return True

    def extract_usage(self, data: dict):
        """Return (prompt_tokens, completion_tokens) if the provider reports usage, else None."""
        return None


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI Chat Completions shape — covers OpenAI, Azure OpenAI, vLLM, and
    local Ollama (which exposes /v1/chat/completions)."""

    name = "openai_compatible"
    supports_native_json = True

    def chat_url(self, base: str) -> str:
        return f"{base}/v1/chat/completions"

    def models_url(self, base: str) -> str:
        return f"{base}/v1/models"

    def build_payload(self, llm, system_prompt, user_prompt, *, json_mode, temperature, max_tokens):
        payload: dict[str, Any] = {
            "model": llm.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": llm.top_p,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if getattr(llm, "reasoning_effort", None):
            payload["reasoning_effort"] = llm.reasoning_effort
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        return payload

    def extract_content(self, data):
        return data["choices"][0]["message"]["content"]

    def verify_models(self, data, model):
        models = data.get("models") or data.get("data") or []
        model_ids = [m.get("id") or m.get("name") for m in models]
        return any(model in (mid or "") for mid in model_ids)

    def extract_usage(self, data):
        usage = data.get("usage") or {}
        if "prompt_tokens" in usage or "completion_tokens" in usage:
            return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
        # Ollama's /v1 shape sometimes reports native eval counts instead.
        if "prompt_eval_count" in data or "eval_count" in data:
            return int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)
        return None


class OllamaNativeProvider(LLMProvider):
    """Ollama's native /chat API (the existing `ollama_cloud` path)."""

    name = "ollama_cloud"
    supports_native_json = False

    def chat_url(self, base: str) -> str:
        return f"{base}/chat"

    def models_url(self, base: str) -> str:
        return f"{base}/tags"

    def build_payload(self, llm, system_prompt, user_prompt, *, json_mode, temperature, max_tokens):
        payload: dict[str, Any] = {
            "model": llm.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": temperature, "top_p": llm.top_p},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        return payload

    def extract_content(self, data):
        return (data.get("message") or {}).get("content", "")

    def verify_models(self, data, model):
        # Reachable is ready: cloud tag listings can lag behind available models.
        return True

    def extract_usage(self, data):
        if "prompt_eval_count" in data or "eval_count" in data:
            return int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0)
        return None


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API. No native json_object flag — relies on the
    prompt-JSON contract, like the GPT-OSS deterministic path."""

    name = "anthropic"
    supports_native_json = False

    def chat_url(self, base: str) -> str:
        return f"{base}/v1/messages"

    def models_url(self, base: str) -> str:
        return f"{base}/v1/models"

    def headers(self, llm, base_headers):
        headers = dict(base_headers)
        headers.pop("Authorization", None)
        if llm.api_key:
            headers["x-api-key"] = llm.api_key
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def build_payload(self, llm, system_prompt, user_prompt, *, json_mode, temperature, max_tokens):
        return {
            "model": llm.model,
            "max_tokens": int(max_tokens or 1024),
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

    def extract_content(self, data):
        blocks = data.get("content") or []
        return "".join(block.get("text", "") for block in blocks if isinstance(block, dict))

    def verify_models(self, data, model):
        return True

    def extract_usage(self, data):
        usage = data.get("usage") or {}
        if "input_tokens" in usage or "output_tokens" in usage:
            return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        return None


_PROVIDERS: dict[str, LLMProvider] = {}


def register_provider(provider: LLMProvider) -> None:
    _PROVIDERS[provider.name] = provider


_OPENAI_ALIASES = ("openai_compatible", "openai", "ollama", "vllm", "azure_openai")
for _alias in _OPENAI_ALIASES:
    _PROVIDERS[_alias] = OpenAICompatibleProvider()
register_provider(OllamaNativeProvider())
register_provider(AnthropicProvider())


def get_provider(name: str) -> LLMProvider:
    provider = _PROVIDERS.get(str(name or "").strip().lower())
    if provider is None:
        raise ValueError(f"Unknown LLM provider '{name}'. Known: {sorted(_PROVIDERS)}")
    return provider


def supported_providers() -> list[str]:
    return sorted(_PROVIDERS)
