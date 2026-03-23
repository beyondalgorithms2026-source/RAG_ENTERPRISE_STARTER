# RAG_POC_V1 — Narrow Assumptions Registry

> Historical/provenance reference generated as an M0 deliverable.
> This file documents narrow donor assumptions that shaped early extraction and schema decisions.
> It is not the primary guide to the current repo state.

Current state docs:
- [README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
- [docs/README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/README.md)
- [docs/adoption_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/adoption_guide.md)

## Summary

The donor codebase (`rag-poc-v1`) was built as a contract-document RAG PoC. It works well within those constraints, but carries 9 narrow assumptions that would break or limit the new multi-format, upload-based, enrichment-ready architecture.

---

## Assumption Register

### A1 — Single-Folder Corpus Ingestion

| Field | Detail |
|---|---|
| **What** | Ingestion walks a local `DATA_DIR` folder for files |
| **Where** | `config.py` (`DATA_DIR = "../data/contracts"`), `ingest.py` (line 23), `file_walker.py` (line 4) |
| **Impact** | Upload-based ingestion (M4) replaces folder-walking entirely |
| **Resolution** | `file_walker.py` is discarded. `ingest.py` is rewritten as `jobs.py`. `DATA_DIR` replaced by `uploads/` directory |

---

### A2 — PDF/DOCX-Only File Support

| Field | Detail |
|---|---|
| **What** | Only `.pdf` and `.docx` extensions are recognized |
| **Where** | `file_walker.py` (line 5: `supported_extensions = {".pdf", ".docx"}`), `parsers.py` (line 73–78) |
| **Impact** | PPTX, XLSX, EML are not parseable |
| **Resolution** | Per-format adapter modules under `app/adapters/` (M5) |

---

### A3 — Contract-Biased Heading Detection

| Field | Detail |
|---|---|
| **What** | Chunking heuristic detects `ARTICLE` + roman numerals and numbered section patterns |
| **Where** | `splitter.py` (lines 17–35, `is_heading` function), `STOPWORDS = {"TERMS", "VARIABLES", "SIGNATURE", "RECITALS"}` |
| **Impact** | Non-contract documents (slides, spreadsheets, emails) won't chunk correctly |
| **Resolution** | Replace with generic heading detection + per-format adapter strategies (M6). Keep word-target splitting and packing logic |

---

### A4 — `contract_date` Field on Documents

| Field | Detail |
|---|---|
| **What** | Every document record has a `contract_date` column, extracted from filename regex |
| **Where** | `repo_documents.py` (line 29), `ingest.py` (lines 13–20, 58), `repo_search.py` (lines 46–51, 128–131), `search.py` (lines 29, 99) |
| **Impact** | Field is meaningless for non-contract documents; pollutes filter logic |
| **Resolution** | Replaced by generic `source_type` + `locator_json` in new schema. Date filters become optional temporal metadata (M13) |

---

### A5 — Flat `documents` → `chunks` Schema

| Field | Detail |
|---|---|
| **What** | Two-table schema: `documents` (file metadata) → `chunks` (text + embeddings). No intermediate structural layer |
| **Where** | `migrate.py` (all), `repo_documents.py`, `repo_chunks.py`, `repo_embeddings.py`, `repo_search.py` |
| **Impact** | Cannot represent page/slide/sheet/email-body structure. Cannot attach enrichment metadata to structural units |
| **Resolution** | New three-layer schema: `sources` → `source_parts` → `chunks` + `attachments` + `ingestion_jobs` + `enrichment_jobs` (M3) |

---

### A6 — No Upload Endpoint

| Field | Detail |
|---|---|
| **What** | No `POST /upload` API. Files must be placed on disk manually |
| **Where** | `main.py` (only registers `/health`, `/search`, `/ask`), `api/` directory |
| **Impact** | Users cannot upload from browser |
| **Resolution** | `POST /upload` endpoint added in M4 |

---

### A7 — No Enrichment Columns on Chunks

| Field | Detail |
|---|---|
| **What** | `chunks` table has no columns for entities, relations, temporal metadata, or provenance |
| **Where** | `repo_chunks.py` (line 17–19: INSERT only has `heading`, `section_path`, `chunk_text`, `token_count`, `search_tsv`) |
| **Impact** | Graph/temporal enrichment cannot be stored |
| **Resolution** | New schema adds `entities_json`, `relations_json`, `temporal_json`, `provenance_json` as optional columns (M3) |

---

### A8 — Hardcoded Vector Dimension Check

| Field | Detail |
|---|---|
| **What** | `verify_db.py` checks for exactly `vector(384)` |
| **Where** | `verify_db.py` (line 48: `if res_dim and res_dim[0] == 'vector(384)'`) |
| **Impact** | Fails verification if embedding model changes dimension |
| **Resolution** | Make dimension check dynamic — read expected dim from `embedder.get_expected_dim()` |

---

### A9 — Static Frontend With Hardcoded API Shapes

| Field | Detail |
|---|---|
| **What** | `index.html` and `app.js` are a single-page demo with search/ask only. Response parsing is tightly coupled to `contract_date`, `file_path`, and old `CitationItem` shape |
| **Where** | `frontend/index.html`, `frontend/app.js` |
| **Impact** | No upload view, no retrieval mode selector, no citation cards with locators, no comparison view |
| **Resolution** | Full frontend rewrite (M10) |

---

## Cross-Reference Matrix

Shows which assumptions affect which donor modules:

| Module | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | A9 |
|---|---|---|---|---|---|---|---|---|---|
| `core/` | ● | | | | | | | | |
| `db/` | | | | ● | ● | | ● | ● | |
| `embedding/` | | | | | | | | | |
| `retrieval/` | | | | ● | ● | | | | |
| `llm/` | | | | | | | | | |
| `answering/` | | | | | ● | | | | |
| `eval/` | | | | | ● | | | | |
| `chunking/` | | | ● | | ● | | | | |
| `ingestion/` | ● | ● | | ● | ● | | | | |
| `api/` | | | | ● | ● | ● | | | |
| `frontend/` | | | | | | | | | ● |

---

## Resolution Timeline

| Assumption | Resolved At |
|---|---|
| A1 (folder corpus) | M4 |
| A2 (PDF/DOCX only) | M5 |
| A3 (contract chunking) | M6 |
| A4 (contract_date) | M3 |
| A5 (flat schema) | M3 |
| A6 (no upload) | M4 |
| A7 (no enrichment cols) | M3 |
| A8 (hardcoded dim) | M2 |
| A9 (static frontend) | M10 |
