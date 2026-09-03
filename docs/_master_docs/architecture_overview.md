# Architecture Overview

This document describes the current implemented architecture through M19. It is a current-state guide, not a future milestone plan.

## Core Shape

The repo is an extraction-first, upload-based RAG system with optional enrichment layers.

Baseline path:
- upload
- parse
- chunk
- embed
- retrieve
- answer

Optional enrichment path:
- entity extraction
- relation extraction
- temporal extraction
- graph artifact build
- retrieval-time graph and temporal integration

Compare and evaluation are explicit surfaces layered on top of the same core.

## Runtime Layers

### Baseline Runtime Flow

1. file upload enters `/upload`
2. ingestion stores source and source-part records
3. chunking creates source-aware chunks
4. embedding writes vectors to `chunks`
5. `/search` or `/ask` runs retrieval
6. answering composes a grounded response with citations

### Enrichment Runtime Flow

When enabled:
1. chunk-level entity/relation extraction may run
2. chunk-level temporal extraction may run
3. source-level graph artifacts may be built
4. source metadata records graph, temporal, and lazy-enrichment state
5. `graph_hybrid` and `full` may consume those artifacts conservatively

### Lazy Full-Mode Readiness

Current M15 behavior:
- `full` can trigger bounded lazy enrichment only when:
  - lazy enrichment is enabled
  - source scope is explicit
  - prerequisites are available
  - artifacts are missing or stale
- fallback remains safe

## Retrieval Modes

Baseline modes:
- `vector`
- `keyword`
- `hybrid`

Enriched modes:
- `graph_hybrid`
- `full`

Current meaning:
- `graph_hybrid`: baseline hybrid retrieval plus conservative graph-aware support when current graph artifacts exist
- `full`: baseline retrieval plus available graph and/or temporal support, with the existing bounded readiness behavior

## Router Boundary

The router is explicit and conservative.

Current behavior:
- applies only when `mode` is omitted
- never overrides explicit mode selection
- uses query signals plus source-scoped artifact readiness
- falls back to safe baseline modes when uncertainty is high

## Compare Boundary

Compare mode is explicit only via `/compare`.

Current behavior:
- requires explicit multi-source scope
- groups evidence by source
- preserves citation grounding discipline
- does not silently change `/ask`

## Evaluation Boundary

The evaluation harness is intentionally separate from production behavior.

Current evaluation surfaces:
- `backend/app/eval/retrieval_eval.py`
- `backend/app/eval/enriched_eval.py`

Current role:
- assess retrieval behavior
- assess grounding/citation behavior
- assess compare and fallback behavior
- emit JSON-first reports

## Storage And Internal State

Relational core:
- sources
- source parts
- chunks
- ingestion jobs
- enrichment jobs

JSON-backed internal state:
- chunk enrichment metadata
- chunk temporal metadata
- chunk provenance
- source graph artifact metadata
- source temporal summary metadata
- source lazy-enrichment trace metadata

Authoritative internal JSON contract guide:
- [internal_metadata_contracts.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)

## Current Architecture Limits

- synchronous ingestion
- local upload storage
- compact graph artifacts stored in source metadata
- deterministic rule-based extraction, not learned extraction
- lightweight frontend relative to backend capability

## Related Docs

- [module_map.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)
- [api_surface.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
- [configuration.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [evaluation.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)

