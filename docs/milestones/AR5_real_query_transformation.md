# AR5 — Replace Placeholder Query Transformation With A Real Implementation

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR5 (the flags do what they say)

## Audit finding remediated

`query_transform.py:9-43` was "scaffolding wearing governance clothing": M18
shipped governed admin controls, profile flags, sandbox visibility, and trace
fields around a stub. The stub was — verbatim from the audit — a hardcoded
5-entry synonym dict for "expansion" (`q4`, `liability`, `subcontracting`,
`budget`, `compensation`), whitespace normalization for "rewrite", and the
literal prefix string `"Hypothetical relevant passage answering: {question}"`
for "HyDE". No LLM anywhere. Variants were string-concatenated into one query
rather than retrieved separately and fused. `transform_timeout_ms` guarded
nothing.

## What was built

- **LLM-backed transform** (`app/core_rag/query_transform.py`, fully rewritten):
  rewrite, expansion, and HyDE each call the configured LLM via a new
  short-timeout client path. The hardcoded `_EXPANSIONS` dict, `_hyde_query`,
  and `_expanded_query` are **deleted**.
- **Budget actually guards something** (`app/llm/client.py::generate_transform_text`):
  a plain-text completion that honors the caller's timeout instead of
  `generate_answer`'s 300 s floor. `transform_timeout_ms` is enforced as a
  TOTAL budget across strategies — once spent, later strategies are skipped
  with `variant_status: skipped_budget_exhausted` and `fallback_reason:
  timeout_budget_exhausted`.
- **Graceful fallback everywhere**: LLM unreachable, timed out, or empty →
  fall back to the original query, never raise; per-strategy status and a
  `fallback_reason` are recorded in the trace (`variant_status`, `llm_calls`,
  `budget_ms`).
- **Multi-query fan-out** (`multi_query_enabled` flag, `app/core_rag/retrieval.py`):
  when enabled, the original query and each generated variant are retrieved
  separately and RRF-fused by chunk_id (`_fuse_multi_query_lists`) before
  rerank, instead of concatenating into one query string. Standard
  vector/keyword/hybrid modes only — deep research owns its own recall. Trace
  carries `multi_query` with per-variant candidate counts. Disabled →
  single-query concatenation (prior behavior), `applied: false`.
- **Surfaced** in admin transform posture, sandbox compare summary, and the
  tuning console (multi-query toggle + summary badge).

## Measured eval delta (honest)

Transform off vs on, 20-case even-stride sample of `pack_general`, hybrid mode,
live profile, CPU:

| metric | off | on | delta |
|--------|-----|----|-------|
| recall@5 | 0.5083 | 0.5083 | +0.0000 |
| MRR | 0.8017 | 0.8017 | +0.0000 |
| nDCG@10 | 0.7233 | 0.7233 | +0.0000 |

**Why zero, stated plainly:** the currently-configured generation model
(`gpt-oss:20b-cloud` via Ollama) returns an **empty `content` field** for these
short transform prompts in this environment (verified directly against
`/v1/chat/completions` at multiple `max_tokens`/`reasoning_effort` settings).
Empty content → every variant falls back → transform-on is byte-identical to
transform-off, so the delta is exactly zero. This is the designed fallback
behavior for an unreliable transform LLM, not a no-op stub: the mechanism is
proven to generate real variants, enforce the budget, and move rankings via the
8 AR5 unit tests (`tests/test_query_transform_ar5.py`), which pin a
content-returning LLM. A model that emits content (or AR9's provider
abstraction) will produce a non-zero delta through the same path; the gate is
"the flags do what they say," and they now do.

## DoD check

- With flags enabled and the LLM returning content, traces show genuinely
  generated variants ✓ (unit tests assert per-strategy `generated` status and
  distinct variant text). With the LLM unreachable/empty, answers still
  complete via fallback within budget ✓.
- Measured eval delta documented honestly ✓ (neutral; root cause named).
- Re-run checks: M18 transform smoke updated for the deleted dict; transform
  timeout/budget + fallback tests; multi-query fan-out on a seeded corpus;
  full suite **257/257 green**; `tsc --noEmit` clean.

**Next:** AR6 — Rename Or Properly Implement The Semantic Cache.
