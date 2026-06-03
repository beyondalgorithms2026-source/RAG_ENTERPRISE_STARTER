# Module Map

This document explains the current folder/module responsibilities for the reusable base repo.

## Top-Level Repo Areas

- `backend/`: FastAPI backend, retrieval, ingestion, eval, and tests
- `web/`: Next.js user and admin console
- `frontend/`: lightweight static frontend
- `docs/`: current-state and provenance docs
- `data/`: local runtime storage for uploaded/extracted artifacts

## `backend/app/`

### `backend/app/api/`

Route layer:
- health
- upload
- corpus
- search
- ask
- compare

Role:
- thin request/response surface over core logic

### `backend/app/core/`

Shared backend infrastructure:
- config
- logging

### `backend/app/core_rag/`

RAG orchestration layer:
- retrieval dispatch
- reranking
- answer orchestration
- router policy

Important files:
- `retrieval.py`
- `reranker.py`
- `answering.py`
- `query_router.py`

### `backend/app/db/`

Persistence layer:
- DB engine
- schema/migration
- table-focused repositories
- DB verification helpers

Important files:
- `schema.sql`
- `migrate.py`
- `repo_sources.py`
- `repo_chunks.py`
- `repo_search.py`
- `repo_jobs.py`

### `backend/app/embedding/`

Embedding model abstraction and embedding pipeline:
- model loading
- expected dimension reporting
- embedding batch execution

### `backend/app/graph/`

Optional graph and temporal support:
- deterministic extraction helpers
- ontology normalization
- temporal extraction
- graph artifact build/store/explain helpers
- graph retrieval support

Important note:
- this folder contains optional capabilities layered on top of the baseline system

### `backend/app/ingestion/`

Upload-to-index pipeline:
- hashing
- normalization
- chunking
- ingestion jobs
- enrichment orchestration

Important files:
- `jobs.py`
- `chunking.py`
- `enrichment.py`

### `backend/app/llm/`

LLM interaction layer:
- provider client
- prompt templates

### `backend/app/eval/`

Evaluation-only modules:
- `retrieval_eval.py`
- `enriched_eval.py`

These should remain separate from production paths.

## `backend/tests/`

Current test layout after hardening:
- `smoke_test_base.py`
- `test_smoke_baseline.py`
- `test_smoke_enrichment.py`
- `test_smoke_router_compare_eval.py`
- `smoke_test_extracted.py` as the thin aggregator
- `fixtures/` for parser and evaluation data

## `frontend/`

Current frontend files:
- `index.html`
- `styles.css`
- `upload.js`
- `corpus.js`
- `ask.js`

Role:
- lightweight demo/operator-facing web surface
- not a full product frontend

## Related Docs

- [scenario_profiles_and_reuse_blueprint.md](../scenario_profiles_and_reuse_blueprint.md)
- [m27_module_selection_map.mmd](../diagrams/m27_module_selection_map.mmd)
- [architecture_overview.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
- [api_surface.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
- [adoption_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/adoption_guide.md)
