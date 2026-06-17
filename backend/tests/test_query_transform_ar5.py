from tests.smoke_test_base import *

import time

import app.core_rag.query_transform as qt
from app.core_rag.query_transform import transform_query
from app.profiles.models import RetrievalProfileConfig


def _pin_generate(self, fn):
    original = qt._generate
    qt._generate = fn
    self.addCleanup(lambda: setattr(qt, "_generate", original))


class QueryTransformLLMBackedAR5Tests(SmokeTestBase):
    """AR5: the transform stub (hardcoded synonym dict, whitespace rewrite,
    literal HyDE prefix) is replaced by real LLM-backed generation."""

    def test_hardcoded_expansion_dictionary_is_deleted(self):
        # Audit remediation: the 5-entry synonym dict must be gone.
        self.assertFalse(hasattr(qt, "_EXPANSIONS"))
        self.assertFalse(hasattr(qt, "_hyde_query"))
        self.assertFalse(hasattr(qt, "_expanded_query"))

    def test_disabled_transform_returns_original(self):
        result = transform_query("quarterly liability review", RetrievalProfileConfig())
        self.assertFalse(result.trace["enabled"])
        self.assertEqual(result.effective_query, "quarterly liability review")
        self.assertEqual(result.generated_queries, [])

    def test_llm_backed_variants_are_generated_and_traced(self):
        responses = {
            qt._REWRITE_SYSTEM: "quarterly liability obligations review",
            qt._EXPANSION_SYSTEM: "fourth quarter, indemnity, responsibility",
            qt._HYDE_SYSTEM: "The quarterly review summarizes liability and indemnity obligations.",
        }
        _pin_generate(self, lambda system_prompt, user_prompt, **_: {"success": True, "content": responses[system_prompt]})
        result = transform_query(
            "quarterly liability review",
            RetrievalProfileConfig(query_transform_enabled=True, rewrite_enabled=True, expansion_enabled=True, hyde_enabled=True, transform_max_variants=4),
        )
        self.assertEqual(result.trace["llm_calls"], 3)
        self.assertEqual(result.trace["variant_status"]["rewrite"], "generated")
        self.assertEqual(result.trace["variant_status"]["expansion"], "generated")
        self.assertEqual(result.trace["variant_status"]["hyde"], "generated")
        self.assertEqual(len(result.generated_queries), 3)
        # Expansion appends terms to the original rather than replacing it.
        expansion_variant = next(d["query"] for d in result.variant_details if d["strategy"] == "expansion")
        self.assertIn("indemnity", expansion_variant)
        self.assertIsNone(result.trace["fallback_reason"])

    def test_llm_unavailable_falls_back_to_original(self):
        # DoD: with the LLM unreachable, the transform still completes via fallback.
        _pin_generate(self, lambda system_prompt, user_prompt, **_: {"success": False, "error": "connection refused"})
        result = transform_query(
            "termination clause obligations",
            RetrievalProfileConfig(query_transform_enabled=True, rewrite_enabled=True, hyde_enabled=True),
        )
        self.assertEqual(result.effective_query, "termination clause obligations")
        self.assertEqual(result.generated_queries, [])
        self.assertEqual(result.trace["variant_status"]["rewrite"], "llm_unavailable")
        self.assertIsNotNone(result.trace["fallback_reason"])

    def test_timeout_budget_is_enforced_across_strategies(self):
        # The first call consumes the whole budget; later strategies are skipped.
        def slow_then_unreached(system_prompt, user_prompt, *, timeout_s, **_):
            if system_prompt == qt._REWRITE_SYSTEM:
                time.sleep(0.06)
                return {"success": True, "content": "rewritten budget query"}
            raise AssertionError("second strategy must be skipped once budget is exhausted")

        _pin_generate(self, slow_then_unreached)
        result = transform_query(
            "budget query",
            RetrievalProfileConfig(query_transform_enabled=True, rewrite_enabled=True, expansion_enabled=True, transform_timeout_ms=50),
        )
        self.assertEqual(result.trace["variant_status"].get("expansion"), "skipped_budget_exhausted")
        self.assertEqual(result.trace["fallback_reason"], "timeout_budget_exhausted")

    def test_timeout_result_records_fallback_reason(self):
        _pin_generate(self, lambda system_prompt, user_prompt, **_: {"success": False, "error": "transform timeout (0.7s)", "timeout": True})
        result = transform_query(
            "indemnity scope",
            RetrievalProfileConfig(query_transform_enabled=True, rewrite_enabled=True),
        )
        self.assertEqual(result.trace["variant_status"]["rewrite"], "timeout")
        self.assertEqual(result.effective_query, "indemnity scope")


