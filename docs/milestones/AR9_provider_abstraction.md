# AR9 — Provider Abstraction For Generation (Gate AR9: bring-your-own-model)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR9

## Audit finding remediated

"`backend/app/llm/client.py` supported exactly two providers: `ollama` and
`ollama_cloud`, with provider-specific payload shapes inlined in
`generate_answer`. Any other provider required editing the client. The
`LLMProfileConfig.provider` field implied a pluggability that did not exist."
The audit flagged Ollama-only support as an adoption blocker.

## What was built

- **Pluggable provider registry** (`app/llm/providers.py`): each provider
  encapsulates its endpoint, request shape, JSON-mode capability, response
  extraction, and preflight model check.
  - `OpenAICompatibleProvider` (Chat Completions `/v1/chat/completions`) covers
    **OpenAI, Azure OpenAI, vLLM, and local Ollama** — registered under
    `openai`, `openai_compatible`, `vllm`, `azure_openai`, `ollama`.
  - `OllamaNativeProvider` preserves the existing `ollama_cloud` `/chat` shape.
  - `AnthropicProvider` (`/v1/messages`, `x-api-key` + `anthropic-version`).
  - `get_provider(name)` resolves by `LLMProfileConfig.provider`;
    `supported_providers()` lists them (exposed at `GET /admin/llm/providers`).
- **Client delegates, contract unchanged** (`app/llm/client.py`): a single
  `_provider_generate` path backs both `generate_answer` (300 s floor, JSON
  mode unless `prompt_json_only`) and `generate_transform_text` (AR5 short
  budget, plain text). `verify_llm_ready` is generalized per provider.
- **`structured_output_mode` honored per provider capability**: native JSON
  object output is requested only when the provider supports it *and* the model
  isn't `prompt_json_only`. Anthropic and Ollama-native have
  `supports_native_json = False`, so they ride the prompt-JSON contract — the
  same path GPT-OSS already uses. The deterministic GPT-OSS behaviour is
  byte-for-byte unchanged (regression suite green).
- **Approved-model registry gating is untouched**: which provider/model
  combinations are *selectable* is still governed by the registry
  (`is_registry_approved_profile`); AR9 only makes the wire protocol pluggable.

## DoD check

- Switching to a non-Ollama endpoint is only a profile change ✓ — proven by
  driving the full `generate_answer` contract against two provider shapes
  (OpenAI-compatible and Anthropic) with a mocked transport: same call, JSON
  parsed, citations intact, repair path available
  (`tests/test_provider_abstraction_ar9.py`).
- Answer-contract + GPT-OSS compatibility tests pass unchanged ✓
  (`test_gpt_oss_json_compatibility`, `test_smoke_router_compare_eval` green;
  existing tests stub `generate_answer` above the provider seam, so they were
  unaffected).
- Re-run checks: full suite **286/286**; `docs/02` untouched.

## Honest limits

- Anthropic/OpenAI/Azure/vLLM paths are validated against mocked transports
  (no live keys in this environment); the request shapes follow each provider's
  documented API. Ollama (local + cloud) remains the only path exercised
  end-to-end against a real endpoint.
- Per-provider token/cost accounting is out of scope here — that is AR11.

**Next:** AR10 — Operator Health And Trust Dashboard.
