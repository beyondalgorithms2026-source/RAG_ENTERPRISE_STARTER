# Imported Baseline Reference Only

This file is kept for provenance. It is not the canonical entrypoint for this repo.

Use these instead:
- top-level [README.md](/path/to/RAG_ENTERPRISE_STARTER/README.md)
- [STATUS.md](/path/to/RAG_ENTERPRISE_STARTER/STATUS.md)
- [docs/02_Enterprise_RAG_Project_Plan_Milestones.md](/path/to/RAG_ENTERPRISE_STARTER/docs/02_Enterprise_RAG_Project_Plan_Milestones.md)

The content below is preserved from the imported baseline and may mention superseded paths such as `frontend/` as the primary UI.

# RAG_MM_MASTER_POC

Reusable, extraction-first, upload-based RAG base repo with optional graph, temporal, router, compare, and evaluation capabilities implemented through M20.

## What This Repo Is

This repo is for teams who want a practical starting point for:
- multi-format upload-based RAG
- grounded answers with citations
- optional enrichment-driven retrieval
- side-by-side comparison and evaluation work

It is a strong reusable PoC base, not a production platform template.

## Current Scope

Implemented through:
- M0-M20 complete

Milestone ledger:
- [STATUS.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/STATUS.md)

Authoritative project plan:
- `RAG_Master_Revised_Project_Plan.md`

## Retrieval And Answering Capabilities

Baseline modes:
- `vector`
- `keyword`
- `hybrid`

Enriched modes:
- `graph_hybrid`
- `full`

Additional behavior:
- compare mode is explicit only via `/compare`
- router behavior applies only when `mode` is omitted
- explicit mode selection is not overridden
- graph and temporal behavior remain optional and flag-controlled

## Supported Inputs

Current upload support:
- `pdf`
- `docx`
- `pptx`
- `xlsx`
- `eml`
- `txt`
- `md`

Format notes:
- `txt` is plain-text only
- `md` is lightweight and text-first; headings are preserved, while links, lists, and code fences remain literal text

## Who This Repo Is For

- teams building new RAG PoCs from a reusable base
- consultants and solution architects adapting one core to multiple client use cases
- developers who want a reference implementation for upload, retrieval, answering, compare, and evaluation flows

## Quick Start

### 1. Start Postgres + pgvector

```bash
docker compose up -d
```

### 2. Set up the backend

```bash
cd backend
cp .env.example .env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Verify the service

```bash
curl http://localhost:8000/health
```

### 5. Open the lightweight frontend

- `http://localhost:8000/frontend/`

## Operational Commands

Common maintainer commands:

```bash
cd backend
venv/bin/python -m unittest tests/smoke_test_extracted.py
python scripts/admin_reindex.py --source-id <SOURCE_ID>
python scripts/admin_enrich.py --source-id <SOURCE_ID>
python scripts/cleanup_test_data.py --storage-prefix tests/
python scripts/cleanup_test_data.py --storage-prefix tests/ --apply
```

For expected behavior and when to use each command:
- [docs/maintainer_runbook.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

## Runtime And Config Overview

Default behavior is defined in:
- [backend/app/core/config.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/core/config.py)

Example env file:
- [backend/.env.example](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/.env.example)

Key defaults:
- `RETRIEVAL_MODE=hybrid`
- `LLM_PROVIDER=ollama`
- `LLM_MODEL=gpt-oss:20b-cloud`
- `ALLOW_LAZY_ENRICHMENT=true`
- `USE_QUERY_ROUTER=true`

Important runtime notes:
- lazy enrichment is bounded and only applies to source-scoped `full` requests when prerequisites are met
- the router only applies when callers omit `mode`
- graph and temporal behavior do not affect baseline modes unless explicitly enabled and usable

For the full config reference:
- [docs/configuration.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)

## Current API Surface

Current routes:
- `/health`
- `/upload`
- `/corpus`
- `/search`
- `/deep_lookup`
- `/ask`
- `/compare`

API details:
- [docs/api_surface.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)

## Frontend Scope

The frontend is intentionally lightweight.

Current frontend focus:
- upload
- corpus list
- baseline ask/search flows

Current frontend limits:
- it does not expose every backend capability
- deep lookup remains backend-first and explicit
- compare mode remains backend-first
- builder/debug behavior is primarily documented through backend routes and eval tooling

## Documentation Guide

Start here:
- [docs/README.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/README.md)

Most useful guides:
- [docs/master_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)
- [docs/configuration.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [docs/architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
- [docs/module_map.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)
- [docs/api_surface.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
- [docs/adoption_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/adoption_guide.md)
- [docs/evaluation.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
- [docs/internal_metadata_contracts.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
- [docs/parser_capability_matrix.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/parser_capability_matrix.md)

## Operational Caveats

- this repo is still PoC-scale
- ingestion is synchronous
- local file storage is used for uploads
- source metadata holds compact graph, temporal, and lazy-enrichment state
- compare mode is explicit and source-scoped, not hidden automation

## Reuse Guidance

For future adopters, the intended customization points are:
- source adapters
- prompts
- evaluation fixtures
- retrieval tuning
- frontend scope
- domain-specific docs and demo data

Start with:
- [docs/adoption_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/adoption_guide.md)
- [docs/master_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)
