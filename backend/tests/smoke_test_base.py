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
from app.llm.prompts import REPAIR_PROMPT, SECOND_PASS_PROMPT, SYSTEM_PROMPT, generate_second_pass_prompt, generate_user_prompt
from sqlalchemy import text


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EVAL_FIXTURE_DIR = FIXTURE_DIR / "eval"

_VECTOR_DIM_CACHE: int | None = None


def expected_vector_dim() -> int:
    """Dimension of the live chunks.embedding column.

    AR1: synthetic test vectors must match whatever embedding profile is
    validly promoted; the suite must never hardcode a model's dimension.
    """
    global _VECTOR_DIM_CACHE
    if _VECTOR_DIM_CACHE is None:
        with engine.connect() as conn:
            typmod = conn.execute(
                text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                )
            ).scalar_one()
        if typmod is None or int(typmod) <= 0:
            typmod = get_expected_dim()
        _VECTOR_DIM_CACHE = int(typmod)
    return _VECTOR_DIM_CACHE


def basis_vector(*head: float) -> list[float]:
    """Synthetic vector with the given leading components, zero-padded to the live dimension."""
    values = list(head)
    return values + [0.0] * (expected_vector_dim() - len(values))


class SmokeTestBase(unittest.TestCase):
    def setUp(self):
        self._temp_cleanup_paths: list[Path] = []
        # AR1: pin the runtime posture the smoke tests are written against so
        # results do not depend on the developer's .env (access strategy,
        # auth mode, or app env). ACL-specific tests override these locally.
        self._orig_posture = (settings.APP_ENV, settings.AUTH_MODE, settings.ACCESS_STRATEGY, settings.AUTH_ENABLED)
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "dev"
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"
        # Config default; tests that exercise auth enable it explicitly.
        settings.AUTH_ENABLED = False
        from app.auth.context import AuthenticatedUser, set_current_user

        self._auth_context_token = set_current_user(
            AuthenticatedUser(
                user_id="dev-test-admin",
                email=settings.DEV_TEST_ADMIN_EMAIL,
                roles=["admin"],
                groups=[],
            )
        )
        self._snapshot_active_profiles()
        self._pin_test_profiles()

    def _snapshot_active_profiles(self):
        """AR1: tests that activate/promote profiles must not leave the dev DB's
        live configuration mutated (the audit found unpromoted draft profiles
        active as live — a state these smoke tests themselves used to create)."""
        with engine.connect() as conn:
            self._active_profiles_snapshot = {
                row[0]: row[1]
                for row in conn.execute(text("SELECT profile_type, profile_name FROM active_profiles")).fetchall()
            }

    def _restore_active_profiles(self):
        from app.db.repo_profiles import set_active_profile
        from app.profiles.resolver import invalidate_cache

        with engine.connect() as conn:
            current = {
                row[0]: row[1]
                for row in conn.execute(text("SELECT profile_type, profile_name FROM active_profiles")).fetchall()
            }
        changed = False
        for profile_type, profile_name in self._active_profiles_snapshot.items():
            if current.get(profile_type) != profile_name:
                set_active_profile(profile_type, profile_name)
                changed = True
        if changed:
            invalidate_cache()
            from app.db.repo_tuning_configs import sync_live_configuration_record

            sync_live_configuration_record()

    def _pin_test_profiles(self):
        """AR1: pin retrieval/reranker/LLM resolution to deterministic code-default
        profiles so suite results do not depend on whatever the dev DB has tuned
        live (the audit found an unpromoted draft active as the live profile).
        The embedding profile stays live: synthetic vectors must match the real
        chunks.embedding column dimension."""
        import app.core_rag.retrieval as retrieval_module
        import app.eval.compare_eval as compare_eval_module
        import app.eval.retrieval_eval as retrieval_eval_module
        import app.profiles.resolver as resolver_module
        from app.profiles.models import LLMProfileConfig, RerankerProfileConfig, RetrievalProfileConfig

        test_retrieval = RetrievalProfileConfig()
        test_reranker = RerankerProfileConfig()
        test_llm = LLMProfileConfig()
        self._profile_patches: list[tuple[object, str, object]] = []

        def _patch(target, attr_name, value):
            self._profile_patches.append((target, attr_name, getattr(target, attr_name)))
            setattr(target, attr_name, value)

        # AR8: pins still honor request-scoped overrides (profile_overrides),
        # so sandbox/candidate-eval bundles apply during tests while the live
        # default stays deterministic (AR1).
        def _eff(kind, default):
            return lambda: resolver_module.current_profile_overrides().get(kind) or default

        _patch(resolver_module, "get_effective_retrieval", _eff("retrieval", test_retrieval))
        _patch(retrieval_module, "get_effective_retrieval", _eff("retrieval", test_retrieval))
        _patch(retrieval_eval_module, "get_effective_retrieval", _eff("retrieval", test_retrieval))
        _patch(compare_eval_module, "get_effective_retrieval", _eff("retrieval", test_retrieval))
        _patch(resolver_module, "get_effective_reranker", _eff("reranker", test_reranker))
        _patch(retrieval_module, "get_effective_reranker", _eff("reranker", test_reranker))
        _patch(compare_eval_module, "get_effective_reranker", _eff("reranker", test_reranker))
        _patch(resolver_module, "get_effective_llm", _eff("llm", test_llm))

    def _unpin_test_profiles(self):
        """Opt-out for tests that intentionally exercise DB-backed profile
        activation: restores the real resolver functions for this test."""
        for target, attr_name, original in reversed(getattr(self, "_profile_patches", [])):
            setattr(target, attr_name, original)
        self._profile_patches = []

    def tearDown(self):
        from app.auth.context import reset_current_user

        for target, attr_name, original in reversed(getattr(self, "_profile_patches", [])):
            setattr(target, attr_name, original)
        self._restore_active_profiles()
        reset_current_user(self._auth_context_token)
        settings.APP_ENV, settings.AUTH_MODE, settings.ACCESS_STRATEGY, settings.AUTH_ENABLED = self._orig_posture
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
                vectors.append((row[0], basis_vector(1.0)))
            else:
                vectors.append((row[0], basis_vector(0.0, 1.0)))
        update_chunk_embeddings(vectors)
        return {"pdf_source_id": pdf_source_id, "docx_source_id": docx_source_id}

    def _delete_retrieval_records(self, source_ids):
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sources WHERE id = ANY(:source_ids)"),
                {"source_ids": list(source_ids)},
            )

    def _seed_seo_anomaly_records(self):
        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 200,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"seo-anomaly-{suffix}.pdf",
                    "storage_path": f"tests/seo-anomaly-{suffix}.pdf",
                    "hash_sha256": (suffix + "seo") * 4,
                },
            ).scalar_one()

        chunks = [
            {
                "name": "ground_truth_page_1",
                "chunk_index": 0,
                "heading": "Page 1",
                "section_path": "page:1",
                "chunk_text": (
                    "The space is saturated. Search results for free online games and specific game titles "
                    "are dominated by large aggregators, making it hard for a newcomer site to rank. "
                    "Incumbents also keep an SEO edge through embeddable content and trend-driven titles."
                ),
                "locator_json": {"page": 1, "chunk_window": 1, "chunk_window_total": 2},
            },
            {
                "name": "ground_truth_page_2",
                "chunk_index": 2,
                "heading": "Page 2",
                "section_path": "page:2",
                "chunk_text": (
                    "For a newcomer, cracking this space via SEO would be challenging unless they use a fresh "
                    "distribution approach or a niche."
                ),
                "locator_json": {"page": 2, "chunk_window": 1, "chunk_window_total": 3},
            },
            {
                "name": "wrong_page_10_a",
                "chunk_index": 26,
                "heading": "Page 10",
                "section_path": "page:10",
                "chunk_text": (
                    "A newcomer can launch a web clone and do some SEO around it to siphon traffic. "
                    "Large aggregators have not saturated every niche."
                ),
                "locator_json": {"page": 10, "chunk_window": 1, "chunk_window_total": 3},
            },
            {
                "name": "wrong_page_10_b",
                "chunk_index": 27,
                "heading": "Page 10",
                "section_path": "page:10",
                "chunk_text": (
                    "A newcomer can move fast in a niche and use SEO as one route for attracting users. "
                    "Execution and marketing matter."
                ),
                "locator_json": {"page": 10, "chunk_window": 2, "chunk_window_total": 3},
            },
        ]

        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": chunk["chunk_index"],
                    "heading": chunk["heading"],
                    "section_path": chunk["section_path"],
                    "chunk_text": chunk["chunk_text"],
                    "token_count": len(chunk["chunk_text"].split()),
                    "locator_json": chunk["locator_json"],
                    "provenance_json": {"test": "seo_anomaly", "name": chunk["name"]},
                }
                for chunk in chunks
            ],
        )

        similarity_by_name = {
            "ground_truth_page_1": 0.55092,
            "ground_truth_page_2": 0.54631,
            "wrong_page_10_a": 0.61401,
            "wrong_page_10_b": 0.63164,
        }

        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, chunk_index, provenance_json FROM chunks WHERE source_id = :source_id ORDER BY chunk_index ASC"),
                {"source_id": source_id},
            ).fetchall()

        chunk_ids: dict[str, int] = {}
        embeddings: list[tuple[int, list[float]]] = []
        for row in rows:
            provenance = dict(row[2] or {})
            name = provenance["name"]
            chunk_ids[name] = row[0]
            similarity = similarity_by_name[name]
            embeddings.append((row[0], basis_vector(similarity, (1 - (similarity ** 2)) ** 0.5)))

        update_chunk_embeddings(embeddings)
        return {"source_id": source_id, "chunk_ids": chunk_ids}

    def _source_chunk_count(self, source_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM chunks WHERE source_id = :source_id"), {"source_id": source_id}).scalar_one()

    def _source_part_count(self, source_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT COUNT(*) FROM source_parts WHERE source_id = :source_id"),
                {"source_id": source_id},
            ).scalar_one()
