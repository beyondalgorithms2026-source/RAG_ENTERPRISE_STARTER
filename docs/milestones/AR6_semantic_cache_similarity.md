# AR6 — Properly Implement The Semantic Cache (Gate AR6: cache naming is truthful)

**Date:** 2026-06-13 · **Plan:** `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` · **Gate:** AR6

## Audit finding remediated

The "semantic cache" matched on an exact normalized-question hash
(`repo_semantic_cache.py`, `cache_scope` → exact `normalized_question`);
paraphrases never hit. `semantic_cache_similarity_threshold: float = 0.92`
(`profiles/models.py:58`) was read by no lookup path — a config field implying
a capability that did not exist. The audit was explicit that the *governance*
around the cache (policy scoping, ACL/profile/revision validation, user
refresh) is genuinely good; only the word "semantic" was untrue.

**Decision: implement the real similarity tier** (not rename). The schema was
already provisioned for it — `semantic_cache_policy_versions.match_mode` and
`semantic_cache_entries.query_embedding_json` both existed but were inert.

## What was built

- **Real embedding-similarity lookup** (`repo_semantic_cache.py`): when the
  active policy's `match_mode == "semantic"` and there is no exact match,
  `_semantic_lookup` embeds the incoming question, selects candidates in the
  **same** namespace + ACL + profile + corpus + mode scope (relaxing **only**
  the question dimension), ranks by cosine, and gates on the policy's
  `similarity_threshold`.
- **Identical governance for exact and similarity hits**: the post-match path
  is now one function, `_finalize_hit` — policy re-check, per-source ACL
  re-authorization, content/profile revision validation, then hit accounting.
  A similarity hit clears the exact same safety bar; it is not a relaxed path.
- **Embeddings stored** for semantic policies (`store_cache_entry` computes the
  query embedding when `match_mode == "semantic"`); embedding failure degrades
  to exact-only, never errors.
- **The dead field is gone**: `semantic_cache_similarity_threshold` removed
  from `RetrievalProfileConfig`. The real threshold lives on the policy version
  (`MIG-P022` adds `similarity_threshold`), validated to 0.5–0.999, with
  `match_mode ∈ {exact, semantic}`.
- **Metrics distinguish hit types**: `cache_health` reports
  `exact_hit_count` vs `similarity_hit_count`; policy events record
  `semantic_similarity` with the matched cosine.
- **Truthful UI**: the cache-policy console replaced the literal
  `"Exact query (locked)"` read-only field with a real match-mode selector and
  a similarity-threshold control shown only in semantic mode.

## Threshold calibration (honest, measured)

Cosine similarity with the active `bge-base-en-v1.5` embedder:

| pair | cosine |
|------|--------|
| "What is the leave policy?" ↔ "How much annual leave do I get?" | 0.704 |
| "termination clause obligations" ↔ "what are the obligations when terminating the contract" | 0.826 |
| "What is the leave policy?" ↔ "How do I reset my password?" (unrelated) | 0.454 |

**The audit's dead default of 0.92 is too strict for this embedder** — genuine
paraphrases land at 0.70–0.83, so 0.92 would almost never fire. The schema
keeps 0.92 as the historical default but it is a precision-first setting;
operators wanting real paraphrase hits on bge-base should lower it toward
~0.80 (which separates the 0.70–0.83 paraphrase band from the ~0.45 unrelated
band). The threshold is policy-tunable across 0.5–0.999 and per-namespace, so
calibration is an operator decision measured per corpus, not a magic constant.

## DoD check

- No user-visible label, config field, or doc claims semantic matching unless
  similarity lookup is live and tested ✓ (lookup implemented; dead field
  removed; UI selector real).
- Paraphrase hit + false-hit guard tests ✓ (`tests/test_semantic_cache_similarity_ar6.py`):
  a 0.98-cosine paraphrase hits, a 0.50-cosine different-intent question misses.
- Same governance on similarity hits ✓ (revision-change invalidation proven on
  the similarity path; shared `_finalize_hit`).
- Re-run checks: M33 cache governance suite green; full suite **265/265**;
  `tsc --noEmit` clean; `docs/02` untouched.

**Next:** AR7 — Embedding And Index Lifecycle Management.
