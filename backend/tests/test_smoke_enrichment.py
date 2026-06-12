from tests.smoke_test_base import *


class SmokeTestEnrichment(SmokeTestBase):
    def test_m11_skeleton_modules_import_cleanly(self):
        self.assertEqual(get_graph_store().status().backend, "noop")
        self.assertFalse(ensure_graph_artifacts(source_id=1).available)
        self.assertEqual(normalize_ontology_tags(candidate_tags=["Person"]).tags, [])
        self.assertEqual(analyze_temporal_metadata(text="March 2026").metadata, {})
        self.assertEqual(retrieve_graph_candidates(question="Who reports to whom?").candidates, [])
        self.assertFalse(run_enrichment_extractors(chunk_text="alpha", source_id=1).ontology_tags)
        self.assertEqual(explain_graph_result(result_count=0).details["result_count"], 0)
        self.assertIn("graph", get_enrichment_artifact_versions())

    def test_m12_rule_based_extractor_normalizes_aliases_and_relations(self):
        original_extract_entities = settings.EXTRACT_ENTITIES
        original_extract_relations = settings.EXTRACT_RELATIONS
        original_enable_ontology = settings.ENABLE_ONTOLOGY
        settings.EXTRACT_ENTITIES = True
        settings.EXTRACT_RELATIONS = True
        settings.ENABLE_ONTOLOGY = True
        try:
            artifacts = run_enrichment_extractors(
                chunk_text="International Business Machines (IBM) works with Acme Corp. Jane Doe reports to IBM.",
                source_id=1,
            )
        finally:
            settings.EXTRACT_ENTITIES = original_extract_entities
            settings.EXTRACT_RELATIONS = original_extract_relations
            settings.ENABLE_ONTOLOGY = original_enable_ontology

        canonical_names = {entity["canonical_name"] for entity in artifacts.entities}
        self.assertIn("International Business Machines", canonical_names)
        self.assertIn("Acme Corp", canonical_names)
        self.assertIn("Jane Doe", canonical_names)
        relation_pairs = {(item["relation_type"], item["subject"], item["object"]) for item in artifacts.relations}
        self.assertIn(("works_with", "International Business Machines", "Acme Corp"), relation_pairs)
        self.assertIn(("reports_to", "Jane Doe", "International Business Machines"), relation_pairs)
        ibm_entity = next(entity for entity in artifacts.entities if entity["surface_text"] == "IBM")
        self.assertIn("IBM", ibm_entity["aliases"])
        self.assertEqual(artifacts.temporal_metadata, {})

    def test_m13_temporal_analyzer_extracts_dates_ranges_and_versions(self):
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        settings.ENABLE_TEMPORAL = True
        settings.EXTRACT_TEMPORAL_METADATA = True
        try:
            result = analyze_temporal_metadata(
                text=(
                    "Effective January 15, 2024. Valid until December 31, 2024. "
                    "This Version 2.1 document remains in force from 2024-01-15 to 2024-12-31."
                )
            )
        finally:
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal

        self.assertTrue(result.enabled)
        self.assertEqual(result.reason, "m13_rule_based_temporal_complete")
        self.assertEqual(result.metadata["effective_window"]["start"], "2024-01-15")
        self.assertEqual(result.metadata["effective_window"]["end"], "2024-12-31")
        self.assertTrue(result.metadata["document_version_refs"])
        self.assertIn("2024-01-15", result.metadata["normalized_dates"])

    def test_graph_hybrid_mode_falls_back_safely_to_hybrid(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            response = perform_search(SearchRequest(question="keywordbanana alpha", k=5, mode="graph_hybrid", debug=True))
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertGreaterEqual(len(response.results), 2)
        self.assertEqual(response.mode, "hybrid")

    def test_m16_graph_hybrid_uses_graph_artifacts_when_available_and_current(self):
        suffix = uuid4().hex[:8]
        source_hash = (suffix + "m") * 4
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
                    "file_name": f"m16-graph-{suffix}.pdf",
                    "storage_path": f"tests/m16-graph-{suffix}.pdf",
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
                    "heading": "Baseline Chunk",
                    "section_path": "page:1",
                    "chunk_text": "General policy overview with no relationship details.",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m16-graph"},
                },
                {
                    "chunk_index": 1,
                    "heading": "Graph Match Chunk",
                    "section_path": "page:2",
                    "chunk_text": "Leadership appendix.",
                    "token_count": 2,
                    "locator_json": {"page": 2},
                    "provenance_json": {"test": "m16-graph"},
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

        original_enable_graph = settings.ENABLE_GRAPH
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            settings.ENABLE_GRAPH = True
            response = perform_search(
                SearchRequest(
                    question="Who reports to IBM?",
                    k=5,
                    mode="graph_hybrid",
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
        finally:
            settings.ENABLE_GRAPH = original_enable_graph
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(source_id)

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "graph_hybrid")
        self.assertEqual(response.results[0].chunk_id, chunk_id_by_index[1])
        self.assertEqual(response.results[0].heading, "Graph Match Chunk")

    def test_full_mode_falls_back_safely_to_hybrid(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            response = perform_search(SearchRequest(question="keywordbanana alpha", k=5, mode="full", debug=True))
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertGreaterEqual(len(response.results), 2)
        self.assertEqual(response.mode, "hybrid")

    def test_m16_full_mode_uses_temporal_metadata_without_changing_result_shape(self):
        suffix = uuid4().hex[:8]
        source_hash = (suffix + "n") * 4
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
                    "file_name": f"m16-full-{suffix}.pdf",
                    "storage_path": f"tests/m16-full-{suffix}.pdf",
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
                    "heading": "Temporal Match Chunk",
                    "section_path": "page:1",
                    "chunk_text": "Policy summary.",
                    "token_count": 2,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m16-full"},
                }
            ],
        )
        update_chunk_embeddings([(self._chunk_id_for_source(source_id), basis_vector(1.0))])

        original_allow_lazy = settings.ALLOW_LAZY_ENRICHMENT
        original_enable_temporal = settings.ENABLE_TEMPORAL
        try:
            settings.ALLOW_LAZY_ENRICHMENT = True
            settings.ENABLE_TEMPORAL = True
            response = perform_search(
                SearchRequest(
                    question="What applied in 2024 under version 2.1?",
                    k=5,
                    mode="full",
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
        finally:
            settings.ALLOW_LAZY_ENRICHMENT = original_allow_lazy
            settings.ENABLE_TEMPORAL = original_enable_temporal
            self._delete_seed_source(source_id)

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "full")
        self.assertIsInstance(response.results[0], SearchResultItem)
        self.assertTrue(hasattr(response.results[0], "locator"))
        self.assertTrue(hasattr(response.results[0], "snippet"))

    def test_m15_full_mode_skips_lazy_enrichment_when_disabled(self):
        seeded = self._seed_retrieval_records()
        original_allow_lazy = settings.ALLOW_LAZY_ENRICHMENT
        try:
            settings.ALLOW_LAZY_ENRICHMENT = False
            response = perform_search(
                SearchRequest(
                    question="alpha",
                    k=5,
                    mode="full",
                    filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                    debug=True,
                )
            )
            with engine.connect() as conn:
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": seeded["pdf_source_id"]},
                ).scalar_one()
        finally:
            settings.ALLOW_LAZY_ENRICHMENT = original_allow_lazy
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "hybrid")
        self.assertEqual(job_count, 0)

    def test_m15_full_mode_triggers_lazy_enrichment_once_when_needed(self):
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
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m15-{suffix}.pdf",
                    "storage_path": f"tests/m15-{suffix}.pdf",
                    "hash_sha256": (suffix + "g") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Lazy Full Chunk",
                    "section_path": "page:1",
                    "chunk_text": "Effective January 15, 2024. Jane Doe reports to IBM. IBM works with Acme Corp.",
                    "token_count": 14,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m15"},
                }
            ],
        )
        update_chunk_embeddings([(self._chunk_id_for_source(source_id), basis_vector(1.0))])

        original_allow_lazy = settings.ALLOW_LAZY_ENRICHMENT
        original_enable_graph = settings.ENABLE_GRAPH
        original_build_graph = settings.BUILD_GRAPH_ON_INGEST
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        original_extract_entities = settings.EXTRACT_ENTITIES
        original_extract_relations = settings.EXTRACT_RELATIONS
        original_enable_ontology = settings.ENABLE_ONTOLOGY
        try:
            settings.ALLOW_LAZY_ENRICHMENT = True
            settings.ENABLE_GRAPH = True
            settings.BUILD_GRAPH_ON_INGEST = True
            settings.ENABLE_TEMPORAL = True
            settings.EXTRACT_TEMPORAL_METADATA = True
            settings.EXTRACT_ENTITIES = True
            settings.EXTRACT_RELATIONS = True
            settings.ENABLE_ONTOLOGY = True
            response = perform_search(
                SearchRequest(
                    question="IBM",
                    k=5,
                    mode="full",
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
            with engine.connect() as conn:
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": source_id},
                ).first()
                job_rows = conn.execute(
                    text(
                        """
                        SELECT enrichment_type, status
                        FROM enrichment_jobs
                        WHERE source_id = :source_id
                        ORDER BY id ASC
                        """
                    ),
                    {"source_id": source_id},
                ).fetchall()
        finally:
            settings.ALLOW_LAZY_ENRICHMENT = original_allow_lazy
            settings.ENABLE_GRAPH = original_enable_graph
            settings.BUILD_GRAPH_ON_INGEST = original_build_graph
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            settings.EXTRACT_ENTITIES = original_extract_entities
            settings.EXTRACT_RELATIONS = original_extract_relations
            settings.ENABLE_ONTOLOGY = original_enable_ontology
            self._delete_seed_source(source_id)

        source_metadata_json = source_row[0]
        self.assertEqual(response.mode, "full")
        self.assertTrue(job_rows)
        self.assertEqual(len(job_rows), 1)
        self.assertEqual(job_rows[0][0], "graph_artifact_build")
        self.assertEqual(job_rows[0][1], "completed")
        self.assertEqual(source_metadata_json["graph"]["built_from_source_hash"], (suffix + "g") * 4)
        self.assertEqual(source_metadata_json["temporal"]["built_from_source_hash"], (suffix + "g") * 4)
        self.assertTrue(source_metadata_json["lazy_enrichment"]["triggered"])

    def test_m15_full_mode_skips_rerun_when_artifacts_are_current(self):
        suffix = uuid4().hex[:8]
        source_hash = (suffix + "h") * 4
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
                    "file_name": f"m15-current-{suffix}.pdf",
                    "storage_path": f"tests/m15-current-{suffix}.pdf",
                    "hash_sha256": source_hash,
                    "source_metadata_json": json.dumps(
                        {
                            "graph": {
                                "artifact_version": "m14-graph-artifact-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
                            },
                            "temporal": {
                                "artifact_version": "m13-rule-based-temporal-v1",
                                "built_from_source_hash": source_hash,
                                "build_status": "built",
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
                    "heading": "Current Artifact Chunk",
                    "section_path": "page:1",
                    "chunk_text": "IBM current artifact chunk",
                    "token_count": 5,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m15-current"},
                }
            ],
        )
        update_chunk_embeddings([(self._chunk_id_for_source(source_id), basis_vector(1.0))])

        import app.ingestion.enrichment as enrichment_module

        original_allow_lazy = settings.ALLOW_LAZY_ENRICHMENT
        original_enable_graph = settings.ENABLE_GRAPH
        original_build_graph = settings.BUILD_GRAPH_ON_INGEST
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        original_run_post = enrichment_module.run_post_ingestion_enrichment
        enrichment_module.run_post_ingestion_enrichment = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("current artifacts should skip rerun in M15")
        )
        try:
            settings.ALLOW_LAZY_ENRICHMENT = True
            settings.ENABLE_GRAPH = True
            settings.BUILD_GRAPH_ON_INGEST = True
            settings.ENABLE_TEMPORAL = True
            settings.EXTRACT_TEMPORAL_METADATA = True
            response = perform_search(
                SearchRequest(
                    question="IBM",
                    k=5,
                    mode="full",
                    filters=SearchFilters(source_id=source_id, source_type="pdf"),
                    debug=True,
                )
            )
            with engine.connect() as conn:
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": source_id},
                ).first()
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": source_id},
                ).scalar_one()
        finally:
            enrichment_module.run_post_ingestion_enrichment = original_run_post
            settings.ALLOW_LAZY_ENRICHMENT = original_allow_lazy
            settings.ENABLE_GRAPH = original_enable_graph
            settings.BUILD_GRAPH_ON_INGEST = original_build_graph
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_seed_source(source_id)

        self.assertEqual(response.mode, "hybrid")
        self.assertEqual(job_count, 0)
        self.assertEqual(source_row[0]["lazy_enrichment"]["reason"], "artifacts_current")

    def test_m15_full_mode_falls_back_safely_when_lazy_trigger_fails(self):
        seeded = self._seed_retrieval_records()
        import app.ingestion.enrichment as enrichment_module

        original_allow_lazy = settings.ALLOW_LAZY_ENRICHMENT
        original_enable_graph = settings.ENABLE_GRAPH
        original_build_graph = settings.BUILD_GRAPH_ON_INGEST
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        original_run_post = enrichment_module.run_post_ingestion_enrichment
        enrichment_module.run_post_ingestion_enrichment = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            settings.ALLOW_LAZY_ENRICHMENT = True
            settings.ENABLE_GRAPH = True
            settings.BUILD_GRAPH_ON_INGEST = True
            settings.ENABLE_TEMPORAL = True
            settings.EXTRACT_TEMPORAL_METADATA = True
            response = perform_search(
                SearchRequest(
                    question="alpha",
                    k=5,
                    mode="full",
                    filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                    debug=True,
                )
            )
            with engine.connect() as conn:
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": seeded["pdf_source_id"]},
                ).first()
        finally:
            enrichment_module.run_post_ingestion_enrichment = original_run_post
            settings.ALLOW_LAZY_ENRICHMENT = original_allow_lazy
            settings.ENABLE_GRAPH = original_enable_graph
            settings.BUILD_GRAPH_ON_INGEST = original_build_graph
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "hybrid")
        self.assertEqual(source_row[0]["lazy_enrichment"]["reason"], "lazy_trigger_failed")

    def test_noop_enrichment_framework_does_not_write_jobs_by_default(self):
        source_id = self._seed_chunk_records()
        try:
            result = run_post_ingestion_enrichment(
                source_id=source_id,
                source_part_count=1,
                chunk_count=2,
                record_job=False,
            )
            with engine.connect() as conn:
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": source_id},
                ).scalar_one()
            self.assertFalse(result.attempted)
            self.assertFalse(result.wrote_job)
            self.assertEqual(result.reason, "enrichment_flags_disabled")
            self.assertEqual(job_count, 0)
        finally:
            self._delete_seed_source(source_id)

    def test_m12_enrichment_updates_chunks_without_temporal_or_graph_work(self):
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
                        :file_name, :storage_path, 'docx', :hash_sha256, 120,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m12-{suffix}.docx",
                    "storage_path": f"tests/m12-{suffix}.docx",
                    "hash_sha256": (suffix + "c") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Entity Chunk",
                    "section_path": "Section 1",
                    "chunk_text": "International Business Machines (IBM) works with Acme Corp. Jane Doe reports to IBM.",
                    "token_count": 12,
                    "locator_json": {"block": 1},
                    "provenance_json": {"test": "m12"},
                }
            ],
        )

        import app.ingestion.enrichment as enrichment_module

        original_extract_entities = settings.EXTRACT_ENTITIES
        original_extract_relations = settings.EXTRACT_RELATIONS
        original_enable_ontology = settings.ENABLE_ONTOLOGY
        original_ensure_graph_artifacts = enrichment_module.ensure_graph_artifacts
        settings.EXTRACT_ENTITIES = True
        settings.EXTRACT_RELATIONS = True
        settings.ENABLE_ONTOLOGY = True
        enrichment_module.ensure_graph_artifacts = lambda **kwargs: (_ for _ in ()).throw(AssertionError("graph index should remain unused in M12"))
        try:
            result = run_post_ingestion_enrichment(
                source_id=source_id,
                source_part_count=1,
                chunk_count=1,
                record_job=False,
            )
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT entities_json, relations_json, provenance_json, temporal_json
                        FROM chunks
                        WHERE source_id = :source_id
                        ORDER BY chunk_index ASC
                        LIMIT 1
                        """
                    ),
                    {"source_id": source_id},
                ).first()
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": source_id},
                ).scalar_one()
        finally:
            enrichment_module.ensure_graph_artifacts = original_ensure_graph_artifacts
            settings.EXTRACT_ENTITIES = original_extract_entities
            settings.EXTRACT_RELATIONS = original_extract_relations
            settings.ENABLE_ONTOLOGY = original_enable_ontology
            self._delete_seed_source(source_id)

        entities_json, relations_json, provenance_json, temporal_json = row
        self.assertTrue(result.attempted)
        self.assertFalse(result.wrote_job)
        self.assertEqual(result.reason, "m12_rule_based_complete")
        self.assertGreater(result.entities_extracted, 0)
        self.assertGreater(result.relations_extracted, 0)
        self.assertEqual(job_count, 0)
        self.assertTrue(entities_json)
        self.assertTrue(relations_json)
        self.assertEqual(temporal_json, {})
        self.assertIn("enrichment", provenance_json)
        self.assertEqual(provenance_json["enrichment"]["artifact_version"], "m12-rule-based-extractor-v1")
        canonical_names = {entity["canonical_name"] for entity in entities_json}
        self.assertIn("International Business Machines", canonical_names)
        self.assertIn("Acme Corp", canonical_names)

    def test_m13_temporal_enrichment_updates_chunks_and_source_summary(self):
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
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m13-{suffix}.pdf",
                    "storage_path": f"tests/m13-{suffix}.pdf",
                    "hash_sha256": (suffix + "d") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Policy Window",
                    "section_path": "page:1",
                    "chunk_text": "Effective January 15, 2024. Valid until December 31, 2024. Version 2.1 applies.",
                    "token_count": 11,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m13"},
                }
            ],
        )

        import app.ingestion.enrichment as enrichment_module

        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        original_ensure_graph_artifacts = enrichment_module.ensure_graph_artifacts
        settings.ENABLE_TEMPORAL = True
        settings.EXTRACT_TEMPORAL_METADATA = True
        enrichment_module.ensure_graph_artifacts = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("graph index should remain unused in M13")
        )
        try:
            result = run_post_ingestion_enrichment(
                source_id=source_id,
                source_part_count=1,
                chunk_count=1,
                record_job=False,
            )
            with engine.connect() as conn:
                chunk_row = conn.execute(
                    text(
                        """
                        SELECT temporal_json, provenance_json
                        FROM chunks
                        WHERE source_id = :source_id
                        ORDER BY chunk_index ASC
                        LIMIT 1
                        """
                    ),
                    {"source_id": source_id},
                ).first()
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": source_id},
                ).first()
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": source_id},
                ).scalar_one()
        finally:
            enrichment_module.ensure_graph_artifacts = original_ensure_graph_artifacts
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_seed_source(source_id)

        temporal_json, provenance_json = chunk_row
        source_metadata_json = source_row[0]
        self.assertTrue(result.attempted)
        self.assertFalse(result.wrote_job)
        self.assertEqual(result.reason, "m13_rule_based_temporal_complete")
        self.assertEqual(job_count, 0)
        self.assertTrue(temporal_json["expressions"])
        self.assertEqual(temporal_json["effective_window"]["start"], "2024-01-15")
        self.assertEqual(temporal_json["effective_window"]["end"], "2024-12-31")
        self.assertTrue(temporal_json["document_version_refs"])
        self.assertIn("temporal", provenance_json)
        self.assertEqual(provenance_json["temporal"]["artifact_version"], "m13-rule-based-temporal-v1")
        self.assertIn("temporal", source_metadata_json)
        self.assertEqual(source_metadata_json["temporal"]["date_bounds"]["earliest"], "2024-01-15")
        self.assertEqual(source_metadata_json["temporal"]["date_bounds"]["latest"], "2024-12-31")

    def test_m13_temporal_enrichment_records_conservative_fallback_when_no_dates_exist(self):
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
                        :file_name, :storage_path, 'docx', :hash_sha256, 120,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m13-fallback-{suffix}.docx",
                    "storage_path": f"tests/m13-fallback-{suffix}.docx",
                    "hash_sha256": (suffix + "e") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "No Dates",
                    "section_path": "Section 1",
                    "chunk_text": "Acme Corp reviewed the policy language and shared comments with IBM.",
                    "token_count": 11,
                    "locator_json": {"block": 1},
                    "provenance_json": {"test": "m13-fallback"},
                }
            ],
        )

        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        settings.ENABLE_TEMPORAL = True
        settings.EXTRACT_TEMPORAL_METADATA = True
        try:
            result = run_post_ingestion_enrichment(
                source_id=source_id,
                source_part_count=1,
                chunk_count=1,
                record_job=False,
            )
            with engine.connect() as conn:
                chunk_row = conn.execute(
                    text(
                        """
                        SELECT temporal_json, provenance_json
                        FROM chunks
                        WHERE source_id = :source_id
                        ORDER BY chunk_index ASC
                        LIMIT 1
                        """
                    ),
                    {"source_id": source_id},
                ).first()
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": source_id},
                ).first()
        finally:
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_seed_source(source_id)

        temporal_json, provenance_json = chunk_row
        source_metadata_json = source_row[0]
        self.assertTrue(result.attempted)
        self.assertEqual(result.reason, "m13_rule_based_temporal_complete")
        self.assertEqual(temporal_json["fallback_reason"], "no_reliable_temporal_metadata")
        self.assertEqual(temporal_json["expressions"], [])
        self.assertEqual(provenance_json["temporal"]["fallback_reason"], "no_reliable_temporal_metadata")
        self.assertEqual(source_metadata_json["temporal"]["fallback_reason"], "no_reliable_temporal_metadata")

    def test_m14_graph_artifact_builds_from_enriched_chunks_without_retrieval_changes(self):
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
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m14-{suffix}.pdf",
                    "storage_path": f"tests/m14-{suffix}.pdf",
                    "hash_sha256": (suffix + "f") * 4,
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Graph Chunk 1",
                    "section_path": "page:1",
                    "chunk_text": "International Business Machines works with Acme Corp.",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "entities_json": [
                        {
                            "surface_text": "International Business Machines",
                            "canonical_name": "International Business Machines",
                            "entity_type": "organization",
                            "ontology_tags": ["organization"],
                            "aliases": ["IBM", "International Business Machines"],
                        },
                        {
                            "surface_text": "Acme Corp",
                            "canonical_name": "Acme Corp",
                            "entity_type": "organization",
                            "ontology_tags": ["organization"],
                            "aliases": ["Acme Corp"],
                        },
                    ],
                    "relations_json": [
                        {
                            "relation_type": "works_with",
                            "subject": "International Business Machines",
                            "object": "Acme Corp",
                            "evidence_text": "International Business Machines works with Acme Corp",
                        }
                    ],
                    "provenance_json": {"test": "m14"},
                },
                {
                    "chunk_index": 1,
                    "heading": "Graph Chunk 2",
                    "section_path": "page:2",
                    "chunk_text": "Jane Doe reports to International Business Machines.",
                    "token_count": 8,
                    "locator_json": {"page": 2},
                    "entities_json": [
                        {
                            "surface_text": "Jane Doe",
                            "canonical_name": "Jane Doe",
                            "entity_type": "person",
                            "ontology_tags": ["person"],
                            "aliases": ["Jane Doe"],
                        },
                        {
                            "surface_text": "IBM",
                            "canonical_name": "International Business Machines",
                            "entity_type": "organization",
                            "ontology_tags": ["organization"],
                            "aliases": ["IBM", "International Business Machines"],
                        },
                    ],
                    "relations_json": [
                        {
                            "relation_type": "reports_to",
                            "subject": "Jane Doe",
                            "object": "International Business Machines",
                            "evidence_text": "Jane Doe reports to International Business Machines",
                        }
                    ],
                    "provenance_json": {"test": "m14"},
                },
            ],
        )

        original_enable_graph = settings.ENABLE_GRAPH
        original_build_graph = settings.BUILD_GRAPH_ON_INGEST
        original_extract_entities = settings.EXTRACT_ENTITIES
        original_extract_relations = settings.EXTRACT_RELATIONS
        original_enable_ontology = settings.ENABLE_ONTOLOGY
        original_enable_temporal = settings.ENABLE_TEMPORAL
        original_extract_temporal = settings.EXTRACT_TEMPORAL_METADATA
        settings.ENABLE_GRAPH = True
        settings.BUILD_GRAPH_ON_INGEST = True
        settings.EXTRACT_ENTITIES = False
        settings.EXTRACT_RELATIONS = False
        settings.ENABLE_ONTOLOGY = False
        settings.ENABLE_TEMPORAL = False
        settings.EXTRACT_TEMPORAL_METADATA = False
        try:
            result = run_post_ingestion_enrichment(
                source_id=source_id,
                source_part_count=1,
                chunk_count=2,
                record_job=False,
            )
            with engine.connect() as conn:
                source_row = conn.execute(
                    text("SELECT source_metadata_json FROM sources WHERE id = :source_id"),
                    {"source_id": source_id},
                ).first()
                job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": source_id},
                ).scalar_one()
        finally:
            settings.ENABLE_GRAPH = original_enable_graph
            settings.BUILD_GRAPH_ON_INGEST = original_build_graph
            settings.EXTRACT_ENTITIES = original_extract_entities
            settings.EXTRACT_RELATIONS = original_extract_relations
            settings.ENABLE_ONTOLOGY = original_enable_ontology
            settings.ENABLE_TEMPORAL = original_enable_temporal
            settings.EXTRACT_TEMPORAL_METADATA = original_extract_temporal
            self._delete_seed_source(source_id)

        source_metadata_json = source_row[0]
        graph_metadata = source_metadata_json["graph"]
        self.assertTrue(result.attempted)
        self.assertFalse(result.wrote_job)
        self.assertEqual(result.reason, "m14_graph_artifact_complete")
        self.assertEqual(job_count, 0)
        self.assertTrue(result.debug_summary["graph_index_invoked"])
        self.assertTrue(result.debug_summary["graph_store_invoked"])
        self.assertEqual(graph_metadata["artifact_version"], "m14-graph-artifact-v1")
        self.assertEqual(graph_metadata["storage_backend"], "source_metadata_json")
        self.assertEqual(graph_metadata["stats"]["node_count"], 3)
        self.assertEqual(graph_metadata["stats"]["edge_count"], 2)
        self.assertEqual(graph_metadata["stats"]["relation_type_counts"]["works_with"], 1)
        self.assertEqual(graph_metadata["stats"]["relation_type_counts"]["reports_to"], 1)
        self.assertEqual(len(graph_metadata["snapshot"]["nodes"]), 3)
        self.assertEqual(len(graph_metadata["snapshot"]["edges"]), 2)
        self.assertIn("provenance", graph_metadata)
        self.assertNotIn("evidence_text", graph_metadata["snapshot"]["edges"][0])
        self.assertIn("chunk_refs", graph_metadata["snapshot"]["edges"][0])

    def test_source_metadata_merge_preserves_nested_graph_temporal_and_lazy_sections(self):
        source_metadata = {
            "graph": {
                "artifact_version": "m14-graph-artifact-v1",
                "stats": {"node_count": 2, "edge_count": 1},
                "provenance": {"built_from_source_hash": "abc"},
            },
            "temporal": {
                "artifact_version": "m13-rule-based-temporal-v1",
                "date_bounds": {"earliest": "2024-01-15", "latest": "2024-12-31"},
            },
        }
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
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'complete', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"merge-{suffix}.pdf",
                    "storage_path": f"tests/merge-{suffix}.pdf",
                    "hash_sha256": suffix * 8,
                    "source_metadata_json": json.dumps(source_metadata),
                },
            ).scalar_one()
        try:
            from app.db.repo_sources import merge_source_metadata

            merge_source_metadata(
                source_id,
                {
                    "graph": {"stats": {"edge_count": 2}},
                    "lazy_enrichment": {"reason": "artifacts_current", "triggered": False},
                },
            )
            updated = get_source_by_id(source_id)
        finally:
            self._delete_seed_source(source_id)

        metadata = updated.source_metadata_json
        self.assertEqual(metadata["graph"]["artifact_version"], "m14-graph-artifact-v1")
        self.assertEqual(metadata["graph"]["stats"]["node_count"], 2)
        self.assertEqual(metadata["graph"]["stats"]["edge_count"], 2)
        self.assertEqual(metadata["temporal"]["artifact_version"], "m13-rule-based-temporal-v1")
        self.assertIn("lazy_enrichment", metadata)

    def test_source_metadata_merge_rejects_non_dict_patch(self):
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
                        :file_name, :storage_path, 'pdf', :hash_sha256, 120,
                        'embedded', 'complete', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"invalid-merge-{suffix}.pdf",
                    "storage_path": f"tests/invalid-merge-{suffix}.pdf",
                    "hash_sha256": suffix * 8,
                },
            ).scalar_one()
        try:
            from app.db.repo_sources import merge_source_metadata

            with self.assertRaises(TypeError):
                merge_source_metadata(source_id, ["bad", "patch"])
            updated = get_source_by_id(source_id)
        finally:
            self._delete_seed_source(source_id)

        self.assertEqual(updated.source_metadata_json, {})

    def test_source_metadata_merge_rejects_invalid_reserved_section_shape(self):
        suffix = uuid4().hex[:8]
        source_metadata = {
            "graph": {"artifact_version": "m14-graph-artifact-v1", "stats": {"node_count": 1}},
            "temporal": {"artifact_version": "m13-rule-based-temporal-v1"},
        }
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
                        'embedded', 'complete', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"invalid-section-{suffix}.pdf",
                    "storage_path": f"tests/invalid-section-{suffix}.pdf",
                    "hash_sha256": suffix * 8,
                    "source_metadata_json": json.dumps(source_metadata),
                },
            ).scalar_one()
        try:
            from app.db.repo_sources import merge_source_metadata

            with self.assertRaises(ValueError):
                merge_source_metadata(source_id, {"graph": "broken"})
            updated = get_source_by_id(source_id)
        finally:
            self._delete_seed_source(source_id)

        self.assertEqual(updated.source_metadata_json["graph"]["artifact_version"], "m14-graph-artifact-v1")
        self.assertEqual(updated.source_metadata_json["temporal"]["artifact_version"], "m13-rule-based-temporal-v1")
