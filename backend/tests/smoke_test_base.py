import asyncio
import json
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from app.adapters import get_adapter, parse_source_bytes
from app.api.ask import ask_endpoint
from app.api.compare import compare_endpoint
from app.api.search import search_endpoint
from app.core.config import REPO_ROOT, settings
from app.core.logging import logger
from app.main import app
from app.db.migrate import run_migrations
from app.db.repo_jobs import get_ingestion_job
from app.db.repo_sources import get_source_by_id
from app.db.verify_db import collect_db_checks
from app.graph import (
    analyze_temporal_metadata,
    ensure_graph_artifacts,
    explain_graph_result,
    get_graph_store,
    normalize_ontology_tags,
    retrieve_graph_candidates,
    run_enrichment_extractors,
)
from app.core_rag.answering import AskRequest, AskResponse, CitationItem, CompareRequest, CompareResponse
from app.core_rag.query_router import route_query
from app.core_rag.retrieval import SearchFilters, SearchRequest, SearchResponse, SearchResultItem, perform_search
from app.db.db import engine
from app.db.repo_chunks import get_chunks_to_embed, insert_chunks, update_chunk_embeddings
from app.db.repo_search import search_chunks, search_chunks_keyword
from app.embedding.embedder import embed_texts, get_expected_dim, get_model
from app.embedding.process import process_embeddings
from app.eval.retrieval_eval import evaluate_question, parse_demo_questions
from app.eval.enriched_eval import (
    evaluate_answer_case,
    evaluate_compare_case,
    load_answer_cases,
    load_compare_cases,
    run_enriched_eval,
)
from app.eval.retrieval_eval import load_eval_cases, run_retrieval_eval
from app.ingestion.chunking import chunk_parsed_document
from app.ingestion.enrichment import get_enrichment_artifact_versions, run_post_ingestion_enrichment
from app.ingestion.jobs import (
    chunk_uploaded_source_file,
    delete_uploaded_source,
    parse_uploaded_source_file,
    process_upload,
    process_upload_batch,
)
from app.llm.client import generate_answer, is_llm_ready, verify_llm_ready
from app.llm.prompts import REPAIR_PROMPT, SYSTEM_PROMPT, generate_user_prompt
from sqlalchemy import text


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EVAL_FIXTURE_DIR = FIXTURE_DIR / "eval"


class SmokeTestBase(unittest.TestCase):
    def setUp(self):
        self._temp_cleanup_paths: list[Path] = []

    def tearDown(self):
        for path in self._temp_cleanup_paths:
            if path.exists():
                path.unlink()

    def _track_temp_cleanup_path(self, path: Path) -> Path:
        self._temp_cleanup_paths.append(path)
        return path

    def _chunk_id_for_source(self, source_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT id FROM chunks WHERE source_id = :source_id ORDER BY chunk_index ASC LIMIT 1"),
                {"source_id": source_id},
            ).scalar_one()

    def _seed_chunk_records(self):
        suffix = uuid4().hex[:8]
        storage_path = f"tests/{suffix}.pdf"
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 123,
                        'chunked', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"seed-{suffix}.pdf",
                    "storage_path": storage_path,
                    "hash_sha256": suffix * 8,
                },
            ).scalar_one()

        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Page 1",
                    "section_path": "page:1",
                    "chunk_text": "Embedding test chunk one.",
                    "token_count": 4,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": True},
                },
                {
                    "chunk_index": 1,
                    "heading": "Page 2",
                    "section_path": "page:2",
                    "chunk_text": "Embedding test chunk two.",
                    "token_count": 4,
                    "locator_json": {"page": 2},
                    "provenance_json": {"test": True},
                },
            ],
        )
        return source_id

    def _delete_seed_source(self, source_id: int):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sources WHERE id = :source_id"), {"source_id": source_id})

    def _seed_retrieval_records(self):
        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            pdf_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 100,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"retrieval-pdf-{suffix}.pdf",
                    "storage_path": f"tests/retrieval-{suffix}.pdf",
                    "hash_sha256": (suffix + "a") * 4,
                },
            ).scalar_one()
            docx_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'docx', :hash_sha256, 100,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"retrieval-docx-{suffix}.docx",
                    "storage_path": f"tests/retrieval-{suffix}.docx",
                    "hash_sha256": (suffix + "b") * 4,
                },
            ).scalar_one()

        insert_chunks(
            pdf_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "PDF Match",
                    "section_path": "page:1",
                    "chunk_text": "alpha semantic vector match text",
                    "token_count": 5,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "retrieval"},
                }
            ],
        )
        insert_chunks(
            docx_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "DOCX Match",
                    "section_path": "Section 1",
                    "chunk_text": "keywordbanana lexical signal text",
                    "token_count": 4,
                    "locator_json": {"block": 1},
                    "provenance_json": {"test": "retrieval"},
                }
            ],
        )

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, source_id
                    FROM chunks
                    WHERE source_id IN (:pdf_source_id, :docx_source_id)
                    ORDER BY source_id ASC, chunk_index ASC
                    """
                ),
                {"pdf_source_id": pdf_source_id, "docx_source_id": docx_source_id},
            ).fetchall()
        vectors = []
        for row in rows:
            if row[1] == pdf_source_id:
                vectors.append((row[0], [1.0] + [0.0] * 383))
            else:
                vectors.append((row[0], [0.0, 1.0] + [0.0] * 382))
        update_chunk_embeddings(vectors)
        return {"pdf_source_id": pdf_source_id, "docx_source_id": docx_source_id}

    def _delete_retrieval_records(self, source_ids):
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sources WHERE id = ANY(:source_ids)"),
                {"source_ids": list(source_ids)},
            )

    def _source_chunk_count(self, source_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM chunks WHERE source_id = :source_id"), {"source_id": source_id}).scalar_one()

    def _source_part_count(self, source_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT COUNT(*) FROM source_parts WHERE source_id = :source_id"),
                {"source_id": source_id},
            ).scalar_one()
