from tests.smoke_test_base import *


class SmokeTestAdminOps(SmokeTestBase):
    def test_m2_retrieval_trace_persists_full_ask_lifecycle_and_admin_inspection(self):
        from fastapi.testclient import TestClient

        from app.core_rag.answering import perform_ask
        from app.db.migrate import run_migrations
        from app.db.repo_traces import get_trace

        run_migrations()
        seeded = self._seed_retrieval_records()
        client = TestClient(app)
        import app.core_rag.retrieval as retrieval_module
        import app.core_rag.answering as answering_module

        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        trace_request_id = None
        try:
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            answering_module.generate_answer = lambda system_prompt, user_prompt: {
                "success": True,
                "content": "{\"answer\":\"The answer confirms the alpha semantic vector match text in the retrieved source [S1]\",\"citations\":[\"S1\"]}",
            }
            response = perform_ask(
                AskRequest(
                    question="alpha semantic vector match text",
                    k_chunks=2,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer

        try:
            trace_request_id = response.debug_info["retrieval_trace"]["request_id"]
            stored = get_trace(trace_request_id)
            self.assertIsNotNone(stored)
            self.assertEqual(stored["request_id"], trace_request_id)
            self.assertEqual(stored["resolved_mode"], "hybrid")
            self.assertEqual(stored["retrieval_path"], "hybrid")
            self.assertEqual(stored["answer_path"], "llm")
            self.assertIn("pre_rerank", stored["candidate_counts"])
            self.assertIn("post_rerank", stored["candidate_counts"])
            self.assertIn("search", stored["latency_ms"])
            self.assertIn("ask", stored["latency_ms"])
            self.assertIn("total", stored["latency_ms"])
            self.assertIn("search_total", stored["latency_ms"])
            self.assertGreaterEqual(len(stored["score_diagnostics"]), 1)

            by_request = client.get(f"/admin/traces/by-request/{trace_request_id}")
            self.assertEqual(by_request.status_code, 200)
            by_request_json = by_request.json()
            self.assertEqual(by_request_json["trace"]["request_id"], trace_request_id)
            self.assertEqual(by_request_json["trace"]["answer_path"], "llm")
            self.assertIn("retrieval", by_request_json["active_profiles"])
            self.assertIn("hybrid_alpha", by_request_json["retrieval_settings"])

            listing = client.get("/admin/traces", params={"limit": 5})
            self.assertEqual(listing.status_code, 200)
            listing_json = listing.json()
            self.assertTrue(any(item["request_id"] == trace_request_id for item in listing_json["traces"]))
            self.assertIn("retrieval", listing_json["active_profiles"])
            self.assertIn("default_mode", listing_json["retrieval_settings"])
        finally:
            if trace_request_id:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM retrieval_traces WHERE request_id = :request_id"), {"request_id": trace_request_id})
            self._delete_retrieval_records(seeded.values())

    def test_m21_structured_logs_exist_for_upload_search_ask_enrich_and_build_graph(self):
        from app.ingestion.jobs import process_upload
        from app.core_rag.answering import perform_ask

        unique_name = f"m21-logs-{uuid4().hex[:8]}.pdf"
        upload = UploadFile(
            filename=unique_name,
            file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
            headers={"content-type": "application/pdf"},
        )

        with self.assertLogs("rag_mm_master_poc", level="INFO") as captured:
            result = asyncio.run(process_upload(upload))
            seeded = self._seed_retrieval_records()
            import app.core_rag.retrieval as retrieval_module

            original_embed_texts = retrieval_module.embed_texts
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            try:
                perform_search(
                    SearchRequest(
                        question="alpha semantic vector match text",
                        k=3,
                        mode="hybrid",
                        filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                    )
                )
                perform_ask(
                    AskRequest(
                        question="alpha semantic vector match text",
                        k_chunks=2,
                        mode="hybrid",
                        dry_run=True,
                        filters=SearchFilters(source_id=seeded["pdf_source_id"]),
                    )
                )
            finally:
                retrieval_module.embed_texts = original_embed_texts
                self._delete_retrieval_records(seeded.values())

        try:
            output = "\n".join(captured.output)
            self.assertIn('"event": "upload.accepted"', output)
            self.assertIn('"event": "parse.completed"', output)
            self.assertIn('"event": "chunk.completed"', output)
            self.assertIn('"event": "embed.completed"', output)
            self.assertIn('"event": "search.started"', output)
            self.assertIn('"event": "ask.started"', output)
            self.assertIn('"event": "enrich.skipped"', output)
            self.assertIn('"event": "build_graph.skipped"', output)
        finally:
            self._delete_seed_source(result["source_id"])

    def test_m21_admin_reindex_rebuilds_from_known_safe_point(self):
        from app.ingestion.jobs import admin_reindex_source

        unique_name = f"m21-reindex-{uuid4().hex[:8]}.pdf"
        upload = UploadFile(
            filename=unique_name,
            file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
            headers={"content-type": "application/pdf"},
        )
        result = asyncio.run(process_upload(upload))
        source_id = result["source_id"]
        try:
            with engine.begin() as conn:
                conn.execute(text("UPDATE sources SET ingestion_status = 'failed' WHERE id = :source_id"), {"source_id": source_id})

            first_chunk_count = self._source_chunk_count(source_id)
            first_part_count = self._source_part_count(source_id)
            rerun = admin_reindex_source(source_id=source_id)

            self.assertEqual(rerun["status"], "completed")
            self.assertGreater(rerun["job_id"], 0)
            self.assertEqual(self._source_chunk_count(source_id), first_chunk_count)
            self.assertEqual(self._source_part_count(source_id), first_part_count)
            source = get_source_by_id(source_id)
            self.assertEqual(source.ingestion_status, "embedded")
            self.assertNotIn("graph", source.source_metadata_json)
            self.assertNotIn("temporal", source.source_metadata_json)
        finally:
            self._delete_seed_source(source_id)

    def test_m21_admin_enrich_reruns_safely_for_existing_source(self):
        from app.ingestion.enrichment import admin_rerun_enrichment

        source_id = self._seed_chunk_records()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE sources
                        SET ingestion_status = 'embedded',
                            enrichment_status = 'failed',
                            source_metadata_json = CAST(:metadata AS jsonb)
                        WHERE id = :source_id
                        """
                    ),
                    {
                        "source_id": source_id,
                        "metadata": json.dumps(
                            {
                                "graph": {"build_status": "failed"},
                                "temporal": {"build_status": "failed"},
                                "lazy_enrichment": {"reason": "old-trace"},
                            }
                        ),
                    },
                )

            original_entities = settings.EXTRACT_ENTITIES
            original_relations = settings.EXTRACT_RELATIONS
            original_temporal = settings.EXTRACT_TEMPORAL_METADATA
            settings.EXTRACT_ENTITIES = True
            settings.EXTRACT_RELATIONS = True
            settings.EXTRACT_TEMPORAL_METADATA = True
            try:
                result = admin_rerun_enrichment(source_id=source_id)
            finally:
                settings.EXTRACT_ENTITIES = original_entities
                settings.EXTRACT_RELATIONS = original_relations
                settings.EXTRACT_TEMPORAL_METADATA = original_temporal

            source = get_source_by_id(source_id)
            self.assertTrue(result.attempted)
            self.assertEqual(source.enrichment_status, "completed")
            self.assertIn("temporal", source.source_metadata_json)
            self.assertNotEqual(source.source_metadata_json["temporal"].get("build_status"), "failed")
            self.assertEqual(source.source_metadata_json["lazy_enrichment"]["reason"], "old-trace")
        finally:
            self._delete_seed_source(source_id)

    def test_m21_cleanup_script_only_deletes_test_scoped_sources(self):
        from scripts.cleanup_test_data import cleanup_test_data

        suffix = uuid4().hex[:8]
        storage_prefix = f"tests/cleanup-{suffix}"
        with engine.begin() as conn:
            test_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 10,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"test-cleanup-{suffix}.pdf",
                    "storage_path": f"{storage_prefix}.pdf",
                    "hash_sha256": (suffix + "c") * 4,
                },
            ).scalar_one()
            keep_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', :hash_sha256, 10,
                        'embedded', 'not_started', '{}'::jsonb
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"keep-cleanup-{suffix}.pdf",
                    "storage_path": f"data/uploads/keep-cleanup-{suffix}.pdf",
                    "hash_sha256": (suffix + "k") * 4,
                },
            ).scalar_one()

        try:
            preview = cleanup_test_data(storage_prefix=storage_prefix, apply=False)
            self.assertEqual(preview["status"], "dry_run")
            self.assertEqual(preview["matched_count"], 1)

            applied = cleanup_test_data(storage_prefix=storage_prefix, apply=True)
            self.assertEqual(applied["deleted_count"], 1)
            self.assertIsNone(get_source_by_id(test_source_id))
            self.assertIsNotNone(get_source_by_id(keep_source_id))
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM sources WHERE id = :source_id"), {"source_id": keep_source_id})
