## M8 — Reranking Policy Layer

- Extended the reranker profile from a single global switch into a policy surface with mode allowlists, corpus allowlists, candidate-depth thresholds, and a latency budget.
- Search traces now expose the rerank policy decision, including why reranking was applied or skipped and the candidate corpora seen before rerank.
- Added an explicit MMR placeholder hook. AR14 superseded that placeholder with standard MMR over reranker relevance and ACL-trimmed stored embeddings; missing vectors fall back in original order with a truthful trace reason.
- Compare-eval now supports rerank A/B variants and emits a latency report that shows per-variant averages plus deltas against the rerank-off baseline.
