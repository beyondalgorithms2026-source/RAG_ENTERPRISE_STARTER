import inspect
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from tests.smoke_test_base import SmokeTestBase, basis_vector


class RetrievalEnhancementsAR14Tests(SmokeTestBase):
    def _seed_source(self, *, group: str | None = None) -> tuple[int, list[int]]:
        from app.db.db import engine
        from app.db.repo_acl import assign_document_acl
        from app.db.repo_chunks import insert_chunks, update_chunk_embeddings

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256,
                        file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
                    )
                        VALUES (:f, :p, 'txt', :sensitivity, :h, 10, 'embedded', 'not_started', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {
                    "f": f"ar14-{suffix}.txt",
                    "p": f"tests/ar14-{suffix}.txt",
                    "sensitivity": "internal" if group else "public",
                    "h": (suffix + "14") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Zeta Policy",
                    "chunk_text": "General operational guidance without the distinctive heading term.",
                    "token_count": 8,
                },
                {
                    "chunk_index": 1,
                    "heading": "General Notes",
                    "chunk_text": "The zeta policy is mentioned in ordinary body text.",
                    "token_count": 9,
                },
                {
                    "chunk_index": 2,
                    "heading": "Different Evidence",
                    "chunk_text": "Unrelated material for diversity selection.",
                    "token_count": 6,
                },
            ],
        )
        with engine.connect() as conn:
            chunk_ids = [
                int(row[0])
                for row in conn.execute(
                    text("SELECT id FROM chunks WHERE source_id = :source_id ORDER BY chunk_index"),
                    {"source_id": source_id},
                ).fetchall()
            ]
        update_chunk_embeddings(
            [
                (chunk_ids[0], basis_vector(1.0, 0.0)),
                (chunk_ids[1], basis_vector(0.999, 0.0447)),
                (chunk_ids[2], basis_vector(0.0, 1.0)),
            ]
        )
        if group:
            assign_document_acl(source_id=source_id, group_names=[group])
        return source_id, chunk_ids

    def test_real_mmr_selects_diverse_candidate_and_traces_fallback(self):
        import app.db.repo_chunks as chunks_repo
        from app.core_rag.reranker import apply_mmr

        candidates = [
            {"chunk_id": 1, "rerank_score": 1.0},
            {"chunk_id": 2, "rerank_score": 0.99},
            {"chunk_id": 3, "rerank_score": 0.8},
        ]
        original_fetch = chunks_repo.fetch_chunk_embeddings
        try:
            chunks_repo.fetch_chunk_embeddings = lambda ids: {
                1: [1.0, 0.0],
                2: [0.999, 0.0447],
                3: [0.0, 1.0],
            }
            policy = {"mmr": {"enabled": True, "lambda": 0.5}}
            selected = apply_mmr(candidates, policy, top_k=2)
            self.assertEqual([item["chunk_id"] for item in selected], [1, 3])
            self.assertTrue(policy["mmr"]["applied"])
            self.assertGreaterEqual(policy["mmr"]["latency_ms"], 0.0)

            chunks_repo.fetch_chunk_embeddings = lambda ids: {1: [1.0, 0.0]}
            fallback_policy = {"mmr": {"enabled": True, "lambda": 0.5}}
            fallback = apply_mmr(candidates, fallback_policy, top_k=2)
            self.assertEqual([item["chunk_id"] for item in fallback], [1, 2])
            self.assertEqual(fallback_policy["mmr"]["reason"], "missing_candidate_embeddings")
        finally:
            chunks_repo.fetch_chunk_embeddings = original_fetch

    def test_weighted_fts_promotes_heading_and_trigger_tracks_heading_updates(self):
        from app.db.db import engine
        from app.db.repo_search import keyword_vector_mode, search_chunks_keyword

        source_id, chunk_ids = self._seed_source()
        try:
            with keyword_vector_mode("body"):
                body_results = search_chunks_keyword("zeta", k=3, source_id=source_id)
            with keyword_vector_mode("stored"):
                weighted_results = search_chunks_keyword("zeta", k=3, source_id=source_id)
            self.assertEqual(body_results[0]["chunk_id"], chunk_ids[1])
            self.assertEqual(weighted_results[0]["chunk_id"], chunk_ids[0], weighted_results)

            with engine.begin() as conn:
                conn.execute(text("UPDATE chunks SET heading = 'Omega Policy' WHERE id = :id"), {"id": chunk_ids[0]})
            self.assertEqual(search_chunks_keyword("omega", k=1, source_id=source_id)[0]["chunk_id"], chunk_ids[0])
        finally:
            self._delete_retrieval_records([source_id])

    def test_mmr_embedding_fetch_reapplies_sql_acl(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.core.config import settings
        from app.db.repo_acl import sync_authenticated_user
        from app.db.repo_chunks import fetch_chunk_embeddings

        allowed_source, allowed_chunks = self._seed_source(group="ar14-alpha")
        blocked_source, blocked_chunks = self._seed_source(group="ar14-beta")
        user = AuthenticatedUser(
            user_id=f"ar14-user-{uuid4().hex[:6]}",
            email=f"ar14-{uuid4().hex[:6]}@example.test",
            roles=["user"],
            groups=["ar14-alpha"],
        )
        original_auth_enabled = settings.AUTH_ENABLED
        original_strategy = settings.ACCESS_STRATEGY
        settings.AUTH_ENABLED = True
        settings.ACCESS_STRATEGY = "document_acl"
        sync_authenticated_user(user)
        token = set_current_user(user)
        try:
            fetched = fetch_chunk_embeddings([allowed_chunks[0], blocked_chunks[0]])
            self.assertIn(allowed_chunks[0], fetched)
            self.assertNotIn(blocked_chunks[0], fetched)
        finally:
            reset_current_user(token)
            settings.AUTH_ENABLED = original_auth_enabled
            settings.ACCESS_STRATEGY = original_strategy
            self._delete_retrieval_records([allowed_source, blocked_source])

    def test_scoring_overrides_are_request_scoped_and_causal_vocabulary_is_gone(self):
        import app.core_rag.retrieval as retrieval
        import app.core_rag.reranker as reranker
        from app.core_rag.retrieval_scoring import get_retrieval_scoring, retrieval_scoring_overrides

        baseline = get_retrieval_scoring().graph_existing_weight
        with retrieval_scoring_overrides(graph_existing_weight=0.0):
            self.assertEqual(get_retrieval_scoring().graph_existing_weight, 0.0)
        self.assertEqual(get_retrieval_scoring().graph_existing_weight, baseline)
        source = inspect.getsource(retrieval._build_anchor_window_candidates)
        self.assertNotIn("causal_terms", source)
        self.assertNotIn("challenging", source)
        self.assertNotIn("placeholder_reserved_for_future_milestone", inspect.getsource(reranker))

    def test_ablation_report_has_paired_verdicts_and_global_control(self):
        from app.api.admin import get_retrieval_evidence
        from app.eval.retrieval_ablation import CASES_PATH, REPORT_PATH, build_report

        self.assertTrue(CASES_PATH.exists())
        report = build_report()
        self.assertEqual(report["decision_policy"]["minimum_gain"], 0.01)
        self.assertTrue(all(item["verdict"] in {"adopted", "retired"} for item in report["evidence"]))
        self.assertEqual(next(item for item in report["evidence"] if item["feature"] == "mmr")["chosen"], "lambda_0_5")
        self.assertEqual(report["adopted_scoring"]["graph_existing_weight"], 0.20)
        self.assertEqual(report["adopted_scoring"]["temporal_weight"], 0.10)
        self.assertIn("demo_causal_terms_vocabulary", report["removed"])
        self.assertTrue(REPORT_PATH.exists())
        committed = json.loads(Path(REPORT_PATH).read_text(encoding="utf-8"))
        self.assertIsNotNone(committed["global_control"]["before"])
        self.assertEqual(get_retrieval_evidence()["gate"], "no_unfalsifiable_tuning")


if __name__ == "__main__":
    import unittest

    unittest.main()