class MultiQueryFanOutAR5Tests(SmokeTestBase):
    """AR5: variants are retrieved separately and fused, behind multi_query_enabled,
    instead of concatenated into one query string."""

    def _seed_two_topic_corpus(self):
        suffix = uuid4().hex[:8]
        token_a = f"alphatopic{suffix}"
        token_b = f"betatopic{suffix}"
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (:f, :p, 'pdf', 'public', :h, 100, 'embedded', 'not_started', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {"f": f"ar5-mq-{suffix}.pdf", "p": f"tests/ar5-mq-{suffix}.pdf", "h": (suffix + "ar5") * 4},
            ).scalar_one()
        self.addCleanup(self._delete_retrieval_records, [source_id])
        insert_chunks(
            source_id,
            [
                {"chunk_index": 0, "heading": "A", "section_path": "p:0", "chunk_text": f"{token_a} content about the first distinct subject.", "token_count": 8, "locator_json": {}, "provenance_json": {}},
                {"chunk_index": 1, "heading": "B", "section_path": "p:1", "chunk_text": f"{token_b} content about a second unrelated subject.", "token_count": 8, "locator_json": {}, "provenance_json": {}},
            ],
        )
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, chunk_index FROM chunks WHERE source_id = :s ORDER BY chunk_index"), {"s": source_id}).fetchall()
        ids = {index: chunk_id for chunk_id, index in rows}
        update_chunk_embeddings([(ids[0], basis_vector(1.0, 0.0)), (ids[1], basis_vector(0.0, 1.0))])
        return token_a, token_b, ids

    def _search_with_profile(self, *, profile, question):
        # Restore within the test body (not addCleanup) so the harness tearDown,
        # which runs afterward, correctly re-restores the real resolver.
        import app.core_rag.retrieval as retrieval_module

        original_resolver = retrieval_module.get_effective_retrieval
        retrieval_module.get_effective_retrieval = lambda: profile
        try:
            return perform_search(SearchRequest(question=question, k=5, mode="keyword"))
        finally:
            retrieval_module.get_effective_retrieval = original_resolver

    def test_multi_query_fan_out_fuses_variant_only_chunk(self):
        token_a, token_b, ids = self._seed_two_topic_corpus()
        # Rewrite variant points at the second topic; keyword mode keeps it deterministic.
        _pin_generate(self, lambda system_prompt, user_prompt, **_: {"success": True, "content": token_b})
        profile = RetrievalProfileConfig(
            default_mode="keyword",
            query_transform_enabled=True,
            rewrite_enabled=True,
            multi_query_enabled=True,
            transform_max_variants=2,
        )
        response = self._search_with_profile(profile=profile, question=token_a)
        mq = response.debug_info["multi_query"]
        self.assertTrue(mq["applied"])
        self.assertEqual(mq["variant_count"], 1)
        self.assertGreaterEqual(mq["per_variant"][0]["count"], 1)
        result_ids = {item.chunk_id for item in response.results}
        # The variant-only chunk (second topic) is surfaced via fan-out fusion.
        self.assertIn(ids[1], result_ids)

    def test_multi_query_disabled_does_not_fan_out(self):
        token_a, token_b, ids = self._seed_two_topic_corpus()
        _pin_generate(self, lambda system_prompt, user_prompt, **_: {"success": True, "content": token_b})
        profile = RetrievalProfileConfig(
            default_mode="keyword",
            query_transform_enabled=True,
            rewrite_enabled=True,
            multi_query_enabled=False,
            transform_max_variants=2,
        )
        response = self._search_with_profile(profile=profile, question=token_a)
        self.assertFalse(response.debug_info["multi_query"]["applied"])
        self.assertEqual(response.debug_info["multi_query"]["reason"], "disabled")
