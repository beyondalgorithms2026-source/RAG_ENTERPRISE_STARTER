# Configuration Reference

This document describes the current runtime configuration of `RAG_MM_MASTER_POC` after M19 and the hardening pass.

## Sources Of Truth

Runtime defaults:
- [backend/app/core/config.py](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/core/config.py)

Example environment file:
- [backend/.env.example](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/.env.example)

Local infrastructure:
- [docker-compose.yml](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docker-compose.yml)

## Default Runtime Story

If `backend/.env` is absent, the backend falls back to defaults defined in `backend/app/core/config.py`.

Current key defaults:
- `DATABASE_URL=postgresql://rag_mm_master_poc:rag_mm_master_poc_dev_pass@localhost:55432/rag_mm_master_poc`
- `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`
- `LLM_PROVIDER=ollama`
- `LLM_BASE_URL=http://localhost:11434`
- `LLM_MODEL=gpt-oss:20b-cloud`
- `RETRIEVAL_MODE=hybrid`
- `ALLOW_LAZY_ENRICHMENT=true`
- `USE_QUERY_ROUTER=true`

## Configuration Areas

### Database

- `DATABASE_URL`

Used by:
- DB engine setup
- migrations
- test suite

### Upload And File Handling

- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_BYTES`
- `ALLOWED_UPLOAD_EXTENSIONS`

Current supported extensions:
- `pdf`
- `docx`
- `pptx`
- `xlsx`
- `eml`
- `txt`
- `md`

### Embeddings

- `EMBEDDING_MODEL`
- `EMBEDDING_BATCH_SIZE`

These drive:
- expected embedding dimension
- embedding generation
- migration-time vector dimension alignment

### LLM

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_S`
- `LLM_API_KEY`
- `OLLAMA_API_KEY`

Current note:
- the repo supports the current provider abstraction in code, but the default local story is Ollama-compatible

### Retrieval

- `RETRIEVAL_MODE`
- `RERANK_ENABLED`
- `RERANK_MODEL`
- `TOP_K_INITIAL`
- `HYBRID_ALPHA`
- `VECTOR_CANDIDATES`
- `KEYWORD_CANDIDATES`

Current supported retrieval modes:
- `vector`
- `keyword`
- `hybrid`
- `graph_hybrid`
- `full`

### Enrichment / Build Flags

- `ENABLE_GRAPH`
- `ENABLE_TEMPORAL`
- `ENABLE_ONTOLOGY`
- `EXTRACT_ENTITIES`
- `EXTRACT_RELATIONS`
- `EXTRACT_TEMPORAL_METADATA`
- `BUILD_GRAPH_ON_INGEST`

Important behavior:
- these are optional enrichment/build controls
- baseline modes do not require them
- they do not change baseline behavior when disabled

### Query-Time Behavior

- `ALLOW_LAZY_ENRICHMENT`
- `TEMPORAL_RERANK_ENABLED`
- `USE_QUERY_ROUTER`

Current behavior:
- lazy enrichment is bounded and only applies to source-scoped `full` requests when prerequisites are met
- the router is only consulted when `mode` is omitted
- explicit mode selection is preserved
- `TEMPORAL_RERANK_ENABLED` remains present as a flag surface, but temporal behavior is integrated conservatively through existing retrieval logic rather than a separate standalone temporal service

### Builder / Debug Flags

- `ENABLE_COMPARISON_VIEW`
- `ENABLE_RETRIEVAL_TRACE`
- `ENABLE_GRAPH_EXPLAINABILITY`

These support:
- compare-mode availability
- retrieval/debug visibility
- graph explain/debug visibility

## Practical Default Behavior

Out of the box:
- baseline retrieval works with `hybrid`
- router behavior is enabled if `mode` is omitted
- lazy enrichment is allowed, but only bounded `full` requests with explicit source scope can trigger it
- graph and temporal extraction/build remain disabled unless their flags are enabled

## Recommended Reuse Guidance

When adapting this repo for a new project:
- decide whether router-on-by-default is appropriate for your use case
- decide whether lazy enrichment should stay enabled by default
- keep env defaults and docs aligned together
- treat `backend/.env.example` as the user-facing runtime story

## Related Docs

- [architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
- [api_surface.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
- [internal_metadata_contracts.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
