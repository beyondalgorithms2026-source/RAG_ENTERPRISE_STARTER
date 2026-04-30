## M2: Retrieval Observability And Traceability

- Retrieval traces now persist request-level routing data, candidate counts, fallback reasons, score diagnostics, and active profile snapshots in `retrieval_traces`.
- `ask` updates the same request trace with `answer_generation_path` plus `ask` and end-to-end `total` latency so operators can inspect the full request lifecycle.
- Admin inspection endpoints are available at `GET /admin/traces`, `GET /admin/traces/{trace_id}`, and `GET /admin/traces/by-request/{request_id}`.
- Retrieval eval and mode benchmark reports now include `report_metadata.retrieval_settings` and per-case trace summaries for strategy comparisons.
