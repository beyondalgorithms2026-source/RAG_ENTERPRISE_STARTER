from tests.smoke_test_base import *


class SmokeTestBaseline(SmokeTestBase):
    def test_core_imports(self):
        self.assertIsNotNone(settings)
        self.assertEqual(logger.name, "rag_mm_master_poc")
        self.assertIsNotNone(engine)

    def test_retrieval_models(self):
        filters = SearchFilters(source_type="pdf", source_id=1, source_part_id=2, locator_filter="page 1")
        request = SearchRequest(
            question="What is this?",
            filters=filters,
            mode="hybrid",
            debug=True,
            deep_research=True,
            custom_query="custom retrieval query",
            anchor_terms=["alpha", "beta"],
            exact_phrase_bias="exact phrase",
            expand_neighbors=True,
            force_rare_keyword_scan=True,
        )
        self.assertEqual(request.filters.source_type, "pdf")
        self.assertTrue(request.deep_research)
        self.assertEqual(request.custom_query, "custom retrieval query")
        self.assertEqual(request.anchor_terms, ["alpha", "beta"])

        item = SearchResultItem(
            chunk_id=1,
            source_id=1,
            source_part_id=2,
            file_name="example.pdf",
            source_type="pdf",
            heading="Intro",
            locator="page=1",
            snippet="Snippet",
            score=0.9,
        )
        response = SearchResponse(results=[item], latency_ms=5, mode="hybrid", debug_info={"deep_research_used": True})
        self.assertEqual(response.results[0].file_name, "example.pdf")
        self.assertTrue(response.debug_info["deep_research_used"])

    def test_answering_models(self):
        request = AskRequest(
            question="Summarize this",
            dry_run=True,
            mode="hybrid",
            deep_research=True,
            custom_query="summary query",
            anchor_terms=["summary"],
            exact_phrase_bias="important phrase",
            expand_neighbors=True,
            force_rare_keyword_scan=True,
        )
        citation = CitationItem(
            citation_id="S1",
            source_id=42,
            source_part_id=7,
            chunk_id=1,
            file_name="example.pdf",
            source_type="pdf",
            heading="Intro",
            locator="page=1",
            snippet="Snippet",
        )
        response = AskResponse(answer="Answer [S1]", citations=[citation], used_chunks_count=1, latency_ms=1, mode="hybrid")
        self.assertTrue(request.dry_run)
        self.assertEqual(request.mode, "hybrid")
        self.assertTrue(request.deep_research)
        self.assertEqual(response.citations[0].source_type, "pdf")
        self.assertEqual(response.citations[0].source_part_id, 7)

        compare_request = CompareRequest(question="Compare these", source_ids=[1, 2], dry_run=True)
        compare_response = CompareResponse(answer="Compared", sources=[], citations=[], used_chunks_count=2, latency_ms=1)
        self.assertEqual(compare_request.source_ids, [1, 2])
        self.assertEqual(compare_response.used_chunks_count, 2)

    def test_prompt_builder(self):
        prompt = generate_user_prompt(
            "What is this?",
            [
                {
                    "citation_id": "S1",
                    "file_name": "example.pdf",
                    "source_type": "pdf",
                    "heading": "Intro",
                    "locator": "page=1",
                    "snippet": "Snippet text",
                }
            ],
        )
        self.assertIn("Source Type: pdf", prompt)
        self.assertIn("Locator: page=1", prompt)
        self.assertIn("QUESTION: What is this?", prompt)
        self.assertIn("Use only the listed [S#] citation ids", prompt)
        self.assertTrue(SYSTEM_PROMPT)
        self.assertTrue(REPAIR_PROMPT)

    def test_module_symbols_are_callable_without_runtime_execution(self):
        self.assertTrue(callable(search_chunks))
        self.assertTrue(callable(search_chunks_keyword))
        self.assertTrue(callable(get_model))
        self.assertTrue(callable(get_expected_dim))
        self.assertTrue(callable(embed_texts))
        self.assertTrue(callable(process_embeddings))
        self.assertTrue(callable(is_llm_ready))
        self.assertTrue(callable(verify_llm_ready))
        self.assertTrue(callable(generate_answer))
        self.assertTrue(callable(parse_demo_questions))
        self.assertTrue(callable(evaluate_question))
        self.assertTrue(callable(parse_uploaded_source_file))
        self.assertTrue(callable(chunk_uploaded_source_file))
        self.assertTrue(callable(run_post_ingestion_enrichment))
        self.assertTrue(callable(retrieve_graph_candidates))
        self.assertTrue(callable(route_query))

    def test_chunk_pdf_fixture(self):
        parsed = parse_source_bytes("pdf", (FIXTURE_DIR / "sample.pdf").read_bytes(), "sample.pdf")
        chunks = chunk_parsed_document(parsed)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["locator_json"]["page"], 1)
        self.assertEqual(chunks[1]["locator_json"]["page"], 2)
        self.assertIn("Page One Text", chunks[0]["chunk_text"])
        self.assertIn("page:1", chunks[0]["section_path"])

    def test_chunk_docx_fixture(self):
        parsed = parse_source_bytes("docx", (FIXTURE_DIR / "sample.docx").read_bytes(), "sample.docx")
        chunks = chunk_parsed_document(parsed)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk["locator_json"] for chunk in chunks))
        self.assertTrue(any("Project Phoenix" in chunk["chunk_text"] for chunk in chunks))
        self.assertTrue(any("Table 1" in chunk["section_path"] for chunk in chunks))

    def test_chunk_pptx_fixture(self):
        parsed = parse_source_bytes("pptx", (FIXTURE_DIR / "sample.pptx").read_bytes(), "sample.pptx")
        chunks = chunk_parsed_document(parsed)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["locator_json"]["slide"], 1)
        self.assertEqual(chunks[1]["locator_json"]["slide"], 2)
        self.assertIn("Kickoff", chunks[0]["chunk_text"])
        self.assertIn("Speaker Notes", chunks[1]["chunk_text"])

    def test_chunk_xlsx_fixture(self):
        parsed = parse_source_bytes("xlsx", (FIXTURE_DIR / "sample.xlsx").read_bytes(), "sample.xlsx")
        chunks = chunk_parsed_document(parsed)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["locator_json"]["sheet"], "Summary")
        self.assertIn("rows 1-2", chunks[0]["locator_json"]["range"])
        self.assertIn("A1=Owner", chunks[0]["chunk_text"])

    def test_chunk_eml_fixture(self):
        parsed = parse_source_bytes("eml", (FIXTURE_DIR / "sample.eml").read_bytes(), "sample.eml")
        chunks = chunk_parsed_document(parsed)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["locator_json"]["section"], "headers")
        self.assertEqual(chunks[1]["locator_json"]["section"], "body")
        self.assertIn("HTML body fallback", chunks[1]["chunk_text"])

    def test_chunk_txt_fixture(self):
        parsed = parse_source_bytes("txt", (FIXTURE_DIR / "sample.txt").read_bytes(), "sample.txt")
        chunks = chunk_parsed_document(parsed)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["locator_json"]["section"], "body")
        self.assertEqual(chunks[0]["section_path"], "text:body")
        self.assertIn("plain text upload fixture", chunks[0]["chunk_text"])

    def test_chunk_md_fixture(self):
        parsed = parse_source_bytes("md", (FIXTURE_DIR / "sample.md").read_bytes(), "sample.md")
        chunks = chunk_parsed_document(parsed)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(any(chunk["heading"] == "Overview" for chunk in chunks))
        self.assertTrue(any(chunk["heading"] == "Details" for chunk in chunks))
        self.assertTrue(any(chunk["section_path"] == "markdown:Overview" for chunk in chunks))
        self.assertTrue(any("```python" in chunk["chunk_text"] for chunk in chunks))

    def test_chunk_preview_serializes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            upload_path = root / "data" / "uploads" / "sample.pdf"
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            upload_path.write_bytes((FIXTURE_DIR / "sample.pdf").read_bytes())

            from app.ingestion import jobs as jobs_module

            original_root = jobs_module.REPO_ROOT
            try:
                jobs_module.REPO_ROOT = str(root)
                result = chunk_uploaded_source_file(
                    source_type="pdf",
                    file_name="sample.pdf",
                    storage_path="data/uploads/sample.pdf",
                    persist_chunk_preview=True,
                )
                preview_path = root / "data" / "extracted" / "sample.pdf.chunks.json"
                self.assertTrue(preview_path.exists())
                self.assertEqual(result["chunk_count"], 2)
            finally:
                jobs_module.REPO_ROOT = original_root

    def test_process_upload_makes_source_answerable_in_same_flow(self):
        unique_name = f"sample-{uuid4().hex[:8]}.pdf"
        upload = UploadFile(
            filename=unique_name,
            file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
            headers={"content-type": "application/pdf"},
        )
        result = asyncio.run(process_upload(upload))

        try:
            source = get_source_by_id(result["source_id"])
            self.assertIsNotNone(source)
            self.assertEqual(source.ingestion_status, "embedded")

            job = get_ingestion_job(result["job_id"])
            self.assertIsNotNone(job)
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.stage, "embedded")

            with engine.connect() as conn:
                chunk_count = conn.execute(
                    text("SELECT COUNT(*) FROM chunks WHERE source_id = :source_id"),
                    {"source_id": result["source_id"]},
                ).scalar_one()
                embedded_count = conn.execute(
                    text("SELECT COUNT(*) FROM chunks WHERE source_id = :source_id AND embedding IS NOT NULL"),
                    {"source_id": result["source_id"]},
                ).scalar_one()
                source_part_count = conn.execute(
                    text("SELECT COUNT(*) FROM source_parts WHERE source_id = :source_id"),
                    {"source_id": result["source_id"]},
                ).scalar_one()
            self.assertGreater(chunk_count, 0)
            self.assertEqual(chunk_count, embedded_count)
            self.assertGreater(source_part_count, 0)
            self.assertEqual(source.enrichment_status, "not_started")

            with engine.connect() as conn:
                enrichment_job_count = conn.execute(
                    text("SELECT COUNT(*) FROM enrichment_jobs WHERE source_id = :source_id"),
                    {"source_id": result["source_id"]},
                ).scalar_one()
            self.assertEqual(enrichment_job_count, 0)

            ask_response = ask_endpoint(
                AskRequest(
                    question="Page One Text",
                    k_chunks=3,
                    filters=SearchFilters(source_id=result["source_id"], source_type="pdf"),
                    mode="keyword",
                    dry_run=True,
                )
            )
            self.assertGreater(ask_response.used_chunks_count, 0)
            self.assertEqual(ask_response.debug_info["mode"], "keyword")
        finally:
            self._delete_seed_source(result["source_id"])

    def test_process_upload_batch_processes_multiple_files(self):
        unique_a = f"sample-a-{uuid4().hex[:8]}.pdf"
        unique_b = f"sample-b-{uuid4().hex[:8]}.pdf"
        uploads = [
            UploadFile(
                filename=unique_a,
                file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
                headers={"content-type": "application/pdf"},
            ),
            UploadFile(
                filename=unique_b,
                file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
                headers={"content-type": "application/pdf"},
            ),
        ]

        results = asyncio.run(process_upload_batch(uploads))

        try:
            self.assertEqual(len(results), 2)
            for result in results:
                source = get_source_by_id(result["source_id"])
                self.assertIsNotNone(source)
                self.assertEqual(source.ingestion_status, "embedded")

                job = get_ingestion_job(result["job_id"])
                self.assertIsNotNone(job)
                self.assertEqual(job.status, "completed")
        finally:
            for result in results:
                self._delete_seed_source(result["source_id"])

    def test_delete_uploaded_source_removes_source_and_file(self):
        unique_name = f"sample-delete-{uuid4().hex[:8]}.pdf"
        upload = UploadFile(
            filename=unique_name,
            file=BytesIO((FIXTURE_DIR / "sample.pdf").read_bytes()),
            headers={"content-type": "application/pdf"},
        )
        result = asyncio.run(process_upload(upload))
        storage_path = Path(REPO_ROOT) / result["storage_path"]

        try:
            self.assertTrue(storage_path.exists())
            delete_result = delete_uploaded_source(source_id=result["source_id"])
            self.assertEqual(delete_result["status"], "deleted")
            self.assertTrue(delete_result["file_deleted"])
            self.assertIsNone(get_source_by_id(result["source_id"]))
            self.assertFalse(storage_path.exists())
        finally:
            if storage_path.exists():
                storage_path.unlink()

    def test_adapter_registry_covers_supported_source_types(self):
        for source_type in settings.ALLOWED_UPLOAD_EXTENSIONS:
            self.assertTrue(callable(get_adapter(source_type)))

    def test_upload_validation_accepts_txt_mime(self):
        import app.ingestion.jobs as jobs_module

        self.assertEqual(jobs_module._detect_source_type("sample.txt"), "txt")
        jobs_module._validate_mime("txt", "text/plain")
        jobs_module._validate_mime("txt", "application/octet-stream")

    def test_upload_validation_accepts_md_mime(self):
        import app.ingestion.jobs as jobs_module

        self.assertEqual(jobs_module._detect_source_type("sample.md"), "md")
        jobs_module._validate_mime("md", "text/markdown")
        jobs_module._validate_mime("md", "text/plain")

    def test_job_status_endpoint_exposes_fields_needed_for_upload_progress(self):
        from app.api.corpus import job_status_endpoint
        from app.db.repo_jobs import create_ingestion_job

        source_id = self._seed_chunk_records()
        job_id = create_ingestion_job(
            source_id=source_id,
            status="processing",
            stage="chunking",
            triggered_by="upload",
            job_metadata_json={"ui_hint": "m24"},
        )
        try:
            item = job_status_endpoint(job_id)
            self.assertEqual(item.id, job_id)
            self.assertEqual(item.source_id, source_id)
            self.assertEqual(item.status, "processing")
            self.assertEqual(item.stage, "chunking")
            self.assertEqual(item.triggered_by, "upload")
            self.assertEqual(item.job_metadata_json["ui_hint"], "m24")
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ingestion_jobs WHERE id = :job_id"), {"job_id": job_id})
            self._delete_seed_source(source_id)

    def test_deep_lookup_request_requires_source_ids(self):
        from pydantic import ValidationError

        from app.core_rag.retrieval import DeepLookupRequest

        with self.assertRaises(ValidationError):
            DeepLookupRequest(question="Where is the answer?")

    def test_deep_lookup_rejects_too_many_source_ids(self):
        from fastapi import HTTPException

        from app.api.deep_lookup import deep_lookup_endpoint
        from app.core_rag.retrieval import DeepLookupRequest

        with self.assertRaises(HTTPException) as ctx:
            deep_lookup_endpoint(
                DeepLookupRequest(
                    question='"keywordbanana"',
                    source_ids=[1, 2, 3, 4],
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "too_many_source_ids")

    def test_deep_lookup_rejects_empty_source_ids(self):
        from fastapi import HTTPException

        from app.api.deep_lookup import deep_lookup_endpoint
        from app.core_rag.retrieval import DeepLookupRequest

        with self.assertRaises(HTTPException) as ctx:
            deep_lookup_endpoint(DeepLookupRequest(question='"keywordbanana"', source_ids=[]))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "source_ids_required")

    def test_deep_lookup_returns_only_selected_source_ids(self):
        from app.api.deep_lookup import deep_lookup_endpoint
        from app.core_rag.retrieval import DeepLookupRequest

        seeded = self._seed_retrieval_records()
        try:
            response = deep_lookup_endpoint(
                DeepLookupRequest(
                    question='"keywordbanana"',
                    source_ids=[seeded["docx_source_id"]],
                    k=5,
                )
            )
        finally:
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "deep_lookup")
        self.assertEqual(response.scoped_source_ids, [seeded["docx_source_id"]])
        self.assertTrue(response.results)
        self.assertTrue(all(item.source_id == seeded["docx_source_id"] for item in response.results))

    def test_deep_lookup_multiple_sources_remain_scoped(self):
        from app.api.deep_lookup import deep_lookup_endpoint
        from app.core_rag.retrieval import DeepLookupRequest

        seeded = self._seed_retrieval_records()
        selected_ids = [seeded["pdf_source_id"], seeded["docx_source_id"]]
        try:
            response = deep_lookup_endpoint(
                DeepLookupRequest(
                    question='"keywordbanana"',
                    source_ids=selected_ids,
                    k=5,
                )
            )
        finally:
            self._delete_retrieval_records(seeded.values())

        self.assertEqual(response.mode, "deep_lookup")
        self.assertEqual(response.scoped_source_ids, selected_ids)
        self.assertTrue(response.results)
        self.assertTrue(all(item.source_id in selected_ids for item in response.results))

    def test_deep_lookup_route_is_registered(self):
        route_paths = {route.path for route in app.routes}
        self.assertIn("/deep_lookup", route_paths)

    def test_get_chunks_to_embed_returns_unembedded_chunks(self):
        source_id = self._seed_chunk_records()
        try:
            selected = get_chunks_to_embed(force=False, source_id=source_id)
            self.assertEqual(len(selected), 2)
            self.assertTrue(all(item["source_id"] == source_id for item in selected))
        finally:
            self._delete_seed_source(source_id)

    def test_process_embeddings_updates_chunk_vectors(self):
        source_id = self._seed_chunk_records()
        try:
            import app.embedding.process as process_module

            original_embed_texts = process_module.embed_texts
            expected_dim = process_module.get_expected_dim()
            fake_vector = [0.1] + ([0.0] * (expected_dim - 1))
            process_module.embed_texts = lambda texts: [list(fake_vector) for _ in texts]
            try:
                stats = process_embeddings(force=True, source_id=source_id)
            finally:
                process_module.embed_texts = original_embed_texts

            self.assertEqual(stats["chunks_total_selected"], 2)
            self.assertEqual(stats["chunks_embedded"], 2)
            with engine.connect() as conn:
                embedded_count = conn.execute(
                    text("SELECT COUNT(*) FROM chunks WHERE source_id = :source_id AND embedding IS NOT NULL"),
                    {"source_id": source_id},
                ).scalar_one()
            self.assertEqual(embedded_count, 2)
        finally:
            self._delete_seed_source(source_id)

    def test_keyword_search_remains_queryable_for_chunk_text(self):
        source_id = self._seed_chunk_records()
        try:
            results = search_chunks_keyword("chunk one", k=5, source_id=source_id)
            self.assertTrue(results)
            self.assertEqual(results[0]["source_id"], source_id)
            self.assertIn("Embedding test chunk one", results[0]["snippet"])
        finally:
            self._delete_seed_source(source_id)

    def test_db_checks_report_index_and_keyword_readiness(self):
        import app.embedding.embedder as embedder_module

        original_get_expected_dim = embedder_module.get_expected_dim
        embedder_module.get_expected_dim = lambda: 3
        try:
            run_migrations()
            checks = collect_db_checks()
        finally:
            embedder_module.get_expected_dim = original_get_expected_dim
            run_migrations()

        self.assertTrue(checks["keyword index exists on chunks.search_tsv"])
        self.assertTrue(checks["vector index exists on chunks.embedding"])
        self.assertTrue(checks["enrichment_jobs.artifact_version column exists"])

    def test_migration_plan_exposes_ordered_patch_steps(self):
        from app.db.migrate import describe_migration_plan

        plan = describe_migration_plan()
        self.assertEqual([item["step_id"] for item in plan], ["MIG-P001", "MIG-P002", "MIG-P003", "MIG-P004"])
        self.assertTrue(all(item["description"] for item in plan))

    def test_vector_mode_returns_embedded_chunk_match(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
        try:
            response = perform_search(SearchRequest(question="semantic alpha", k=5, mode="vector"))
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "vector")
        self.assertEqual(response.results[0].source_id, seeded["pdf_source_id"])
        self.assertIn("page", response.results[0].locator)

    def test_keyword_mode_returns_full_text_match(self):
        seeded = self._seed_retrieval_records()
        try:
            response = perform_search(
                SearchRequest(
                    question="keywordbanana",
                    k=5,
                    mode="keyword",
                    filters=SearchFilters(source_id=seeded["docx_source_id"]),
                )
            )
        finally:
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertEqual(response.mode, "keyword")
        self.assertEqual(response.results[0].source_id, seeded["docx_source_id"])
        self.assertIn("keywordbanana", response.results[0].snippet)

    def test_hybrid_mode_merges_candidates_stably(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
        try:
            response = perform_search(SearchRequest(question="keywordbanana alpha", k=5, mode="hybrid", debug=True))
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertGreaterEqual(len(response.results), 2)
        self.assertEqual(response.mode, "hybrid")
        self.assertTrue(all(result.combined_score is not None for result in response.results[:2]))

    def test_keyword_mode_soft_fallback_recovers_split_seo_evidence(self):
        seeded = self._seed_seo_anomaly_records()
        try:
            response = perform_search(
                SearchRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k=5,
                    mode="keyword",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                )
            )
        finally:
            self._delete_seed_source(seeded["source_id"])

        self.assertEqual(response.mode, "keyword")
        top_ids = [item.chunk_id for item in response.results[:2]]
        self.assertEqual(
            top_ids,
            [
                seeded["chunk_ids"]["ground_truth_page_1"],
                seeded["chunk_ids"]["ground_truth_page_2"],
            ],
        )

    def test_vector_mode_anchor_boost_surfaces_true_seo_chunks(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0, 0.0] + [0.0] * 382 for _ in texts]
        try:
            response = perform_search(
                SearchRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k=4,
                    mode="vector",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(seeded["source_id"])

        returned_ids = [item.chunk_id for item in response.results]
        self.assertEqual(response.mode, "vector")
        self.assertEqual(returned_ids[0], seeded["chunk_ids"]["ground_truth_page_1"])
        self.assertIn(seeded["chunk_ids"]["ground_truth_page_2"], returned_ids[:4])

    def test_hybrid_mode_anchor_boost_recovers_true_seo_chunks(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0, 0.0] + [0.0] * 382 for _ in texts]
        try:
            response = perform_search(
                SearchRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k=4,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                    debug=True,
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(seeded["source_id"])

        top_ids = [item.chunk_id for item in response.results[:3]]
        self.assertEqual(response.mode, "hybrid")
        self.assertEqual(response.results[0].chunk_id, seeded["chunk_ids"]["ground_truth_page_1"])
        self.assertIn(seeded["chunk_ids"]["ground_truth_page_2"], top_ids)

    def test_ask_dry_run_uses_ground_truth_seo_chunks_after_hybrid_recovery(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module
        from app.core_rag.answering import perform_ask

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0, 0.0] + [0.0] * 382 for _ in texts]
        try:
            response = perform_ask(
                AskRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k_chunks=3,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                    dry_run=True,
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(seeded["source_id"])

        prompt = response.debug_info["user_prompt"]
        self.assertEqual(response.debug_info["mode"], "hybrid")
        self.assertIn("dominated by large aggregators", prompt)
        self.assertIn("cracking this space via SEO would be challenging", prompt)

    def test_deep_research_search_returns_trace_metadata_and_uses_custom_query(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0, 0.0] + [0.0] * 382 for _ in texts]
        try:
            response = perform_search(
                SearchRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k=4,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                    deep_research=True,
                    custom_query="SEO rank aggregators newcomer",
                    anchor_terms=["SEO", "aggregators"],
                    expand_neighbors=True,
                    force_rare_keyword_scan=True,
                    debug=True,
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(seeded["source_id"])

        self.assertEqual(response.mode, "hybrid")
        self.assertTrue(response.debug_info["deep_research_used"])
        self.assertEqual(response.debug_info["effective_query"], "SEO rank aggregators newcomer")
        self.assertTrue(response.debug_info["neighbor_expansion_used"])
        self.assertTrue(response.debug_info["force_rare_keyword_scan"])
        self.assertEqual(response.results[0].chunk_id, seeded["chunk_ids"]["ground_truth_page_1"])

    def test_ask_dry_run_includes_retrieval_trace_for_deep_research(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module
        from app.core_rag.answering import perform_ask

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0, 0.0] + [0.0] * 382 for _ in texts]
        try:
            response = perform_ask(
                AskRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k_chunks=4,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                    dry_run=True,
                    deep_research=True,
                    custom_query="SEO rank aggregators newcomer",
                    anchor_terms=["SEO", "aggregators"],
                    expand_neighbors=True,
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(seeded["source_id"])

        self.assertEqual(response.mode, "hybrid")
        self.assertTrue(response.debug_info["retrieval_trace"]["deep_research_used"])
        self.assertIn("aggregators", " ".join(response.debug_info["retrieval_trace"]["anchor_terms_used"]))

    def test_source_type_filter_works(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
        try:
            request = SearchRequest(
                question="alpha",
                k=5,
                mode="vector",
                filters=SearchFilters(source_type="pdf"),
            )
            response = perform_search(request)
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertTrue(response.results)
        self.assertTrue(all(result.source_type == "pdf" for result in response.results))

    def test_search_route_returns_expected_shape_and_reranker_flag_stays_off(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
        try:
            response = search_endpoint(
                SearchRequest(question="alpha", k=5, mode="vector", debug=True)
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        payload = response.model_dump()
        self.assertEqual(payload["mode"], "vector")
        self.assertIn("results", payload)
        self.assertTrue(payload["results"])
        self.assertIn("locator", payload["results"][0])
        self.assertIsNone(payload["results"][0]["rerank_score"])

    def test_ask_route_is_registered(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/ask", paths)

    def test_ask_dry_run_returns_stable_prompt_payload(self):
        import app.core_rag.answering as answering_module

        original_perform_search = answering_module.perform_search
        answering_module.perform_search = lambda request: SearchResponse(
            results=[
                SearchResultItem(
                    chunk_id=11,
                    source_id=21,
                    source_part_id=31,
                    file_name="evidence.pdf",
                    source_type="pdf",
                    heading="Page 1",
                    locator="page=1",
                    snippet="Grounded evidence snippet.",
                    score=0.9,
                )
            ],
            latency_ms=3,
            mode="hybrid",
        )
        try:
            response = ask_endpoint(
                AskRequest(question="What happened?", k_chunks=4, mode="hybrid", dry_run=True)
            )
        finally:
            answering_module.perform_search = original_perform_search

        payload = response.model_dump()
        self.assertEqual(payload["used_chunks_count"], 1)
        self.assertIsNone(payload["answer"])
        self.assertEqual(payload["debug_info"]["mode"], "hybrid")
        self.assertIn("user_prompt", payload["debug_info"])

    def test_ask_returns_not_found_when_no_evidence(self):
        import app.core_rag.answering as answering_module

        original_perform_search = answering_module.perform_search
        answering_module.perform_search = lambda request: SearchResponse(results=[], latency_ms=1, mode="hybrid")
        try:
            response = ask_endpoint(AskRequest(question="Unsupported?", dry_run=True))
            fallback = answering_module.perform_ask(AskRequest(question="Unsupported?", dry_run=False))
        finally:
            answering_module.perform_search = original_perform_search

        self.assertEqual(response.used_chunks_count, 0)
        self.assertEqual(fallback.answer, "Not found in provided sources.")
        self.assertEqual(fallback.citations, [])

    def test_ask_blocks_citation_laundering_and_returns_ui_safe_fields(self):
        import app.api.ask as ask_api_module
        import app.core_rag.answering as answering_module

        original_verify_llm_ready = ask_api_module.verify_llm_ready
        original_perform_search = answering_module.perform_search
        original_generate_answer = answering_module.generate_answer
        ask_api_module.verify_llm_ready = lambda: True
        answering_module.perform_search = lambda request: SearchResponse(
            results=[
                SearchResultItem(
                    chunk_id=101,
                    source_id=202,
                    source_part_id=303,
                    file_name="alpha.pdf",
                    source_type="pdf",
                    heading="Page 2",
                    locator="page=2",
                    snippet="Alpha clause evidence.",
                    score=0.91,
                )
            ],
            latency_ms=4,
            mode="hybrid",
        )
        answering_module.generate_answer = lambda system_prompt, user_prompt: {
            "success": True,
            "content": '{"answer":"Supported claim [S1] and fake claim [S9]","citations":["S1","S9"]}',
        }
        try:
            response = ask_endpoint(AskRequest(question="What is supported?", mode="hybrid", dry_run=False))
        finally:
            ask_api_module.verify_llm_ready = original_verify_llm_ready
            answering_module.perform_search = original_perform_search
            answering_module.generate_answer = original_generate_answer

        self.assertEqual(response.answer, "Supported claim [S1] and fake claim")
        self.assertEqual(len(response.citations), 1)
        citation = response.citations[0]
        self.assertEqual(citation.citation_id, "S1")
        self.assertEqual(citation.source_id, 202)
        self.assertEqual(citation.source_part_id, 303)
        self.assertEqual(citation.chunk_id, 101)
        self.assertEqual(citation.file_name, "alpha.pdf")
        self.assertEqual(citation.source_type, "pdf")
        self.assertEqual(citation.locator, "page=2")
        self.assertEqual(citation.snippet, "Alpha clause evidence.")

    def test_ask_route_returns_503_when_llm_is_not_ready(self):
        import app.api.ask as ask_api_module

        original_verify_llm_ready = ask_api_module.verify_llm_ready
        ask_api_module.verify_llm_ready = lambda: False
        try:
            with self.assertRaises(HTTPException) as ctx:
                ask_endpoint(AskRequest(question="Call the model", dry_run=False))
        finally:
            ask_api_module.verify_llm_ready = original_verify_llm_ready

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail["error"], "llm_not_ready")

    def test_verify_llm_ready_accepts_ollama_v1_models_data_shape(self):
        import app.llm.client as llm_client_module

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"object": "list", "data": [{"id": settings.LLM_MODEL}]}

        class FakeClient:
            def __init__(self, timeout):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            @staticmethod
            def get(url):
                return FakeResponse()

        class FakeHttpx:
            Client = FakeClient

        original_get_httpx = llm_client_module._get_httpx
        original_provider = settings.LLM_PROVIDER
        try:
            llm_client_module._get_httpx = lambda: FakeHttpx
            settings.LLM_PROVIDER = "ollama"
            self.assertTrue(llm_client_module.verify_llm_ready())
        finally:
            llm_client_module._get_httpx = original_get_httpx
            settings.LLM_PROVIDER = original_provider

    def test_parse_docx_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.docx").read_bytes()
        parsed = parse_source_bytes("docx", content, "sample.docx")
        self.assertEqual(parsed.source_type, "docx")
        self.assertTrue(any(part.part_type == "section" for part in parsed.parts))
        self.assertTrue(any(part.part_type == "paragraph" for part in parsed.parts))
        self.assertTrue(any(part.part_type == "table" for part in parsed.parts))
        self.assertIn("Project Phoenix", "\n".join(part.content_text for part in parsed.parts))

    def test_parse_pptx_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.pptx").read_bytes()
        parsed = parse_source_bytes("pptx", content, "sample.pptx")
        self.assertEqual(parsed.source_type, "pptx")
        self.assertEqual(parsed.metadata["slide_count"], 2)
        self.assertEqual(parsed.parts[0].part_type, "slide")
        self.assertIn("Kickoff", parsed.parts[0].content_text)
        self.assertIn("Speaker Notes", parsed.parts[1].content_text)

    def test_parse_xlsx_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.xlsx").read_bytes()
        parsed = parse_source_bytes("xlsx", content, "sample.xlsx")
        self.assertEqual(parsed.source_type, "xlsx")
        self.assertEqual(parsed.parts[0].part_type, "sheet")
        self.assertEqual(parsed.metadata["sheet_count"], 2)
        self.assertIn("A1=Owner", parsed.parts[0].content_text)
        self.assertEqual(parsed.parts[0].locator_json["sheet"], "Summary")

    def test_parse_eml_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.eml").read_bytes()
        parsed = parse_source_bytes("eml", content, "sample.eml")
        self.assertEqual(parsed.source_type, "eml")
        self.assertEqual(parsed.parts[0].part_type, "email_header")
        self.assertEqual(parsed.parts[1].part_type, "email_body")
        self.assertEqual(parsed.metadata["attachment_count"], 1)
        self.assertIn("HTML body fallback", parsed.parts[1].content_text)
        self.assertEqual(parsed.parts[1].locator_json["body_format"], "text/html_fallback")

    def test_parse_pdf_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.pdf").read_bytes()
        parsed = parse_source_bytes("pdf", content, "sample.pdf")
        self.assertEqual(parsed.source_type, "pdf")
        self.assertEqual(parsed.metadata["page_count"], 2)
        self.assertEqual(parsed.parts[0].part_type, "page")
        self.assertEqual(parsed.parts[0].locator_json["page"], 1)
        self.assertEqual(parsed.parts[1].locator_json["page"], 2)
        self.assertIn("Page One Text", parsed.parts[0].content_text)
        self.assertIn("Page Two Text", parsed.parts[1].content_text)

    def test_parse_txt_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.txt").read_bytes()
        parsed = parse_source_bytes("txt", content, "sample.txt")
        self.assertEqual(parsed.source_type, "txt")
        self.assertEqual(len(parsed.parts), 1)
        self.assertEqual(parsed.parts[0].part_type, "text_block")
        self.assertEqual(parsed.parts[0].locator_json["section"], "body")
        self.assertIn("plain text upload fixture", parsed.parts[0].content_text)

    def test_parse_md_to_canonical_representation(self):
        content = (FIXTURE_DIR / "sample.md").read_bytes()
        parsed = parse_source_bytes("md", content, "sample.md")
        self.assertEqual(parsed.source_type, "md")
        self.assertTrue(any(part.title == "Overview" for part in parsed.parts))
        self.assertTrue(any(part.title == "Details" for part in parsed.parts))
        self.assertTrue(any("[docs](https://example.com/docs)" in part.content_text for part in parsed.parts))
        self.assertTrue(any("```python" in part.content_text for part in parsed.parts))
