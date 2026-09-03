# API Surface

This document describes the currently implemented API surface through M20.

## Routes

Current backend routes:
- `/health`
- `/upload`
- `/corpus`
- `/search`
- `/deep_lookup`
- `/ask`
- `/compare`

Implemented in:
- [backend/app/api/health.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/health.py)
- [backend/app/api/upload.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/upload.py)
- [backend/app/api/corpus.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/corpus.py)
- [backend/app/api/search.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/search.py)
- [backend/app/api/ask.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/ask.py)
- [backend/app/api/compare.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/api/compare.py)

## `/health`

Purpose:
- service liveness check

## `/upload`

Purpose:
- upload a supported file
- trigger ingestion, chunking, embedding, and optional post-ingestion enrichment hooks

Current supported source types:
- `pdf`
- `docx`
- `pptx`
- `xlsx`
- `eml`
- `txt`
- `md`

Current upload behavior:
- `POST /upload` accepts one file
- `POST /upload/batch` accepts multiple files and returns one result per file

Format notes:
- `txt` is ingested as plain text only
- `md` preserves lightweight heading structure only and does not render markdown

## `/corpus`

Purpose:
- inspect uploaded sources and current ingestion state
- delete an uploaded source by id

## `/search`

Purpose:
- retrieval-only surface returning chunk-level results

Current mode support:
- `vector`
- `keyword`
- `hybrid`
- `graph_hybrid`
- `full`

Behavior notes:
- baseline modes remain intact
- `graph_hybrid` is additive and conservative
- `full` uses current graph/temporal support when available
- router behavior only applies when `mode` is omitted

## `/deep_lookup`

Purpose:
- explicit source-scoped rescue retrieval when a user believes evidence exists in one source or a very small selected set

Behavior notes:
- explicit only; never activated silently
- requires explicit `source_ids`
- bounded to a very small selected source set
- retrieval-only; it does not generate answers
- uses larger candidate pools, stronger lexical weighting, and bounded anchor co-occurrence boosting only within the selected sources
- does not use router behavior
- does not trigger graph, temporal, or indexing changes

## `/ask`

Purpose:
- grounded answer generation over retrieved evidence

Behavior notes:
- response shape remains the normal ask contract
- explicit mode selection is preserved
- compare behavior is not hidden inside `/ask`

## `/compare`

Purpose:
- explicit compare-mode answer surface across multiple sources

Behavior notes:
- compare is explicit only here
- it is source-scoped
- it groups evidence by source
- it preserves citation grounding discipline
- omitted-mode compare requests can reuse the current router conservatively

## Mode Semantics

For the most explicit current retrieval-mode matrix:
- [master_guide.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)

### Baseline modes

- `vector`: vector similarity only
- `keyword`: lexical/full-text retrieval only
- `hybrid`: vector + keyword baseline retrieval

### Enriched modes

- `graph_hybrid`: baseline hybrid plus graph-aware retrieval support when graph artifacts are ready
- `full`: baseline retrieval plus available graph/temporal support and bounded readiness orchestration

### Router behavior

Current router policy:
- applies only when `mode` is omitted
- never silently overrides explicit mode choice
- prefers conservative fallback to `hybrid` when enriched paths are not clearly usable

Deep lookup policy:
- is not part of the normal `/search` mode matrix
- is a separate explicit route
- requires explicit source scope

## Current API Limits

- no compare UI contract beyond the backend route itself
- no broad answer-contract redesign
- no hidden automatic compare behavior
- no M20+ admin or advanced evaluation route surface

## Related Docs

- [configuration.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
- [evaluation.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
