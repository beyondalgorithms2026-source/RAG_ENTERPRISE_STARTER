# AR14 — Eval-Proven Retrieval Enhancements

**Status:** Complete (2026-06-13)
**Gate:** No unfalsifiable tuning

## Findings Remediated

> “MMR is an explicit placeholder.”

> “Score-fusion arithmetic is ad hoc. Anchor boosts, graph boosts, temporal boosts, window candidates, and neighbor bonuses are additive magic constants…”

> “Some constants encode test-specific vocabulary — `causal_terms = {"because", "challenging", "dominated", …}` — is overfit to a particular demo corpus.”

> “Keyword indexing used a single `search_tsv` with no field weighting…”

## Shipped

- Standard MMR over full-pool reranker relevance and ACL-trimmed stored embeddings; eval-selected `lambda=0.5`; missing vectors preserve original order with a traced fallback.
- Heading=A/body=B PostgreSQL FTS with idempotent `MIG-P026`, trigger coverage for both fields, and full backfill.
- Request-scoped `ContextVar` scoring overrides and committed paired ablation evidence.
- Centralized adopted boost constants; graph `0.20`, temporal matched-signal blend `0.10`; demo `causal_terms` bonus deleted.
- `GET /admin/retrieval/evidence` and tuning-console verdict/delta visibility.

## Evidence

| Feature | Verdict | Chosen | Feature delta |
|---|---|---|---:|
| MMR | Adopted | lambda 0.5 | diversity +0.5000 |
| Field-weighted FTS | Adopted | heading A/body B | nDCG@10 +0.2902 |
| Anchor boost | Adopted | centralized caps | nDCG@10 +0.2902 |
| Graph blend | Adopted | 0.20 | nDCG@10 +0.2902 |
| Temporal blend | Adopted | 0.10 | nDCG@10 +0.2902 |
| Deep research | Adopted | widened, neighbors off by default | recall@5 +0.5000 |

400-case AR3 control:

- Recall@5: `0.5041667 → 0.5050000`
- MRR: `0.8500863 → 0.8500863`
- nDCG@10: `0.7657362 → 0.7659302`
- Gate: pass

## Honest Limit

Graph and temporal evidence is deterministic reviewed isolation evidence. The dev DB contains smoke-test residue, not a real reviewed graph/temporal corpus. Production-corpus validation remains open.

## Verification

- Backend: `315/315` passed.
- TypeScript: `npx tsc --noEmit` passed.
- Evidence: `backend/eval_packs/AR14_retrieval_ablation_report.json`.
- Protected M-series plan unchanged.
