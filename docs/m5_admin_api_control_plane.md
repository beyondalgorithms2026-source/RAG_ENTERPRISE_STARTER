# M5 — Admin API Control Plane

- Added admin-only `/admin/*` authorization enforcement via the shared authenticated user context and `admin` role check.
- Added corpus registry APIs for create/update/list plus source-to-corpus assignment using existing source metadata labels.
- Added operator APIs for profile metadata/default inspection, retrieval debug query traces, reindex triggers, enrichment reruns, eval triggers, report listing, and ingestion/enrichment job status.
- Kept the implementation aligned with the existing PoC backend: reindex and eval actions remain synchronous, but now they are runnable without Python code edits.
- Verified with targeted M5 smoke tests plus baseline job/retrieval smoke coverage.
