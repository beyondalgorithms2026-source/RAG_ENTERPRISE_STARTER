# Adoption Guide

This guide explains how to reuse `RAG_MM_MASTER_POC` as a base for a new RAG project.

For the broadest first-pass walkthrough:
- [master_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)

## What To Reuse As-Is First

Strong reuse candidates:
- upload-based ingestion flow
- source-aware schema and repositories
- baseline retrieval modes
- answer orchestration and citation discipline
- optional graph/temporal layering
- compare route and evaluation harnesses

## What Future Projects Will Usually Change

- source adapters
- prompt wording
- evaluation fixtures and benchmark cases
- retrieval weights and thresholds
- frontend scope
- deployment/runtime defaults

## Recommended Forking Approach

1. keep the current backend folder structure
2. keep the baseline retrieval and answer contracts stable first
3. decide whether graph/temporal features are needed for the new project
4. adapt adapters and prompts before touching retrieval internals
5. add domain-specific eval fixtures early

## How To Think About Modes

Baseline modes:
- `vector`
- `keyword`
- `hybrid`

Use these as the stable core.

Optional enrichment-backed modes:
- `graph_hybrid`
- `full`

Use these only if the new project benefits from:
- relationship-heavy retrieval
- time/version-sensitive retrieval
- bounded lazy enrichment behavior

## How To Think About Compare Mode

Compare mode is explicit and source-scoped.

Reuse it when:
- users need side-by-side source reasoning
- grouped source evidence matters

Do not assume it is a general hidden reasoning layer for `/ask`.

## How To Adapt Configuration Safely

Before changing behavior:
- update `backend/app/core/config.py`
- update `backend/.env.example`
- update `README.md` and `docs/configuration.md`

Keep those three aligned so adopters have one truthful runtime story.

## How To Extend Safely

Low-risk extension points:
- `backend/app/adapters/`
- `backend/app/llm/prompts.py`
- eval fixtures under `backend/tests/fixtures/`
- lightweight frontend behavior

More sensitive areas:
- `backend/app/ingestion/enrichment.py`
- `backend/app/core_rag/retrieval.py`
- `backend/app/ingestion/jobs.py`
- metadata contracts documented in `docs/internal_metadata_contracts.md`

## Current Reuse Caveats

- this repo is still PoC-scale
- ingestion is synchronous
- local upload storage is used
- source metadata carries compact graph/temporal/lazy state
- some architecture hotspots have been hardened but not fully decomposed

## Recommended First Reading For New Adopters

1. [README.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
2. [configuration.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
3. [architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
4. [module_map.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)
5. [internal_metadata_contracts.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
6. [evaluation.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
