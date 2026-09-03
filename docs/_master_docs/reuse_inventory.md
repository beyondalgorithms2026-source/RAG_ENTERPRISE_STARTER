# Reuse Inventory — RAG_POC_V1 → RAG_MM_MASTER_POC

> Historical/provenance reference generated as an M0 deliverable.
> This file documents donor extraction decisions.
> It is not the primary onboarding guide for the current repo.

Current orientation docs:
- [README.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
- [docs/README.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/README.md)
- [docs/architecture_overview.md](/path/to/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)

## Classification Key

| Tag | Meaning |
|---|---|
| 🟢 **KEEP** | Reuse with minimal refactor (rename fields, extend config) |
| 🟡 **REFACTOR** | Reuse the pattern/logic; implementation must adapt to new data model |
| 🔴 **REPLACE** | Reference only; too narrow or coupled to survive as working code |
| ⚪ **SUPPORT** | Config/infra files carried forward with extensions |

---

## Module: `core/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 1 | `core/config.py` | 47 | 🟢 KEEP | `app/core/config.py` | Remove `DATA_DIR`/`EXTRACT_DIR` contract defaults. Add retrieval mode, enrichment, builder flags per master plan §10 |
| 2 | `core/logging.py` | 13 | 🟢 KEEP | `app/core/logging.py` | Rename logger from `rag_poc` → `rag_master` |

---

## Module: `db/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 3 | `db/db.py` | 5 | 🟢 KEEP | `app/db/db.py` | None |
| 4 | `db/repo_search.py` | 169 | 🟢 KEEP | `app/db/repo_search.py` | Replace `documents` JOIN → `sources` JOIN. Replace `contract_date` → generic `source_type` / locator filters. Add `source_part_id` to result set |
| 5 | `db/repo_documents.py` | 70 | 🟡 REFACTOR | `app/db/repo_sources.py` | Rename to `repo_sources.py`. Align `DocumentRow` → `SourceRow` with new schema fields (`source_type`, `enrichment_status`, etc.) |
| 6 | `db/repo_chunks.py` | 31 | 🟡 REFACTOR | `app/db/repo_chunks.py` | Add `source_part_id`, `locator_json`, enrichment JSON columns to INSERT |
| 7 | `db/repo_embeddings.py` | 72 | 🟡 REFACTOR | `app/db/repo_chunks.py` or `app/embedding/` | `_pgvector_literal` is reusable as-is. Align fetch/update queries to new `chunks` schema |
| 8 | `db/migrate.py` | 72 | 🟡 REFACTOR | `app/db/migrate.py` | Rewrite to run new `schema.sql`. Keep HNSW/IVFFLAT fallback strategy and patch migration pattern |
| 9 | `db/verify_db.py` | 80 | 🟡 REFACTOR | `app/db/verify_db.py` | Update table/column checks to match new schema. Remove hardcoded `vector(384)` — make dimension dynamic |

---

## Module: `embedding/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 10 | `embedding/embedder.py` | 33 | 🟢 KEEP | `app/embedding/embedder.py` | None |
| 11 | `embedding/process.py` | 89 | 🟡 REFACTOR | `app/embedding/process.py` | Align chunk fetch/update to new schema |

---

## Module: `retrieval/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 12 | `retrieval/search.py` | 203 | 🟢 KEEP | `app/core_rag/retrieval.py` | Replace `contract_date`/`doc_type` field refs. Add `graph_hybrid`/`full` mode stubs (no-op until M16) |
| 13 | `retrieval/reranker.py` | 33 | 🟢 KEEP | `app/core_rag/reranker.py` | None |

---

## Module: `llm/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 14 | `llm/client.py` | 141 | 🟢 KEEP | `app/llm/client.py` | None |
| 15 | `llm/prompts.py` | 29 | 🟢 KEEP | `app/llm/prompts.py` | Generalize user prompt builder for multi-format source metadata (source_type, locator) |

---

## Module: `answering/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 16 | `answering/ask.py` | 164 | 🟢 KEEP | `app/core_rag/answering.py` | Update Pydantic model imports to new API models. Adjust context block to include `source_type` and `locator` |

---

## Module: `eval/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 17 | `eval/retrieval_eval.py` | 237 | 🟢 KEEP | `app/eval/retrieval_eval.py` | Replace schema field refs. Extend mode choices to include `graph_hybrid`, `full` |

---

## Module: `chunking/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 18 | `chunking/splitter.py` | 167 | 🟡 REFACTOR | `app/ingestion/chunking.py` | Replace `ARTICLE`/contract heading heuristics with generic + per-adapter heading strategies. Keep target-word splitting, overlap, and packing logic |
| 19 | `chunking/process.py` | 97 | 🟡 REFACTOR | `app/ingestion/chunking.py` | Replace `document_id` → `source_id`. Integrate per-format adapter calls |

---

## Module: `ingestion/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 20 | `ingestion/hashing.py` | 9 | 🟢 KEEP | `app/ingestion/` or utility | None — generic SHA-256 |
| 21 | `ingestion/normalize.py` | 20 | 🟢 KEEP | `app/ingestion/normalize.py` | None — generic text cleanup |
| 22 | `ingestion/parsers.py` | 79 | 🔴 REPLACE | `app/adapters/pdf/`, `app/adapters/docx/`, etc. | PDF/DOCX only. No structured `SourcePart` output. New per-format adapters required |
| 23 | `ingestion/file_walker.py` | 18 | 🔴 REPLACE | Removed (upload-based) | Hardcoded `.pdf`/`.docx`. Folder-walk not needed |
| 24 | `ingestion/ingest.py` | 102 | 🔴 REPLACE | `app/ingestion/jobs.py` | Folder-based. `contract_date` from filename. Tied to old schema |

---

## Module: `api/`

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 25 | `api/health.py` | 8 | 🟢 KEEP | `app/api/health.py` | None |
| 26 | `api/search.py` | 49 | 🔴 REPLACE | `app/api/search.py` | Pydantic models have `contract_date`, old field set. Must align to new `sources`/`chunks` schema |
| 27 | `api/ask.py` | 43 | 🔴 REPLACE | `app/api/ask.py` | `CitationItem` lacks `source_type`, `locator_json`. Must align to new citation spec |

---

## Root / App-level

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 28 | `main.py` | 33 | 🔴 REPLACE | `app/main.py` | Needs upload/corpus/compare/admin routers. CORS origins will change |
| 29 | `cli_ingest.py` | ~25 | 🔴 REPLACE | CLI scripts | Must call new pipelines |
| 30 | `cli_chunk.py` | ~25 | 🔴 REPLACE | CLI scripts | Must call new pipelines |
| 31 | `cli_embed.py` | ~25 | 🔴 REPLACE | CLI scripts | Must call new pipelines |

---

## Frontend

| # | Donor File | Lines | Class | Target Module | Required Changes |
|---|---|---|---|---|---|
| 32 | `frontend/index.html` | ~100 | 🔴 REPLACE | `frontend/index.html` | No upload, no mode selector, no citation cards |
| 33 | `frontend/app.js` | ~170 | 🔴 REPLACE | `frontend/` | Tightly coupled to old API shapes |

---

## Support / Config Files

| # | Donor File | Class | Target | Notes |
|---|---|---|---|---|
| 34 | `requirements.txt` | ⚪ SUPPORT | `backend/requirements.txt` | Carry forward; add format-parser deps later |
| 35 | `.env.example` | ⚪ SUPPORT | `backend/.env.example` | Extend with new flags |
| 36 | `docker-compose.yml` | ⚪ SUPPORT | `docker-compose.yml` | Likely unchanged |
| 37 | `demo_questions.md` | ⚪ SUPPORT | `demo_questions_multiformat.md` | Reference for eval pattern; new multi-format version needed |
| 38 | `README.md` | ⚪ SUPPORT | `README.md` | Rewrite for new project |

---

## Summary Counts

| Classification | Count |
|---|---|
| 🟢 KEEP | 14 |
| 🟡 REFACTOR | 8 |
| 🔴 REPLACE | 11 |
| ⚪ SUPPORT | 5 |
| **Total** | **38** |

> `__init__.py` files (10 total) are trivially regenerated and not counted individually.
