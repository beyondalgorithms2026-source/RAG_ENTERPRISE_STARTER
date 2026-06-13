# AR11 — Cost, Token, And Latency Governance (Gate AR11: the cost half of "latency/cost traces")

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR11

## Audit finding remediated

"The original plan promised 'latency/cost traces'; the audit found latency
delivered and cost entirely absent. No token counting, no per-request cost
estimate, no per-profile cost rollups, no budget alerts anywhere in traces,
eval reports, or the console. The only budget mechanism was the reranker latency
budget."

## What was built

- **Token usage per generation call** (`app/llm/providers.py::extract_usage` +
  `client._build_usage`): provider-reported usage where available (OpenAI/Azure
  `usage`, Anthropic `input_tokens`/`output_tokens`, Ollama
  `prompt_eval_count`/`eval_count`); otherwise estimated via a documented
  heuristic (`pricing.py`, ceil(len/4) chars-per-token) and flagged
  `estimated: true` so a guess is never shown as a measurement.
- **Configurable price table** (`app/llm/pricing.py`): per-1K-token input/output
  USD, overridable via `LLM_PRICE_TABLE_JSON`; unknown/local models cost $0.
- **Request-scoped accumulation** (`app/llm/usage.py`, ContextVar): a single
  answer's primary + JSON-repair + second-pass calls are summed into one
  token/cost figure, attached to the retrieval trace as `generation_usage`.
- **Persisted usage events + rollups** (`MIG-P024` `generation_usage_events`,
  `repo_generation_usage.py`): every answered request records provider, model,
  retrieval mode, answer path, tokens, cost, latency, and an over-budget flag.
  `GET /admin/cost/summary?group_by=retrieval_mode|model|provider` rolls them up.
- **Budget alerting**: `LLM_COST_ALERT_USD` (0 disables) flags over-budget
  events and emits a `cost.budget_exceeded` admin audit event.
- **Sandbox compare deltas**: the compare summary now carries
  `cost_delta_usd`/`token_delta` and per-run `generation_usage` alongside the
  latency delta.
- **Console**: `/console/admin/cost` shows totals + a per-mode/model/provider
  table (cost, tokens, avg latency, over-budget count, est. flag) — the operator
  can read "deep research vs fast mode cost" directly.

## DoD check

- An operator can answer "what does deep research cost vs fast mode" from the
  console ✓ — `cost_summary(group_by="retrieval_mode")` separates
  `deep_research` from `hybrid` with per-bucket cost
  (`tests/test_cost_governance_ar11.py`), surfaced on the cost page.
- Token counts recorded into traces (provider-reported or estimated, method
  documented) ✓; budget threshold raises an alert event ✓.
- Re-run checks: pricing/usage/provider-extraction/rollup/budget tests; full
  suite **302/302**; `tsc --noEmit` clean; `docs/02` untouched; ledger
  `MIG-P001..P024` reconciled.

## Honest limits

- Cloud price-table defaults are illustrative starting points operators must
  tune; with the configured local `gpt-oss` model (unpriced) cost rolls up as
  $0 while tokens/latency are still tracked.
- Estimated token counts (no provider usage) are character-heuristic
  approximations, always flagged `est.`; they are directional, not billing-grade.
- Eval-report cost embedding (AR3 reports) is not wired here — usage flows
  through traces and the cost endpoint; per-eval cost is future work.

**Next:** AR12 — Feedback-To-Eval Flywheel.
