# Maintainer Runbook

This is a compact human-maintainer guide for common development and debugging tasks in `RAG_MM_MASTER_POC`.

For a broad system walkthrough before using this runbook:
- [master_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)

## Authoritative Docs

Current-state docs:
- [README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
- [docs/configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [docs/architecture_overview.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
- [docs/internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)

Historical/provenance docs:
- [docs/reuse_inventory.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/reuse_inventory.md)
- [docs/extraction_map.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/extraction_map.md)
- [docs/rag_poc_v1_assumptions.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/rag_poc_v1_assumptions.md)

## Start The Local Stack

Database:

```bash
docker compose up -d
```

Backend:

```bash
cd backend
cp .env.example .env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## DB And Migration Basics

Migration entrypoint:
- [backend/app/db/migrate.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/db/migrate.py)

Schema source:
- [backend/app/db/schema.sql](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/db/schema.sql)

Current migration model:
- canonical schema apply
- ordered patch steps
- no heavy migration framework

When debugging DB readiness:
- inspect migration logs
- run DB checks through the existing smoke coverage and `verify_db` helpers

Operational commands:

```bash
cd backend
python -m app.db.migrate
python scripts/admin_reindex.py --source-id <SOURCE_ID>
python scripts/admin_enrich.py --source-id <SOURCE_ID>
python scripts/cleanup_test_data.py --storage-prefix tests/
python scripts/cleanup_test_data.py --storage-prefix tests/ --apply
```

Expected behavior:
- `admin_reindex.py` clears chunks, source parts, and derived graph/temporal/lazy metadata sections for one source, then rebuilds ingestion artifacts from the stored file.
- `admin_enrich.py` clears derived graph/temporal metadata for one source, reruns enrichment, and leaves lazy traces intact.
- `cleanup_test_data.py` is conservative by default and only reports matches unless `--apply` is supplied.

## Test Basics

Current split smoke layout:
- [backend/tests/test_smoke_baseline.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/tests/test_smoke_baseline.py)
- [backend/tests/test_smoke_enrichment.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/tests/test_smoke_enrichment.py)
- [backend/tests/test_smoke_router_compare_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/tests/test_smoke_router_compare_eval.py)
- [backend/tests/smoke_test_extracted.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/tests/smoke_test_extracted.py) as the thin aggregator

Full suite:

```bash
cd backend
PYTHONPATH=. venv/bin/python -m unittest tests/smoke_test_extracted.py
```

## Eval Basics

Eval modules:
- [backend/app/eval/retrieval_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/retrieval_eval.py)
- [backend/app/eval/enriched_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/enriched_eval.py)
- [backend/app/eval/compare_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/compare_eval.py)

Fixtures:
- `backend/tests/fixtures/eval/`

Benchmark artifact examples:
- `backend/tests/fixtures/eval/benchmarks/`

## Where To Look When Something Breaks

Upload/ingestion issues:
- [backend/app/ingestion/jobs.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/ingestion/jobs.py)
- [backend/app/ingestion/chunking.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/ingestion/chunking.py)
- [backend/app/adapters/](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/adapters)

Retrieval issues:
- [backend/app/core_rag/retrieval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/core_rag/retrieval.py)
- [backend/app/db/repo_search.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/db/repo_search.py)
- [backend/app/core_rag/query_router.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/core_rag/query_router.py)

Enrichment/graph/temporal issues:
- [backend/app/ingestion/enrichment.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/ingestion/enrichment.py)
- [backend/app/graph/](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/graph)
- [docs/internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)

Ask/compare issues:
- [backend/app/core_rag/answering.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/core_rag/answering.py)
- [backend/app/api/ask.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/ask.py)
- [backend/app/api/compare.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/compare.py)
