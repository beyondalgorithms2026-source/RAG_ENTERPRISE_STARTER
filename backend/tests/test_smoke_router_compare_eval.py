from tests.smoke_test_base import *


class SmokeTestRouterCompareEval(SmokeTestBase):
    def test_m8_rerank_policy_can_gate_by_mode_corpus_depth_and_latency(self):
        import app.core_rag.reranker as reranker_module
        import app.profiles.resolver as resolver_module
        from app.profiles.models import RerankerProfileConfig

        original_get_effective_reranker = resolver_module.get_effective_reranker
        resolver_module.get_effective_reranker = lambda: RerankerProfileConfig(
            enabled=True,
            enabled_modes=["hybrid"],
            enabled_corpora=["finance"],
            min_candidate_count=3,
            latency_budget_ms=40,
            mmr_enabled=True,
        )
        try:
            eligible = reranker_module.evaluate_rerank_policy(
                resolved_mode="hybrid",
                chunks=[{"chunk_id": 1}, {"chunk_id": 2}, {"chunk_id": 3}],
                candidate_corpora=["finance"],
                search_latency_ms=18,
            )
            wrong_mode = reranker_module.evaluate_rerank_policy(
                resolved_mode="keyword",
                chunks=[{"chunk_id": 1}, {"chunk_id": 2}, {"chunk_id": 3}],
                candidate_corpora=["finance"],
                search_latency_ms=18,
            )
            too_slow = reranker_module.evaluate_rerank_policy(
                resolved_mode="hybrid",
                chunks=[{"chunk_id": 1}, {"chunk_id": 2}, {"chunk_id": 3}],
                candidate_corpora=["finance"],
                search_latency_ms=61,
            )
        finally:
            resolver_module.get_effective_reranker = original_get_effective_reranker

        self.assertTrue(eligible["eligible"])
        self.assertEqual(eligible["reason"], "eligible_policy_match")
        self.assertEqual(eligible["observed_corpora"], ["finance"])
        self.assertTrue(eligible["mmr"]["enabled"])
        self.assertEqual(eligible["mmr"]["reason"], "eligible")
        self.assertFalse(wrong_mode["eligible"])
        self.assertEqual(wrong_mode["reason"], "mode_not_enabled")
        self.assertFalse(too_slow["eligible"])
        self.assertEqual(too_slow["reason"], "latency_budget_exceeded")

    def test_m8_search_trace_exposes_applied_mmr(self):
        from types import SimpleNamespace

        import app.core_rag.reranker as reranker_module
        import app.core_rag.retrieval as retrieval_module
        import app.profiles.resolver as resolver_module
        from app.profiles.models import RerankerProfileConfig

        original_get_effective_reranker = retrieval_module.get_effective_reranker
        original_resolver_get_effective_reranker = resolver_module.get_effective_reranker
        original_run_hybrid_baseline = retrieval_module._run_hybrid_baseline
        original_apply_graph_and_temporal_layers = retrieval_module._apply_graph_and_temporal_layers
        original_get_sources_by_ids = retrieval_module.get_sources_by_ids
        original_rerank = reranker_module.rerank
        original_fetch_embeddings = None
        try:
            patched_reranker_profile = lambda: RerankerProfileConfig(
                enabled=True,
                enabled_modes=["hybrid"],
                enabled_corpora=["ops"],
                min_candidate_count=2,
                latency_budget_ms=100,
                mmr_enabled=True,
            )
            retrieval_module.get_effective_reranker = patched_reranker_profile
            resolver_module.get_effective_reranker = patched_reranker_profile
            retrieval_module._run_hybrid_baseline = lambda **kwargs: (
                [
                    {
                        "chunk_id": 11,
                        "source_id": 101,
                        "source_part_id": None,
                        "file_name": "ops-a.pdf",
                        "source_type": "pdf",
                        "heading": "Ops A",
                        "locator": "page=1",
                        "snippet": "ops evidence A",
                        "distance": 0.1,
                        "chunk_index": 0,
                        "vector_score": 0.9,
                        "keyword_score": 0.5,
                        "rank_score": 1.0,
                        "combined_score": 0.8,
                    },
                    {
                        "chunk_id": 12,
                        "source_id": 102,
                        "source_part_id": None,
                        "file_name": "ops-b.pdf",
                        "source_type": "pdf",
                        "heading": "Ops B",
                        "locator": "page=2",
                        "snippet": "ops evidence B",
                        "distance": 0.2,
                        "chunk_index": 1,
                        "vector_score": 0.8,
                        "keyword_score": 0.4,
                        "rank_score": 0.8,
                        "combined_score": 0.7,
                    },
                ],
                4,
            )
            retrieval_module._apply_graph_and_temporal_layers = lambda **kwargs: (
                kwargs["raw_results"],
                kwargs["resolved_mode"],
                {"graph_used": False, "graph_reason": "not_requested", "temporal_used": False, "temporal_reason": "not_requested"},
            )
            retrieval_module.get_sources_by_ids = lambda ids: {
                101: SimpleNamespace(id=101, sensitivity_label="public", source_metadata_json={"corpus": "ops"}),
                102: SimpleNamespace(id=102, sensitivity_label="public", source_metadata_json={"corpus": "ops"}),
            }
            reranker_module.rerank = lambda question, chunks: [
                {**chunk, "rerank_score": 0.95 - (index * 0.1)}
                for index, chunk in enumerate(chunks)
            ]
            from app.db import repo_chunks

            original_fetch_embeddings = repo_chunks.fetch_chunk_embeddings
            repo_chunks.fetch_chunk_embeddings = lambda ids: {11: [1.0, 0.0], 12: [0.0, 1.0]}

            response = perform_search(SearchRequest(question="ops policy", k=2, mode="hybrid", debug=True))
        finally:
            retrieval_module.get_effective_reranker = original_get_effective_reranker
            resolver_module.get_effective_reranker = original_resolver_get_effective_reranker
            retrieval_module._run_hybrid_baseline = original_run_hybrid_baseline
            retrieval_module._apply_graph_and_temporal_layers = original_apply_graph_and_temporal_layers
            retrieval_module.get_sources_by_ids = original_get_sources_by_ids
            reranker_module.rerank = original_rerank
            if original_fetch_embeddings is not None:
                from app.db import repo_chunks

                repo_chunks.fetch_chunk_embeddings = original_fetch_embeddings

        self.assertEqual(response.mode, "hybrid")
        self.assertEqual(response.debug_info["rerank_policy"]["reason"], "eligible_policy_match")
        self.assertTrue(response.debug_info["rerank_policy"]["applied"])
        self.assertEqual(response.debug_info["rerank_policy"]["observed_corpora"], ["ops"])
        self.assertTrue(response.debug_info["rerank_policy"]["mmr"]["enabled"])
        self.assertTrue(response.debug_info["rerank_policy"]["mmr"]["applied"])
        self.assertEqual(response.debug_info["rerank_policy"]["mmr"]["reason"], "eval_proven_diversity")
        self.assertEqual(response.debug_info["latency_ms"]["rerank"], 0)

    def test_m7_router_selects_keyword_for_quote_like_lookup(self):
        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            decision = route_query(
                question='"keywordbanana" final words',
                explicit_mode=None,
                default_mode="hybrid",
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router

        self.assertEqual(decision.selected_mode, "keyword")
        self.assertEqual(decision.route_class, "lexical_first")
        self.assertEqual(decision.reason, "quote_like_exact_lookup_signal")
        self.assertTrue(decision.reason_details["quote_like"])

    def test_m7_router_selects_keyword_for_identifier_lookup(self):
        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            decision = route_query(
                question="Find case number AB-2024-0091",
                explicit_mode=None,
                default_mode="hybrid",
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router

        self.assertEqual(decision.selected_mode, "keyword")
        self.assertEqual(decision.route_class, "lexical_first")
        self.assertEqual(decision.reason, "identifier_lookup_signal")
        self.assertTrue(decision.reason_details["identifier_like"])

    def test_m7_router_routes_date_heavy_lexical_queries_keyword_first_without_temporal_artifacts(self):
        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            decision = route_query(
                question="What happened on January 15, 2024?",
                explicit_mode=None,
                default_mode="hybrid",
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router

        self.assertEqual(decision.selected_mode, "keyword")
        self.assertEqual(decision.preferred_mode, "keyword")
        self.assertEqual(decision.route_class, "lexical_first")
        self.assertEqual(decision.reason, "date_heavy_lexical_signal")
        self.assertTrue(decision.reason_details["date_heavy_lexical"])

    def test_m7_semantic_queries_remain_hybrid_with_route_details(self):
        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            decision = route_query(
                question="Summarize the benchmark policy coverage.",
                explicit_mode=None,
                default_mode="hybrid",
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router

        self.assertEqual(decision.selected_mode, "hybrid")
        self.assertEqual(decision.route_class, "semantic_first")
        self.assertEqual(decision.reason, "default_hybrid_router_policy")
        self.assertFalse(decision.reason_details["quote_like"])
        self.assertFalse(decision.reason_details["identifier_like"])

    def test_m17_manual_mode_selection_remains_intact_with_router_enabled(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_use_router = settings.USE_QUERY_ROUTER
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            settings.USE_QUERY_ROUTER = True
            response = perform_search(SearchRequest(question="Who reports to IBM?", k=5, mode="vector", debug=True))
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "vector")

    def test_m17_router_disabled_preserves_default_mode_behavior(self):
        seeded = self._seed_retrieval_records()

        original_use_router = settings.USE_QUERY_ROUTER
        original_retrieval_mode = settings.RETRIEVAL_MODE
        try:
            settings.USE_QUERY_ROUTER = False
            settings.RETRIEVAL_MODE = "keyword"
            response = perform_search(
                SearchRequest(
                    question='"keywordbanana"',
                    k=5,
                    debug=True,
                    filters=SearchFilters(source_id=seeded["docx_source_id"]),
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            settings.RETRIEVAL_MODE = original_retrieval_mode
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "keyword")
        self.assertEqual(response.results[0].source_id, seeded["docx_source_id"])

    def test_m7_search_debug_trace_exposes_route_reason_details(self):
        seeded = self._seed_retrieval_records()

        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            response = perform_search(
                SearchRequest(
                    question='"keywordbanana" final words',
                    k=5,
                    debug=True,
                    filters=SearchFilters(source_id=seeded["docx_source_id"]),
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "keyword")
        self.assertEqual(response.debug_info["route_reason"], "quote_like_exact_lookup_signal")
        self.assertEqual(response.debug_info["route_class"], "lexical_first")
        self.assertEqual(response.debug_info["preferred_mode"], "keyword")
        self.assertTrue(response.debug_info["route_details"]["quote_like"])

    def test_m7_router_benchmark_cases_cover_quote_code_semantic_temporal_sets(self):
        cases = json.loads((EVAL_FIXTURE_DIR / "router_cases.json").read_text(encoding="utf-8"))

        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            for case in cases:
                decision = route_query(
                    question=case["question"],
                    explicit_mode=None,
                    default_mode=case.get("default_mode", "hybrid"),
                    source_id=case.get("source_id"),
                )
                expected = case["expected"]
                self.assertEqual(decision.selected_mode, expected["selected_mode"], case["id"])
                self.assertEqual(decision.preferred_mode, expected["preferred_mode"], case["id"])
                self.assertEqual(decision.route_class, expected["route_class"], case["id"])
                self.assertEqual(decision.reason, expected["reason"], case["id"])
                for key, value in expected.get("route_details", {}).items():
                    self.assertEqual(decision.reason_details[key], value, case["id"])
        finally:
            settings.USE_QUERY_ROUTER = original_use_router

    def test_m17_router_selects_keyword_for_exact_lookup_when_mode_omitted(self):
        seeded = self._seed_retrieval_records()

        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            response = perform_search(
                SearchRequest(
                    question='"keywordbanana"',
                    k=5,
                    debug=True,
                    filters=SearchFilters(source_id=seeded["docx_source_id"]),
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "keyword")
        self.assertEqual(response.results[0].source_id, seeded["docx_source_id"])

    def test_m17_router_falls_back_to_hybrid_when_graph_artifacts_are_unavailable(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_use_router = settings.USE_QUERY_ROUTER
        original_enable_graph = settings.ENABLE_GRAPH
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            settings.USE_QUERY_ROUTER = True
            settings.ENABLE_GRAPH = False
            response = perform_search(
                SearchRequest(
                    question="Who reports to IBM?",
                    k=5,
                    filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                    debug=True,
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            settings.ENABLE_GRAPH = original_enable_graph
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "hybrid")

    def test_m17_router_selects_graph_hybrid_when_graph_is_ready(self):
        suffix = uuid4().hex[:8]
        source_hash = (suffix + "r") * 4
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m17-graph-{suffix}.pdf",
                    "storage_path": f"tests/m17-graph-{suffix}.pdf",
                    "hash_sha256": source_hash,
                    "source_metadata_json": json.dumps(
                        {
                            "graph": {
                                "artifact_version": "m14-graph-artifact-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
                                "storage_backend": "source_metadata_json",
                                "stats": {"node_count": 2, "edge_count": 1},
                                "snapshot": {
                                    "nodes": [
                                        {
                                            "node_id": "node::International Business Machines",
                                            "canonical_name": "International Business Machines",
                                            "aliases": ["IBM", "International Business Machines"],
                                            "chunk_refs": [{"chunk_id": None}],
                                        }
                                    ],
                                    "edges": [
                                        {
                                            "edge_id": "edge::Jane Doe::reports_to::International Business Machines",
                                            "subject": "Jane Doe",
                                            "relation_type": "reports_to",
                                            "object": "International Business Machines",
                                            "chunk_refs": [],
                                        }
                                    ],
                                },
                            }
                        }
                    ),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Router Baseline Chunk",
                    "section_path": "page:1",
                    "chunk_text": "General policy overview with no relationship details.",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m17-graph"},
                },
                {
                    "chunk_index": 1,
                    "heading": "Router Graph Match Chunk",
                    "section_path": "page:2",
                    "chunk_text": "Leadership appendix.",
                    "token_count": 2,
                    "locator_json": {"page": 2},
                    "provenance_json": {"test": "m17-graph"},
                },
            ],
        )
        with engine.connect() as conn:
            chunk_rows = conn.execute(
                text("SELECT id, chunk_index FROM chunks WHERE source_id = :source_id ORDER BY chunk_index ASC"),
                {"source_id": source_id},
            ).fetchall()
        chunk_id_by_index = {row[1]: row[0] for row in chunk_rows}
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sources
                    SET source_metadata_json = jsonb_set(
                        source_metadata_json,
                        '{graph,snapshot,nodes,0,chunk_refs}',
                        CAST(:node_refs AS jsonb),
                        true
                    )
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": source_id,
                    "node_refs": json.dumps([{"chunk_id": chunk_id_by_index[1], "chunk_index": 1, "locator": {"page": 2}}]),
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE sources
                    SET source_metadata_json = jsonb_set(
                        source_metadata_json,
                        '{graph,snapshot,edges,0,chunk_refs}',
                        CAST(:edge_refs AS jsonb),
                        true
                    )
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": source_id,
                    "edge_refs": json.dumps([{"chunk_id": chunk_id_by_index[1], "chunk_index": 1, "locator": {"page": 2}}]),
                },
            )
        update_chunk_embeddings(
            [
                (chunk_id_by_index[0], basis_vector(-1.0)),
                (chunk_id_by_index[1], basis_vector(0.0, 1.0)),
            ]
        )

        import app.core_rag.retrieval as retrieval_module

        original_use_router = settings.USE_QUERY_ROUTER
        original_enable_graph = settings.ENABLE_GRAPH
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            settings.USE_QUERY_ROUTER = True
            settings.ENABLE_GRAPH = True
            response = perform_search(
                SearchRequest(
                    question="Who reports to IBM?",
                    k=5,
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            settings.ENABLE_GRAPH = original_enable_graph
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(source_id)

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "graph_hybrid")
        self.assertEqual(response.results[0].heading, "Router Graph Match Chunk")

    def test_m17_router_selects_full_when_temporal_is_ready(self):
        suffix = uuid4().hex[:8]
        source_hash = (suffix + "s") * 4
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m17-full-{suffix}.pdf",
                    "storage_path": f"tests/m17-full-{suffix}.pdf",
                    "hash_sha256": source_hash,
                    "source_metadata_json": json.dumps(
                        {
                            "temporal": {
                                "artifact_version": "m13-rule-based-temporal-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
                                "date_bounds": {"earliest": "2024-01-15", "latest": "2024-12-31"},
                                "effective_window": {"start": "2024-01-15", "end": "2024-12-31"},
                                "document_version_refs": [{"value": "2.1"}],
                                "fallback_reason": None,
                            }
                        }
                    ),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Router Temporal Match Chunk",
                    "section_path": "page:1",
                    "chunk_text": "Policy summary.",
                    "token_count": 2,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m17-full"},
                }
            ],
        )
        update_chunk_embeddings([(self._chunk_id_for_source(source_id), basis_vector(1.0))])

        original_use_router = settings.USE_QUERY_ROUTER
        original_enable_temporal = settings.ENABLE_TEMPORAL
        try:
            settings.USE_QUERY_ROUTER = True
            settings.ENABLE_TEMPORAL = True
            response = perform_search(
                SearchRequest(
                    question="What applied in 2024 under version 2.1?",
                    k=5,
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            settings.ENABLE_TEMPORAL = original_enable_temporal
            self._delete_seed_source(source_id)

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "full")

    def test_m17_ask_flow_inherits_router_without_payload_changes(self):
        seeded = self._seed_retrieval_records()

        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            response = ask_endpoint(
                AskRequest(
                    question='"keywordbanana"',
                    k_chunks=4,
                    dry_run=True,
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            self._delete_retrieval_records(seeded.values())

        payload = response.model_dump()
        self.assertIn("debug_info", payload)
        self.assertEqual(payload["debug_info"]["mode"], "keyword")
        self.assertIn("system_prompt", payload["debug_info"])
        self.assertIn("user_prompt", payload["debug_info"])

    def test_m18_compare_requires_explicit_source_scope(self):
        response = compare_endpoint(CompareRequest(question="Compare these", source_ids=[1], dry_run=True))
        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertEqual(response.sources, [])
        self.assertEqual(response.debug_info["error"], "compare_requires_at_least_two_source_ids")

    def test_m18_compare_dry_run_groups_evidence_by_source_with_explicit_mode(self):
        seeded = self._seed_retrieval_records()
        try:
            response = compare_endpoint(
                CompareRequest(
                    question="Compare alpha and keywordbanana",
                    source_ids=[seeded["pdf_source_id"], seeded["docx_source_id"]],
                    mode="hybrid",
                    dry_run=True,
                )
            )
        finally:
            self._delete_retrieval_records(seeded.values())

        payload = response.model_dump()
        self.assertEqual(len(payload["sources"]), 2)
        self.assertEqual(payload["debug_info"]["resolved_modes"], ["hybrid", "hybrid"])
        self.assertEqual(payload["used_chunks_count"], 2)
        source_ids = {item["source_id"] for item in payload["sources"]}
        self.assertEqual(source_ids, {seeded["pdf_source_id"], seeded["docx_source_id"]})
        self.assertTrue(all(item["citations"] for item in payload["sources"]))

    def test_m18_compare_dry_run_reuses_router_conservatively_when_mode_omitted(self):
        seeded = self._seed_retrieval_records()
        original_use_router = settings.USE_QUERY_ROUTER
        try:
            settings.USE_QUERY_ROUTER = True
            response = compare_endpoint(
                CompareRequest(
                    question='"keywordbanana"',
                    source_ids=[seeded["pdf_source_id"], seeded["docx_source_id"]],
                    dry_run=True,
                )
            )
        finally:
            settings.USE_QUERY_ROUTER = original_use_router
            self._delete_retrieval_records(seeded.values())

        payload = response.model_dump()
        self.assertEqual(payload["debug_info"]["resolved_modes"], ["keyword", "keyword"])
        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["source_id"], seeded["docx_source_id"])

    def test_m18_compare_preserves_citation_discipline_with_grouped_sources(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.answering as answering_module

        original_generate_answer = answering_module.generate_answer
        answering_module.generate_answer = lambda system_prompt, user_prompt: {
            "success": True,
            "content": '{"answer":"PDF says alpha [S1]. DOCX says keywordbanana [S2]. Fake [S9]","citations":["S1","S2","S9"]}',
        }
        try:
            response = compare_endpoint(
                CompareRequest(
                    question="Compare alpha and keywordbanana",
                    source_ids=[seeded["pdf_source_id"], seeded["docx_source_id"]],
                    mode="hybrid",
                    dry_run=False,
                )
            )
        finally:
            answering_module.generate_answer = original_generate_answer
            self._delete_retrieval_records(seeded.values())

        self.assertNotIn("[S9]", response.answer)
        self.assertEqual(len(response.citations), 2)
        self.assertEqual(len(response.sources), 2)
        grouped_ids = {bucket.source_id for bucket in response.sources}
        self.assertEqual(grouped_ids, {seeded["pdf_source_id"], seeded["docx_source_id"]})

    def test_m18_compare_uses_second_pass_for_fragmented_initial_answer(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.answering as answering_module

        original_generate_answer = answering_module.generate_answer
        calls = []

        def fake_generate_answer(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                return {
                    "success": True,
                    "content": json.dumps(
                        {
                            "answer": "pdf alpha [S1] docx keywordbanana [S2]",
                            "citations": ["S1", "S2"],
                        }
                    ),
                }
            return {
                "success": True,
                "content": json.dumps(
                    {
                        "answer": "The PDF source supports alpha while the DOCX source supports keywordbanana, so the evidence comes from two different documents [S1] [S2].",
                        "citations": ["S1", "S2"],
                    }
                ),
            }

        answering_module.generate_answer = fake_generate_answer
        try:
            response = compare_endpoint(
                CompareRequest(
                    question="Compare alpha and keywordbanana",
                    source_ids=[seeded["pdf_source_id"], seeded["docx_source_id"]],
                    mode="hybrid",
                    dry_run=False,
                )
            )
        finally:
            answering_module.generate_answer = original_generate_answer
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(len(calls), 2)
        self.assertIn("two different documents", response.answer.lower())
        self.assertEqual(response.debug_info["answer_generation_path"], "repair")
        self.assertEqual(len(response.citations), 2)

    def test_m18_baseline_ask_remains_unchanged_when_compare_not_requested(self):
        seeded = self._seed_retrieval_records()
        try:
            response = ask_endpoint(AskRequest(question='"keywordbanana"', mode="keyword", dry_run=True))
        finally:
            self._delete_retrieval_records(seeded.values())

        payload = response.model_dump()
        self.assertEqual(payload["debug_info"]["mode"], "keyword")
        self.assertNotIn("resolved_modes", payload["debug_info"])

    def test_m19_eval_fixtures_load_and_cover_required_modes(self):
        retrieval_cases = load_eval_cases(EVAL_FIXTURE_DIR / "retrieval_cases.json")
        answer_cases = load_answer_cases(EVAL_FIXTURE_DIR / "answer_cases.json")
        compare_cases = load_compare_cases(EVAL_FIXTURE_DIR / "compare_cases.json")

        self.assertEqual({case["request"]["mode"] for case in retrieval_cases if case["request"].get("mode")}, {"vector", "keyword", "hybrid", "graph_hybrid", "full"})
        self.assertTrue(any(case.get("surface") == "deep_lookup" for case in retrieval_cases))
        self.assertTrue(answer_cases)
        self.assertTrue(compare_cases)

    def test_m19_retrieval_eval_runs_repeatably_across_modes(self):
        retrieval_seeded = self._seed_retrieval_records()
        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            temporal_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'complete',
                        CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m19-temporal-{suffix}.pdf",
                    "storage_path": f"tests/m19-temporal-{suffix}.pdf",
                    "hash_sha256": (suffix + "t") * 4,
                    "source_metadata_json": json.dumps(
                        {
                            "temporal": {
                                "artifact_version": "m13-rule-based-temporal-v1",
                                "built_from_source_hash": (suffix + "t") * 4,
                                "date_bounds": {"earliest": "2024-01-15", "latest": "2024-12-31"},
                            }
                        }
                    ),
                },
            ).scalar_one()
            graph_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'complete',
                        CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m19-graph-{suffix}.pdf",
                    "storage_path": f"tests/m19-graph-{suffix}.pdf",
                    "hash_sha256": (suffix + "g") * 4,
                    "source_metadata_json": json.dumps(
                        {
                            "graph": {
                                "artifact_version": "m14-graph-artifact-v1",
                                "build_status": "built",
                                "built_from_source_hash": (suffix + "g") * 4,
                                "stats": {"node_count": 2, "edge_count": 1},
                                "snapshot": {
                                    "nodes": [
                                        {
                                            "node_id": "organization:International Business Machines",
                                            "canonical_name": "International Business Machines",
                                            "entity_type": "organization",
                                            "ontology_tags": ["organization"],
                                            "aliases": ["IBM", "International Business Machines"],
                                            "mention_count": 1,
                                            "chunk_refs": [],
                                        },
                                        {
                                            "node_id": "organization:Acme Corp",
                                            "canonical_name": "Acme Corp",
                                            "entity_type": "organization",
                                            "ontology_tags": ["organization"],
                                            "aliases": ["Acme Corp"],
                                            "mention_count": 1,
                                            "chunk_refs": [],
                                        },
                                    ],
                                    "edges": [
                                        {
                                            "edge_id": "International Business Machines|works_with|Acme Corp",
                                            "subject": "International Business Machines",
                                            "relation_type": "works_with",
                                            "object": "Acme Corp",
                                            "chunk_refs": [],
                                            "evidence_count": 1,
                                        }
                                    ],
                                },
                            }
                        }
                    ),
                },
            ).scalar_one()

        insert_chunks(
            temporal_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Policy Window",
                    "section_path": "page:1",
                    "chunk_text": "Effective January 15, 2024. Valid until December 31, 2024.",
                    "token_count": 9,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m19"},
                    "temporal_json": {
                        "expressions": ["January 15, 2024", "December 31, 2024"],
                        "effective_window": {"start": "2024-01-15", "end": "2024-12-31"},
                    },
                }
            ],
        )
        insert_chunks(
            graph_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Graph Chunk 1",
                    "section_path": "page:1",
                    "chunk_text": "International Business Machines works with Acme Corp.",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m19"},
                    "entities_json": [
                        {"canonical_name": "International Business Machines", "entity_type": "organization", "ontology_tags": ["organization"], "aliases": ["IBM", "International Business Machines"]},
                        {"canonical_name": "Acme Corp", "entity_type": "organization", "ontology_tags": ["organization"], "aliases": ["Acme Corp"]},
                    ],
                    "relations_json": [
                        {"relation_type": "works_with", "subject": "International Business Machines", "object": "Acme Corp"}
                    ],
                }
            ],
        )
        graph_chunk_id = self._chunk_id_for_source(graph_source_id)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sources
                    SET source_metadata_json = CAST(:source_metadata_json AS jsonb)
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": graph_source_id,
                    "source_metadata_json": json.dumps(
                        {
                            "graph": {
                                "artifact_version": "m14-graph-artifact-v1",
                                "build_status": "built",
                                "built_from_source_hash": (suffix + "g") * 4,
                                "stats": {"node_count": 2, "edge_count": 1},
                                "snapshot": {
                                    "nodes": [
                                        {
                                            "node_id": "organization:International Business Machines",
                                            "canonical_name": "International Business Machines",
                                            "entity_type": "organization",
                                            "ontology_tags": ["organization"],
                                            "aliases": ["IBM", "International Business Machines"],
                                            "mention_count": 1,
                                            "chunk_refs": [{"chunk_id": graph_chunk_id}],
                                        },
                                        {
                                            "node_id": "organization:Acme Corp",
                                            "canonical_name": "Acme Corp",
                                            "entity_type": "organization",
                                            "ontology_tags": ["organization"],
                                            "aliases": ["Acme Corp"],
                                            "mention_count": 1,
                                            "chunk_refs": [{"chunk_id": graph_chunk_id}],
                                        },
                                    ],
                                    "edges": [
                                        {
                                            "edge_id": "International Business Machines|works_with|Acme Corp",
                                            "subject": "International Business Machines",
                                            "relation_type": "works_with",
                                            "object": "Acme Corp",
                                            "chunk_refs": [{"chunk_id": graph_chunk_id}],
                                            "evidence_count": 1,
                                        }
                                    ],
                                },
                            }
                        }
                    ),
                },
            )

        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        original_enable_graph = settings.ENABLE_GRAPH
        original_build_graph = settings.BUILD_GRAPH_ON_INGEST
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        settings.ENABLE_GRAPH = True
        settings.BUILD_GRAPH_ON_INGEST = True
        settings.ENABLE_TEMPORAL = True
        settings.EXTRACT_TEMPORAL_METADATA = True
        try:
            cases = load_eval_cases(EVAL_FIXTURE_DIR / "retrieval_cases.json")
            for case in cases:
                binding = case.get("binding")
                if binding == "graph_source_id":
                    case["request"]["filters"]["source_id"] = graph_source_id
                elif binding == "temporal_source_id":
                    case["request"]["filters"]["source_id"] = temporal_source_id
                elif binding == "deep_lookup_docx_source_ids":
                    case["request"]["source_ids"] = [retrieval_seeded["docx_source_id"]]
                elif binding == "deep_lookup_pair_source_ids":
                    case["request"]["source_ids"] = [retrieval_seeded["pdf_source_id"], retrieval_seeded["docx_source_id"]]

            with TemporaryDirectory() as tmpdir:
                report = run_retrieval_eval(
                    cases=cases,
                    report_path=Path(tmpdir) / "retrieval_eval.json",
                    debug=False,
                )
                report_path_exists = Path(report["report_path"]).exists()
        finally:
            retrieval_module.embed_texts = original_embed_texts
            settings.ENABLE_GRAPH = original_enable_graph
            settings.BUILD_GRAPH_ON_INGEST = original_build_graph
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_retrieval_records(retrieval_seeded.values())
            self._delete_seed_source(graph_source_id)
            self._delete_seed_source(temporal_source_id)

        self.assertEqual(report["summary"]["kind"], "retrieval")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(set(report["summary"]["evaluated_modes"]), {"vector", "keyword", "hybrid", "graph_hybrid", "full", "deep_lookup"})
        self.assertIn("report_metadata", report)
        self.assertIn("active_profiles", report["report_metadata"])
        self.assertIn("retrieval_settings", report["report_metadata"])
        self.assertTrue(all("trace" in item for item in report["results"]))
        self.assertTrue(report_path_exists)

    def test_m26_deep_lookup_bypasses_router_and_stays_source_scoped(self):
        from app.api.deep_lookup import deep_lookup_endpoint
        from app.core_rag.retrieval import DeepLookupRequest
        import app.core_rag.retrieval as retrieval_module

        seeded = self._seed_retrieval_records()
        original_route_query = retrieval_module.route_query
        retrieval_module.route_query = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("router should not run"))
        try:
            response = deep_lookup_endpoint(
                DeepLookupRequest(
                    question='"keywordbanana"',
                    source_ids=[seeded["docx_source_id"]],
                    k=5,
                )
            )
        finally:
            retrieval_module.route_query = original_route_query
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "deep_lookup")
        self.assertTrue(response.results)
        self.assertTrue(all(item.source_id == seeded["docx_source_id"] for item in response.results))

    def test_m26_ask_fallback_remains_unchanged(self):
        import app.api.ask as ask_api_module
        import app.core_rag.answering as answering_module

        original_verify_llm_ready = ask_api_module.verify_llm_ready
        original_perform_search = answering_module.perform_search
        ask_api_module.verify_llm_ready = lambda: True
        answering_module.perform_search = lambda request: SearchResponse(results=[], latency_ms=1, mode="hybrid")
        try:
            response = ask_endpoint(
                AskRequest(
                    question="missing evidence",
                    mode="hybrid",
                    k_chunks=4,
                    dry_run=False,
                )
            )
        finally:
            ask_api_module.verify_llm_ready = original_verify_llm_ready
            answering_module.perform_search = original_perform_search

        self.assertEqual(response.answer, "Not found in provided sources.")

    def test_m26_compare_remains_explicit_and_separate(self):
        response = compare_endpoint(CompareRequest(question="Compare these", source_ids=[1], dry_run=True))
        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertEqual(response.debug_info["error"], "compare_requires_at_least_two_source_ids")

    def test_m19_enriched_eval_emits_structured_json_for_ask_compare_and_fallback(self):
        seeded = self._seed_retrieval_records()
        try:
            answer_cases = load_answer_cases(EVAL_FIXTURE_DIR / "answer_cases.json")
            compare_cases = load_compare_cases(EVAL_FIXTURE_DIR / "compare_cases.json")
            for case in compare_cases:
                if case.get("binding") == "compare_source_ids":
                    case["request"]["source_ids"] = [seeded["pdf_source_id"], seeded["docx_source_id"]]
                    expected = case.get("expected", {})
                    if case["id"] == "compare_citation_grounding":
                        expected["grouped_source_ids"] = [seeded["pdf_source_id"], seeded["docx_source_id"]]
                    if case["id"] == "compare_explicit_hybrid_dry_run":
                        expected["grouped_source_ids"] = [seeded["pdf_source_id"], seeded["docx_source_id"]]

            with TemporaryDirectory() as tmpdir:
                report = run_enriched_eval(
                    answer_cases=answer_cases,
                    compare_cases=compare_cases,
                    report_path=Path(tmpdir) / "enriched_eval.json",
                )
                report_path_exists = Path(report["report_path"]).exists()

                single_answer = evaluate_answer_case(answer_cases[1])
                single_compare = evaluate_compare_case(compare_cases[2])
        finally:
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(report["summary"]["kind"], "enriched")
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertTrue(report_path_exists)
        self.assertEqual(single_answer["status"], "PASS")
        self.assertEqual(single_compare["status"], "PASS")
        self.assertIn("results", report)
        self.assertIn("failures", report)

    def test_m20_load_benchmark_cases_reads_fixture(self):
        from app.eval.compare_eval import load_benchmark_cases

        cases = load_benchmark_cases()
        self.assertTrue(cases)
        categories = {case["category"] for case in cases}
        self.assertIn("simple_lookup", categories)
        self.assertIn("relationship_heavy", categories)
        self.assertIn("temporal_query", categories)
        self.assertIn("source_scoped_deep_lookup", categories)

    def test_m20_mode_benchmark_runs_same_query_across_all_modes(self):
        from app.eval.compare_eval import run_mode_benchmark

        suffix = uuid4().hex[:8]
        source_hash = (suffix + "b") * 4
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m20-benchmark-{suffix}.pdf",
                    "storage_path": f"tests/m20-benchmark-{suffix}.pdf",
                    "hash_sha256": source_hash,
                    "source_metadata_json": json.dumps(
                        {
                            "graph": {
                                "artifact_version": "m14-graph-artifact-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
                                "storage_backend": "source_metadata_json",
                                "stats": {"node_count": 2, "edge_count": 1},
                                "snapshot": {
                                    "nodes": [
                                        {
                                            "node_id": "node::International Business Machines",
                                            "canonical_name": "International Business Machines",
                                            "aliases": ["IBM", "International Business Machines"],
                                            "chunk_refs": [{"chunk_id": None}],
                                        }
                                    ],
                                    "edges": [
                                        {
                                            "edge_id": "edge::Jane Doe::reports_to::International Business Machines",
                                            "subject": "Jane Doe",
                                            "relation_type": "reports_to",
                                            "object": "International Business Machines",
                                            "chunk_refs": [],
                                        }
                                    ],
                                },
                            },
                            "temporal": {
                                "artifact_version": "m13-rule-based-temporal-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
                                "date_bounds": {"earliest": "2024-01-15", "latest": "2024-12-31"},
                                "effective_window": {"start": "2024-01-15", "end": "2024-12-31"},
                                "document_version_refs": [{"value": "2.1"}],
                                "fallback_reason": None,
                            },
                        }
                    ),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Benchmark Match Chunk",
                    "section_path": "page:1",
                    "chunk_text": "keywordbanana Jane Doe reports to IBM under Version 2.1 during 2024 policy coverage.",
                    "token_count": 12,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m20-benchmark"},
                }
            ],
        )
        chunk_id = self._chunk_id_for_source(source_id)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE sources
                    SET source_metadata_json = jsonb_set(
                        source_metadata_json,
                        '{graph,snapshot,nodes,0,chunk_refs}',
                        CAST(:node_refs AS jsonb),
                        true
                    )
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": source_id,
                    "node_refs": json.dumps([{"chunk_id": chunk_id, "chunk_index": 0, "locator": {"page": 1}}]),
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE sources
                    SET source_metadata_json = jsonb_set(
                        source_metadata_json,
                        '{graph,snapshot,edges,0,chunk_refs}',
                        CAST(:edge_refs AS jsonb),
                        true
                    )
                    WHERE id = :source_id
                    """
                ),
                {
                    "source_id": source_id,
                    "edge_refs": json.dumps([{"chunk_id": chunk_id, "chunk_index": 0, "locator": {"page": 1}}]),
                },
            )
        update_chunk_embeddings([(chunk_id, basis_vector(1.0))])

        import app.core_rag.retrieval as retrieval_module

        original_enable_graph = settings.ENABLE_GRAPH
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_embed_texts = retrieval_module.embed_texts
        tmp_report = self._track_temp_cleanup_path(EVAL_FIXTURE_DIR / "benchmarks" / "tmp_smoke_benchmark_report.json")
        benchmark_case = {
            "id": "m20_smoke_case",
            "category": "relationship_heavy",
            "question": "Who reports to IBM in 2024 under Version 2.1?",
            "request": {
                "k": 5,
                "k_chunks": 3,
                "filters": {"source_id": "benchmark_source_id", "source_type": "pdf"},
            },
            "expected": {
                "retrieval": {
                    "headings_any": ["Benchmark Match Chunk"],
                    "snippet_keywords_any": ["keywordbanana", "jane doe", "ibm"],
                    "source_types_any": ["pdf"],
                },
                "citations": {
                    "min_citations": 1,
                    "source_ids": ["benchmark_source_id"],
                },
                "answer": {
                    "contains_any": ["IBM", "2024"],
                    "not_found_allowed": False,
                },
            },
            "mock_llm_content": "{\"answer\":\"IBM and 2024 are both supported in the benchmark chunk [S1]\",\"citations\":[\"S1\"]}",
            "settings_overrides": {"ENABLE_GRAPH": True, "ENABLE_TEMPORAL": True},
        }
        try:
            retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
            settings.ENABLE_GRAPH = True
            settings.ENABLE_TEMPORAL = True
            report = run_mode_benchmark(
                cases=[benchmark_case],
                bindings={"benchmark_source_id": source_id},
                report_path=tmp_report,
            )
        finally:
            settings.ENABLE_GRAPH = original_enable_graph
            settings.ENABLE_TEMPORAL = original_enable_temporal
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(source_id)

        self.assertEqual(report["summary"]["kind"], "mode_benchmark")
        self.assertEqual(report["summary"]["total"], 1)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertIn("report_metadata", report)
        self.assertIn("active_profiles", report["report_metadata"])
        self.assertIn("retrieval_settings", report["report_metadata"])
        mode_names = [item["mode"] for item in report["results"][0]["modes"]]
        self.assertEqual(mode_names, ["vector", "keyword", "hybrid", "graph_hybrid", "full", "deep_lookup"])
        for item in report["results"][0]["modes"]:
            self.assertIn("retrieval_relevance", item)
            self.assertIn("citation_quality", item)
            self.assertIn("answer_clarity", item)
            self.assertIn("latency_ms", item)
            self.assertIn("failure_mode", item)
            self.assertIn("trace", item)
            self.assertIn("latency_ms", item["trace"])
            self.assertIn("candidate_counts", item["trace"])

    def test_m8_mode_benchmark_reports_rerank_ab_latency_deltas(self):
        import app.eval.compare_eval as compare_eval_module

        original_perform_search = compare_eval_module.perform_search
        original_ask_endpoint = compare_eval_module.ask_endpoint
        try:
            compare_eval_module.perform_search = lambda request: SearchResponse(
                results=[
                    SearchResultItem(
                        chunk_id=1,
                        source_id=10,
                        source_part_id=None,
                        file_name="ops.pdf",
                        source_type="pdf",
                        heading="Ops Benchmark",
                        locator="page=1",
                        snippet="rerank benchmark chunk",
                        score=0.9,
                    )
                ],
                latency_ms=12,
                mode=request.mode or "hybrid",
                debug_info={
                    "request_id": "search-rerank",
                    "retrieval_path_used": request.mode or "hybrid",
                    "candidate_counts": {"pre_rerank": 3, "post_rerank": 1},
                    "latency_ms": {
                        "search": 12,
                        "rerank": 14 if compare_eval_module.get_effective_reranker().enabled else 0,
                        "total": 26 if compare_eval_module.get_effective_reranker().enabled else 12,
                    },
                    "rerank_policy": {
                        "enabled": compare_eval_module.get_effective_reranker().enabled,
                        "eligible": True,
                        "applied": compare_eval_module.get_effective_reranker().enabled,
                        "reason": "eligible_policy_match" if compare_eval_module.get_effective_reranker().enabled else "reranker_disabled",
                    },
                },
            )
            compare_eval_module.ask_endpoint = lambda request: AskResponse(
                answer="Supported answer [S1]",
                citations=[
                    CitationItem(
                        citation_id="S1",
                        source_id=10,
                        source_part_id=None,
                        chunk_id=1,
                        file_name="ops.pdf",
                        source_type="pdf",
                        heading="Ops Benchmark",
                        locator="page=1",
                        snippet="rerank benchmark chunk",
                    )
                ],
                used_chunks_count=1,
                latency_ms=8,
                mode=request.mode or "hybrid",
                debug_info={
                    "answer_generation_path": "grounded_answer",
                    "retrieval_trace": {
                        "request_id": "ask-rerank",
                        "retrieval_path_used": request.mode or "hybrid",
                        "candidate_counts": {"pre_rerank": 3, "post_rerank": 1},
                        "latency_ms": {
                            "search": 12,
                            "rerank": 14 if compare_eval_module.get_effective_reranker().enabled else 0,
                            "total": 26 if compare_eval_module.get_effective_reranker().enabled else 12,
                        },
                        "rerank_policy": {
                            "enabled": compare_eval_module.get_effective_reranker().enabled,
                            "eligible": True,
                            "applied": compare_eval_module.get_effective_reranker().enabled,
                            "reason": "eligible_policy_match" if compare_eval_module.get_effective_reranker().enabled else "reranker_disabled",
                        },
                    },
                },
            )

            report = compare_eval_module.run_mode_benchmark(
                cases=[
                    {
                        "id": "m8_rerank_ab",
                        "category": "rerank_ab",
                        "question": "What is the rerank benchmark result?",
                        "request": {"question": "What is the rerank benchmark result?", "k": 3, "k_chunks": 2},
                        "modes": ["hybrid"],
                        "rerank_variants": [
                            {"label": "rerank_off", "overrides": {"enabled": False}},
                            {"label": "rerank_on", "overrides": {"enabled": True, "enabled_modes": ["hybrid"], "min_candidate_count": 1}},
                        ],
                        "expected": {
                            "retrieval": {"headings_any": ["Ops Benchmark"], "source_types_any": ["pdf"]},
                            "citations": {"min_citations": 1, "source_ids": [10]},
                            "answer": {"contains_any": ["Supported"], "not_found_allowed": False},
                        },
                    }
                ]
            )
        finally:
            compare_eval_module.perform_search = original_perform_search
            compare_eval_module.ask_endpoint = original_ask_endpoint

        self.assertEqual(report["summary"]["evaluated_rerank_variants"], ["rerank_off", "rerank_on"])
        self.assertIn("rerank_latency_report", report["summary"])
        self.assertEqual(len(report["summary"]["rerank_latency_report"]["variants"]), 2)
        self.assertEqual(report["summary"]["rerank_latency_report"]["deltas"][0]["target_variant"], "rerank_on")
        self.assertEqual(report["summary"]["rerank_latency_report"]["deltas"][0]["delta_avg_rerank_latency_ms"], 14.0)
