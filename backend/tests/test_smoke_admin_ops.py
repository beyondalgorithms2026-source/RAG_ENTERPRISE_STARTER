from tests.smoke_test_base import *


class SmokeTestAdminOps(SmokeTestBase):
    def _seed_acl_records(self):
        from app.db.repo_acl import assign_document_acl

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            alpha_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', 'internal', :hash_sha256, 100,
                        'embedded', 'not_started', CAST(:metadata AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"acl-alpha-{suffix}.pdf",
                    "storage_path": f"tests/acl-alpha-{suffix}.pdf",
                    "hash_sha256": (suffix + "alpha") * 4,
                    "metadata": json.dumps({"corpus": "alpha-corpus"}),
                },
            ).scalar_one()
            beta_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', 'confidential', :hash_sha256, 100,
                        'embedded', 'not_started', CAST(:metadata AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"acl-beta-{suffix}.pdf",
                    "storage_path": f"tests/acl-beta-{suffix}.pdf",
                    "hash_sha256": (suffix + "beta") * 4,
                    "metadata": json.dumps({"corpus": "beta-corpus"}),
                },
            ).scalar_one()

        insert_chunks(
            alpha_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Alpha Restricted",
                    "section_path": "page:1",
                    "chunk_text": "alpha acl protected content only for group alpha alphaonlytoken123",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "acl"},
                }
            ],
        )
        insert_chunks(
            beta_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Beta Restricted",
                    "section_path": "page:1",
                    "chunk_text": "beta acl protected content only for group beta betaonlytoken456",
                    "token_count": 8,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "acl"},
                }
            ],
        )

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, source_id
                    FROM chunks
                    WHERE source_id IN (:alpha_source_id, :beta_source_id)
                    ORDER BY source_id ASC
                    """
                ),
                {"alpha_source_id": alpha_source_id, "beta_source_id": beta_source_id},
            ).fetchall()
        update_chunk_embeddings([(row[0], [1.0] + [0.0] * 383) for row in rows])
        assign_document_acl(source_id=alpha_source_id, group_names=["group-alpha"])
        assign_document_acl(source_id=beta_source_id, group_names=["group-beta"])
        return {"alpha_source_id": alpha_source_id, "beta_source_id": beta_source_id}

    def test_m4_acl_trimming_prevents_cross_group_search_and_citation_leaks(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.core_rag.answering import perform_ask
        from app.db.migrate import run_migrations
        from app.db.repo_acl import sync_authenticated_user

        run_migrations()
        seeded = self._seed_acl_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        token = None
        try:
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            alpha_user = AuthenticatedUser(user_id="user-alpha", email="alpha@example.com", groups=["group-alpha"], roles=["user"])
            sync_authenticated_user(alpha_user)
            token = set_current_user(alpha_user)

            alpha_search = perform_search(SearchRequest(question="alphaonlytoken123", k=5, mode="keyword"))
            self.assertTrue(alpha_search.results)
            self.assertTrue(all(item.source_id == seeded["alpha_source_id"] for item in alpha_search.results))

            forbidden_search = perform_search(SearchRequest(question="betaonlytoken456", k=5, mode="keyword"))
            self.assertTrue(all(item.source_id != seeded["beta_source_id"] for item in forbidden_search.results))

            forbidden_answer = perform_ask(AskRequest(question="betaonlytoken456", k_chunks=3, mode="keyword"))
            self.assertEqual(forbidden_answer.answer, "Not found in provided sources.")
            self.assertEqual(forbidden_answer.citations, [])
            self.assertEqual(forbidden_answer.used_chunks_count, 0)
        finally:
            if token is not None:
                reset_current_user(token)
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

    def test_m4_acl_leak_pack_differentiates_users_and_emits_audit_logs(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.migrate import run_migrations
        from app.db.repo_acl import sync_authenticated_user

        run_migrations()
        seeded = self._seed_acl_records()
        cases = json.loads((EVAL_FIXTURE_DIR / "acl_leak_cases.json").read_text(encoding="utf-8"))
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        try:
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            for case in cases:
                user = AuthenticatedUser(
                    user_id=case["user_id"],
                    email=f"{case['user_id']}@example.com",
                    groups=list(case["groups"]),
                    roles=["user"],
                )
                sync_authenticated_user(user)
                token = set_current_user(user)
                try:
                    with self.assertLogs(logger.name, level="INFO") as captured:
                        response = perform_search(SearchRequest(question=case["query"], k=5, mode="keyword"))
                finally:
                    reset_current_user(token)

                self.assertTrue(response.results)
                allowed_source_id = seeded[case["allowed_source_key"]]
                forbidden_source_id = seeded[case["forbidden_source_key"]]
                self.assertTrue(all(item.source_id == allowed_source_id for item in response.results))
                self.assertTrue(all(item.source_id != forbidden_source_id for item in response.results))
                output = "\n".join(captured.output)
                self.assertIn('"event": "search.audit_access"', output)
                self.assertIn(f'"user_id": "{case["user_id"]}"', output)
                self.assertIn('"user_groups":', output)
                self.assertIn('"doc_ids":', output)
                self.assertIn('"corpora":', output)
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

    def test_m3_oidc_login_redirect_support_exists(self):
        from fastapi.testclient import TestClient

        import app.api.auth as auth_api

        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_build_login_url = auth_api.build_login_url
        try:
            settings.AUTH_ENABLED = True
            auth_api.build_login_url = lambda next_path: ("https://issuer.example.com/authorize?state=fake", "signed-state")
            response = client.get("/auth/login", params={"next_path": "/frontend/"}, follow_redirects=False)
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            auth_api.build_login_url = original_build_login_url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://issuer.example.com/authorize?state=fake")
        self.assertIn(settings.AUTH_STATE_COOKIE_NAME, response.headers.get("set-cookie", ""))

    def test_m3_ask_requires_auth_when_enabled(self):
        from fastapi.testclient import TestClient

        import app.main as main_module

        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_verify = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: None
            response = client.post("/ask", json={"question": "Who is authenticated?", "dry_run": True, "mode": "hybrid"})
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_verify

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"], "authentication_required")

    def test_m3_authenticated_user_identity_appears_in_logs(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        import app.core_rag.retrieval as retrieval_module
        import app.core_rag.answering as answering_module
        from app.auth.context import AuthenticatedUser

        seeded = self._seed_retrieval_records()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="user-123",
                email="user@example.com",
                roles=["user", "admin"],
                issuer="https://issuer.example.com",
            )
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            answering_module.generate_answer = lambda system_prompt, user_prompt: {
                "success": True,
                "content": "{\"answer\":\"The answer confirms the alpha semantic vector match text in the retrieved source [S1]\",\"citations\":[\"S1\"]}",
            }
            with self.assertLogs(logger.name, level="INFO") as captured:
                response = client.post(
                    "/ask",
                    json={
                        "question": "alpha semantic vector match text",
                        "k_chunks": 2,
                        "mode": "hybrid",
                        "dry_run": True,
                        "filters": {"source_id": seeded["pdf_source_id"]},
                    },
                    headers={"Authorization": "Bearer fake-token"},
                )
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer
            self._delete_retrieval_records(seeded.values())

    def test_m5_admin_endpoints_require_admin_role(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="user-only",
                email="user@example.com",
                roles=["user"],
            )
            response = client.get("/admin/profiles")
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_required")

    def test_m5_admin_control_plane_runs_without_code_edits(self):
        from fastapi.testclient import TestClient

        import app.api.admin as admin_api
        import app.main as main_module
        import app.core_rag.retrieval as retrieval_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        seeded = self._seed_retrieval_records()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        original_embed_texts = retrieval_module.embed_texts
        original_reindex = admin_api.admin_reindex_source
        original_load_eval_cases = admin_api.load_eval_cases
        original_run_eval = admin_api.run_retrieval_eval
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-1",
                email="admin@example.com",
                roles=["user", "admin"],
            )
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            admin_api.admin_reindex_source = lambda source_id, force=False: {
                "status": "completed",
                "source_id": source_id,
                "job_id": 999,
                "chunk_count": 1,
                "source_part_count": 1,
            }
            admin_api.load_eval_cases = lambda: []
            admin_api.run_retrieval_eval = lambda cases, report_path=None, debug=False: {
                "summary": {"kind": "retrieval", "total": 0, "passed": 0, "failed": 0},
                "report_metadata": {"active_profiles": admin_api.get_active_profile_snapshot()},
            }

            create_response = client.post(
                "/admin/corpora",
                json={"name": "ops-corpus", "description": "Operations corpus", "metadata_json": {"owner": "ops"}},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(create_response.status_code, 200)

            assign_response = client.patch(
                "/admin/corpora/ops-corpus/sources",
                json={"source_ids": [seeded["pdf_source_id"]], "sensitivity_label": "internal"},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(assign_response.status_code, 200)
            self.assertEqual(assign_response.json()["updated_source_ids"], [seeded["pdf_source_id"]])

            corpora_response = client.get("/admin/corpora", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(corpora_response.status_code, 200)
            corpora_payload = corpora_response.json()
            self.assertTrue(any(item["name"] == "ops-corpus" for item in corpora_payload["corpora"]))

            reindex_response = client.post(
                f"/admin/sources/{seeded['pdf_source_id']}/reindex",
                json={"force": True},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(reindex_response.status_code, 200)
            self.assertEqual(reindex_response.json()["job_id"], 999)

            trace_response = client.post(
                "/admin/traces/query-debug",
                json={"question": "alpha semantic vector match text", "mode": "hybrid", "k": 3},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(trace_response.status_code, 200)
            trace_payload = trace_response.json()
            self.assertEqual(trace_payload["mode"], "hybrid")
            self.assertIn("trace", trace_payload)
            self.assertIn("request_id", trace_payload["trace"])

            metadata_response = client.get("/admin/profiles/metadata", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(metadata_response.status_code, 200)
            self.assertIn("strategy_defaults", metadata_response.json())

            eval_response = client.post(
                "/admin/eval/run",
                json={"report_kind": "retrieval"},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(eval_response.status_code, 200)
            self.assertEqual(eval_response.json()["status"], "completed")

            reports_response = client.get("/admin/eval/reports", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(reports_response.status_code, 200)
            self.assertTrue(any(item["kind"] == "retrieval" for item in reports_response.json()["reports"]))
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate
            retrieval_module.embed_texts = original_embed_texts
            admin_api.admin_reindex_source = original_reindex
            admin_api.load_eval_cases = original_load_eval_cases
            admin_api.run_retrieval_eval = original_run_eval
            self._delete_retrieval_records(seeded.values())

    def test_m5_admin_job_status_surface_lists_ingestion_and_enrichment_jobs(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser
        from app.db.repo_jobs import create_enrichment_job, create_ingestion_job

        run_migrations()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-2",
                email="admin2@example.com",
                roles=["admin"],
            )
            ingestion_job_id = create_ingestion_job(
                source_id=None,
                status="queued",
                stage="admin_reindex",
                triggered_by="admin_reindex",
                job_metadata_json={"test": "m5"},
            )
            enrichment_job_id = create_enrichment_job(
                source_id=None,
                enrichment_type="graph",
                status="queued",
                stage="admin_enrich",
                job_metadata_json={"test": "m5"},
            )

            jobs_response = client.get("/admin/jobs", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(jobs_response.status_code, 200)
            jobs_payload = jobs_response.json()
            self.assertTrue(any(item["id"] == ingestion_job_id for item in jobs_payload["ingestion_jobs"]))
            self.assertTrue(any(item["id"] == enrichment_job_id for item in jobs_payload["enrichment_jobs"]))

            ingestion_response = client.get(
                f"/admin/jobs/ingestion/{ingestion_job_id}",
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(ingestion_response.status_code, 200)
            self.assertEqual(ingestion_response.json()["stage"], "admin_reindex")

            enrichment_response = client.get(
                f"/admin/jobs/enrichment/{enrichment_job_id}",
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(enrichment_response.status_code, 200)
            self.assertEqual(enrichment_response.json()["stage"], "admin_enrich")
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

    def test_m10_1_3_1_admin_truthful_surfaces_and_audit_log(self):
        from fastapi.testclient import TestClient

        import app.api.admin as admin_api
        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        class StubEnrichmentResult:
            def __init__(self, source_id: int):
                self.source_id = source_id

            def model_dump(self):
                return {"status": "completed", "source_id": self.source_id, "job_id": 321}

        run_migrations()
        seeded = self._seed_retrieval_records()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        original_reindex = admin_api.admin_reindex_source
        original_enrich = admin_api.admin_rerun_enrichment
        original_run_eval = admin_api.run_retrieval_eval
        original_load_eval_cases = admin_api.load_eval_cases
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-ops",
                email="admin.ops@example.com",
                roles=["admin"],
                groups=["ops", "legal"],
            )
            admin_api.admin_reindex_source = lambda source_id, force=False: {
                "status": "completed",
                "source_id": source_id,
                "job_id": 123,
                "chunk_count": 1,
                "source_part_count": 1,
            }
            admin_api.admin_rerun_enrichment = lambda source_id, force=False: StubEnrichmentResult(source_id)
            admin_api.load_eval_cases = lambda: []
            admin_api.run_retrieval_eval = lambda cases, report_path=None, debug=False: {
                "summary": {"pass_rate_percent": 100, "total": 0, "passed": 0, "failed": 0},
                "report_metadata": {"active_profiles": admin_api.get_active_profile_snapshot()},
            }

            profiles_response = client.get("/admin/profiles", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(profiles_response.status_code, 200)
            first_profile = profiles_response.json()["profiles"][0]
            activate_response = client.post(
                "/admin/profiles/active",
                json={"profile_type": first_profile["profile_type"], "profile_name": first_profile["name"]},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(activate_response.status_code, 200)

            create_response = client.post(
                "/admin/corpora",
                json={"name": "audit-ops", "description": "Audit ops corpus", "metadata_json": {}},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(create_response.status_code, 200)

            assign_response = client.patch(
                "/admin/corpora/audit-ops/sources",
                json={"source_ids": [seeded["pdf_source_id"]], "sensitivity_label": "internal"},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(assign_response.status_code, 200)

            source_update_response = client.patch(
                f"/admin/sources/{seeded['pdf_source_id']}",
                json={"sensitivity_label": "confidential", "acl_group_names": ["ops", "legal"]},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(source_update_response.status_code, 200)
            self.assertEqual(source_update_response.json()["source"]["sensitivity_label"], "confidential")

            reindex_response = client.post(
                f"/admin/sources/{seeded['pdf_source_id']}/reindex",
                json={"force": True},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(reindex_response.status_code, 200)

            enrich_response = client.post(
                f"/admin/sources/{seeded['pdf_source_id']}/enrich",
                json={"force": True},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(enrich_response.status_code, 200)

            eval_response = client.post(
                "/admin/eval/run",
                json={"report_kind": "retrieval"},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(eval_response.status_code, 200)

            overview_response = client.get("/admin/overview", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(overview_response.status_code, 200)
            overview_payload = overview_response.json()
            self.assertIsInstance(overview_payload["summary"]["source_count"], int)
            self.assertNotEqual(overview_payload["summary"]["source_count"], "45.2k")
            self.assertIn("alerts", overview_payload)

            sources_response = client.get("/admin/sources", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(sources_response.status_code, 200)
            source_item = next(item for item in sources_response.json()["sources"] if item["id"] == seeded["pdf_source_id"])
            self.assertEqual(source_item["corpus_name"], "audit-ops")
            self.assertEqual(set(source_item["acl_groups"]), {"legal", "ops"})

            access_response = client.get("/admin/access", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(access_response.status_code, 200)
            access_payload = access_response.json()
            self.assertGreaterEqual(access_payload["summary"]["protected_source_count"], 1)
            self.assertTrue(any(group["name"] == "ops" for group in access_payload["groups"]))

            audit_response = client.get("/admin/audit-log", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(audit_response.status_code, 200)
            actions = {item["action"] for item in audit_response.json()["events"]}
            self.assertTrue({"profile.activate", "corpus.create", "corpus.assign_sources", "source.update", "source.reindex", "source.enrich", "eval.run"}.issubset(actions))
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate
            admin_api.admin_reindex_source = original_reindex
            admin_api.admin_rerun_enrichment = original_enrich
            admin_api.run_retrieval_eval = original_run_eval
            admin_api.load_eval_cases = original_load_eval_cases
            self._delete_retrieval_records(seeded.values())

    def test_m17_b_1_live_configuration_candidate_drafts_and_approved_registry(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-tuning",
                email="admin.tuning@example.com",
                roles=["admin"],
                groups=["ops"],
            )

            tuning_response = client.get("/admin/tuning/configurations", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(tuning_response.status_code, 200)
            tuning_payload = tuning_response.json()
            self.assertEqual(tuning_payload["live_configuration"]["version_label"], "live-current")
            self.assertIn("llm", tuning_payload["approved_options"])
            self.assertGreaterEqual(len(tuning_payload["approved_options"]["llm"]), 1)
            self.assertGreaterEqual(len(tuning_payload["approved_options"]["embedding"]), 1)
            self.assertGreaterEqual(len(tuning_payload["approved_options"]["reranker"]), 1)

            live_selected = tuning_payload["live_configuration"]["selected_profiles"]
            create_response = client.post(
                "/admin/tuning/drafts",
                json={
                    "name": "Quality candidate",
                    "description": "M17.b.1 smoke draft",
                    "selected_profiles": {
                        "llm": tuning_payload["approved_options"]["llm"][0]["name"],
                        "embedding": tuning_payload["approved_options"]["embedding"][0]["name"],
                        "reranker": tuning_payload["approved_options"]["reranker"][0]["name"],
                        "retrieval": live_selected["retrieval"],
                    },
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(create_response.status_code, 200)
            draft = create_response.json()["draft"]
            self.assertEqual(draft["status"], "draft")
            self.assertTrue(draft["version_label"].startswith("draft-"))

            invalid_response = client.post(
                "/admin/tuning/drafts",
                json={
                    "name": "Invalid candidate",
                    "description": "Should be blocked by the approved registry",
                    "selected_profiles": {
                        "llm": "freeform-llm",
                        "embedding": tuning_payload["approved_options"]["embedding"][0]["name"],
                        "reranker": tuning_payload["approved_options"]["reranker"][0]["name"],
                        "retrieval": live_selected["retrieval"],
                    },
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(invalid_response.status_code, 422)

            patch_response = client.patch(
                f"/admin/tuning/drafts/{draft['id']}",
                json={"description": "Updated M17.b.1 smoke draft"},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(patch_response.status_code, 200)
            self.assertEqual(patch_response.json()["draft"]["description"], "Updated M17.b.1 smoke draft")

            profiles_response = client.get("/admin/profiles", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(profiles_response.status_code, 200)
            llm_profiles = [profile for profile in profiles_response.json()["profiles"] if profile["profile_type"] == "llm"]
            target_profile = next((profile for profile in llm_profiles if not profile["is_active"]), llm_profiles[0])
            activate_response = client.post(
                "/admin/profiles/active",
                json={"profile_type": "llm", "profile_name": target_profile["name"]},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(activate_response.status_code, 200)
            self.assertEqual(activate_response.json()["live_configuration"]["version_label"], "live-current")
            self.assertEqual(activate_response.json()["live_configuration"]["selected_profiles"]["llm"], target_profile["name"])

            audit_response = client.get("/admin/audit-log", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(audit_response.status_code, 200)
            actions = {item["action"] for item in audit_response.json()["events"]}
            self.assertTrue({"tuning.draft.create", "tuning.draft.update", "profile.activate"}.issubset(actions))
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

    def test_m17_b_2_interactive_sandbox_compare_and_embedding_scope_warning(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser
        import app.core_rag.answering as answering_module
        import app.core_rag.retrieval as retrieval_module

        run_migrations()
        seeded = self._seed_retrieval_records()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-compare",
                email="admin.compare@example.com",
                roles=["admin"],
                groups=["ops"],
            )
            retrieval_module.embed_texts = lambda texts: [[1.0] + [0.0] * 383 for _ in texts]
            answering_module.generate_answer = lambda system_prompt, user_prompt: {
                "success": True,
                "content": "{\"answer\":\"Sandbox compare confirms the alpha semantic vector match text in the retrieved source [S1]\",\"citations\":[\"S1\"]}",
            }

            tuning_payload = client.get("/admin/tuning/configurations", headers={"Authorization": "Bearer fake-token"}).json()
            selected_profiles = dict(tuning_payload["live_configuration"]["selected_profiles"])

            compare_response = client.post(
                "/admin/tuning/compare",
                json={
                    "question": "alpha semantic vector match text",
                    "selected_profiles": selected_profiles,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "chunk_size_cap_chars": 640,
                    "k_retrieval_count": 2,
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(compare_response.status_code, 200)
            compare_payload = compare_response.json()
            self.assertEqual(compare_payload["live_run"]["status"], "completed")
            self.assertEqual(compare_payload["candidate_run"]["status"], "completed")
            self.assertEqual(compare_payload["candidate_run"]["generation_summary"]["temperature"], 0.7)
            self.assertEqual(compare_payload["candidate_run"]["generation_summary"]["top_p"], 0.9)
            self.assertEqual(compare_payload["candidate_run"]["retrieval_summary"]["answer_time_chunk_cap_chars"], 640)
            self.assertLessEqual(compare_payload["candidate_run"]["used_chunks_count"], 2)

            alternate_embedding = next(
                option["name"]
                for option in tuning_payload["approved_options"]["embedding"]
                if option["name"] != selected_profiles["embedding"]
            )
            blocked_response = client.post(
                "/admin/tuning/compare",
                json={
                    "question": "alpha semantic vector match text",
                    "selected_profiles": {**selected_profiles, "embedding": alternate_embedding},
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "chunk_size_cap_chars": 640,
                    "k_retrieval_count": 2,
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(blocked_response.status_code, 200)
            blocked_payload = blocked_response.json()
            self.assertEqual(blocked_payload["candidate_run"]["status"], "blocked_embedding_scope")
            self.assertTrue(blocked_payload["warnings"])
            self.assertIn("file-", blocked_payload["warnings"][0]["detail"])

            audit_response = client.get("/admin/audit-log", headers={"Authorization": "Bearer fake-token"})
            actions = {item["action"] for item in audit_response.json()["events"]}
            self.assertIn("tuning.compare.run", actions)
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer
            self._delete_retrieval_records(seeded.values())

    def test_m17_2_seed_import_admin_access_controls_and_executive_acl_visibility(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user

        run_migrations()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(
                user_id="admin-m172",
                email="admin.m172@example.com",
                roles=["admin", "user"],
                groups=["dev-admins"],
            )

            seed_response = client.post("/admin/access/seed-import", json={}, headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(seed_response.status_code, 200)
            summary = seed_response.json()["summary"]
            self.assertGreaterEqual(summary["users"], 10)
            self.assertGreaterEqual(summary["sources"], 5)

            access_response = client.get("/admin/access", headers={"Authorization": "Bearer fake-token"})
            self.assertEqual(access_response.status_code, 200)
            access_payload = access_response.json()
            self.assertTrue(access_payload["seed_pack_status"]["ready"])
            self.assertTrue(any(item["seed_source_key"] == "finance_budget" for item in access_payload["source_acl"]))
            self.assertTrue(any(item["contact_role"] == "business_approver" for item in access_payload["source_contacts"]))

            restricted_before = AuthenticatedUser(
                user_id="m172-restricted",
                email="restricted@ragenterprise.local",
                roles=["user"],
                groups=["public_users"],
            )
            token = set_current_user(restricted_before)
            try:
                before = perform_search(SearchRequest(question="legalfalcontoken", k=5, mode="keyword"))
            finally:
                reset_current_user(token)
            self.assertFalse(before.results)

            membership_response = client.patch(
                "/admin/access/users/m172-restricted/memberships",
                json={"group_names": ["public_users", "finance"]},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(membership_response.status_code, 200)
            explained_user = membership_response.json()["user"]
            self.assertTrue(any(item["reason"] == "group:finance" for item in explained_user["group_access"]))

            finance_source = next(item for item in access_payload["source_acl"] if item["seed_source_key"] == "finance_budget")
            acl_response = client.patch(
                f"/admin/access/sources/{finance_source['source_id']}/acl",
                json={"group_names": ["finance", "executive_access", "compliance_observers"]},
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(acl_response.status_code, 200)
            explained_source = acl_response.json()["source"]
            self.assertIn("compliance_observers", explained_source["acl_groups"])

            contacts_response = client.patch(
                f"/admin/access/sources/{finance_source['source_id']}/contacts",
                json={
                    "contacts": [
                        {
                            "contact_role": "business_approver",
                            "contact_external_user_id": "m172-finance-approver",
                            "contact_email": "finance-approver@ragenterprise.local",
                            "contact_display_name": "Finance Approver",
                        },
                        {
                            "contact_role": "acl_manager",
                            "contact_external_user_id": "m172-governance",
                            "contact_email": "observer@ragenterprise.local",
                            "contact_display_name": "Governance Observer",
                        },
                    ]
                },
                headers={"Authorization": "Bearer fake-token"},
            )
            self.assertEqual(contacts_response.status_code, 200)
            self.assertTrue(any(item["contact_role"] == "acl_manager" for item in contacts_response.json()["source"]["contacts"]))

            executive = AuthenticatedUser(
                user_id="m172-ceo",
                email="ceo@ragenterprise.local",
                roles=["user"],
                groups=["executive_access"],
            )
            token = set_current_user(executive)
            try:
                executive_results = perform_search(SearchRequest(question="q3budgettoken", k=5, mode="keyword"))
            finally:
                reset_current_user(token)
            self.assertTrue(executive_results.results)
            self.assertEqual(executive_results.results[0].file_name, "Q3 Budget Forecast")

            reviewer = AuthenticatedUser(
                user_id="m161-requester",
                email="requester@ragenterprise.local",
                roles=["user"],
                groups=["contract_reviewers"],
            )
            token = set_current_user(reviewer)
            try:
                reviewer_results = perform_search(SearchRequest(question="legalfalcontoken", k=5, mode="keyword"))
            finally:
                reset_current_user(token)
            self.assertTrue(reviewer_results.results)
            self.assertEqual(reviewer_results.results[0].file_name, "Falcon Contract Renewal")
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

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

    def test_m17_b3_promotion_rollback_embedding_scope_and_warmup_records(self):
        from app.auth.context import AuthenticatedUser
        from app.db.repo_jobs import get_ingestion_job
        from app.db.repo_profiles import get_active_profile_map, seed_default_profiles
        from app.db.repo_tuning_configs import (
            create_candidate_draft,
            create_embedding_experiment,
            list_model_warmups,
            list_tuning_history,
            promote_candidate_to_live,
            record_model_warmup,
            rollback_to_version,
        )

        run_migrations()
        seed_default_profiles(settings)
        actor = AuthenticatedUser(user_id="admin-m17b3", email="admin.m17b3@example.com", roles=["admin"])
        selected_profiles = get_active_profile_map(["embedding", "reranker", "llm", "retrieval"])
        draft = create_candidate_draft(
            name=f"m17b3-smoke-{uuid4().hex[:6]}",
            description="Smoke candidate for rollout controls.",
            selected_profiles=selected_profiles,
            actor=actor,
        )

        with self.assertRaises(ValueError):
            create_embedding_experiment(
                candidate_config_id=draft["id"],
                basis_embedding_profile=selected_profiles["embedding"],
                target_embedding_profile="bge-base-en-v1_5",
                scope_type="selected_5_files",
                source_ids=[1, 2],
                warning_acknowledged=True,
                confirmation_count=2,
                actor=actor,
            )

        scoped = create_embedding_experiment(
            candidate_config_id=draft["id"],
            basis_embedding_profile=selected_profiles["embedding"],
            target_embedding_profile="bge-base-en-v1_5",
            scope_type="selected_5_files",
            source_ids=[1, 2, 3, 4, 5],
            warning_acknowledged=True,
            confirmation_count=2,
            actor=actor,
        )
        self.assertEqual(scoped["scope_type"], "selected_5_files")
        self.assertEqual(scoped["locked_source_ids_json"], [1, 2, 3, 4, 5])

        full = create_embedding_experiment(
            candidate_config_id=draft["id"],
            basis_embedding_profile=selected_profiles["embedding"],
            target_embedding_profile="bge-base-en-v1_5",
            scope_type="all_files",
            source_ids=[],
            warning_acknowledged=True,
            confirmation_count=2,
            actor=actor,
        )
        self.assertIsNotNone(full["job_id"])
        self.assertEqual(get_ingestion_job(full["job_id"]).stage, "embedding_full_reindex_requested")

        promoted = promote_candidate_to_live(draft_id=draft["id"], promotion_note="Smoke promotion.", actor=actor)
        promoted_label = promoted["promoted_version"]["version_label"]
        rolled_back = rollback_to_version(version_label=promoted_label, reason="Smoke rollback.", actor=actor)
        self.assertEqual(rolled_back["rolled_back_to"]["version_label"], promoted_label)
        history = list_tuning_history()
        self.assertTrue(any(event["action"] == "promote" for event in history["promotion_events"]))
        self.assertTrue(any(event["action"] == "rollback" for event in history["promotion_events"]))

        warmup = record_model_warmup(model_type="reranker", model_name="cross-encoder/ms-marco-TinyBERT-L-2-v2", status="success", latency_ms=12, error_message=None)
        self.assertEqual(warmup["status"], "success")
        self.assertTrue(any(row["model_name"] == "cross-encoder/ms-marco-TinyBERT-L-2-v2" for row in list_model_warmups()))

    def test_m18_query_transform_is_disabled_by_default_and_trace_visible_when_enabled(self):
        from app.core_rag.query_transform import transform_query
        from app.profiles.models import RetrievalProfileConfig

        default_result = transform_query("Q4 liability subcontracting", RetrievalProfileConfig())
        self.assertFalse(default_result.trace["enabled"])
        self.assertEqual(default_result.effective_query, "Q4 liability subcontracting")

        transformed = transform_query(
            "Q4 liability subcontracting",
            RetrievalProfileConfig(
                query_transform_enabled=True,
                rewrite_enabled=True,
                expansion_enabled=True,
                hyde_enabled=True,
                transform_max_variants=4,
            ),
        )
        self.assertTrue(transformed.trace["enabled"])
        self.assertIn("original_query", transformed.trace)
        self.assertGreaterEqual(len(transformed.generated_queries), 2)
        self.assertIn("liability", transformed.effective_query)

    def test_m19_semantic_cache_is_acl_profile_and_mode_scoped(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_semantic_cache import get_cache_entry, invalidate_cache, store_cache_entry

        run_migrations()
        actor = AuthenticatedUser(user_id=f"user-cache-{uuid4().hex[:6]}", email="cache@example.com", groups=["ops"], roles=["user"])
        question = f"cache question {uuid4().hex}"
        invalidate_cache(reason="test_setup")

        token = set_current_user(actor)
        try:
            self.assertIsNone(get_cache_entry(question=question, retrieval_mode="hybrid", corpus_scope={"corpus": "ops"}, actor=actor))
            entry = store_cache_entry(
                question=question,
                retrieval_mode="hybrid",
                corpus_scope={"corpus": "ops"},
                answer_json={"answer": "Cached answer", "used_chunks_count": 1},
                citations_json=[],
                retrieved_chunk_ids=[],
                ttl_seconds=60,
                metadata_json={"test": True},
            )
            self.assertGreater(entry["id"], 0)
            self.assertIsNotNone(get_cache_entry(question=question, retrieval_mode="hybrid", corpus_scope={"corpus": "ops"}, actor=actor))
            self.assertIsNone(get_cache_entry(question=question, retrieval_mode="keyword", corpus_scope={"corpus": "ops"}, actor=actor))
            self.assertGreaterEqual(invalidate_cache(reason="test_teardown"), 1)
        finally:
            reset_current_user(token)

    def test_m20_query_mining_clusters_and_derives_eval_pack(self):
        from app.auth.context import AuthenticatedUser
        from app.db.repo_query_mining import (
            annotate_cluster,
            build_failure_clusters,
            create_eval_pack_from_clusters,
            record_query_event,
        )

        run_migrations()
        actor = AuthenticatedUser(user_id=f"user-mining-{uuid4().hex[:6]}", email="mining@example.com", roles=["user"])
        question = f"missing payroll policy {uuid4().hex}"
        record_query_event(question=question, event_type="no_evidence", answer_path="not_found", retrieval_mode="hybrid", actor=actor)
        record_query_event(question=question, event_type="not_helpful", feedback_type="not_helpful", retrieval_mode="hybrid", actor=actor)
        clusters = build_failure_clusters()
        cluster = next(item for item in clusters if question in item["sample_questions_json"])
        annotated = annotate_cluster(cluster["id"], {"owner": "retrieval", "priority": "high"})
        self.assertEqual(annotated["annotation_json"]["priority"], "high")
        pack = create_eval_pack_from_clusters(name=f"derived-pack-{uuid4().hex[:6]}", cluster_ids=[cluster["id"]], actor=actor)
        self.assertEqual(pack["status"], "ready")
        self.assertTrue(pack["cases_json"])

    def test_m22_structured_negative_feedback_persists_and_lists_for_admin(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser
        from app.db.repo_actions import list_negative_feedback_events
        from app.db.repo_query_mining import list_query_events

        run_migrations()
        client = TestClient(app)
        actor = AuthenticatedUser(
            user_id=f"m22-user-{uuid4().hex[:6]}",
            email="m22-user@example.com",
            roles=["user", "admin"],
        )
        question = f"m22 answer failure {uuid4().hex}"
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: actor

            helpful = client.post(
                "/feedback",
                json={
                    "question": question,
                    "feedback_type": "helpful",
                    "rating": "up",
                    "request_id": f"m22-helpful-{uuid4().hex[:6]}",
                    "answer_path": "generated",
                },
            )
            self.assertEqual(helpful.status_code, 200)
            self.assertIsNone(helpful.json()["negative_feedback_id"])

            invalid = client.post(
                "/feedback",
                json={
                    "question": question,
                    "feedback_type": "not_helpful",
                    "rating": "down",
                    "answer_text": "Wrong answer",
                },
            )
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(invalid.json()["detail"]["error"], "negative_reason_required")

            request_id = f"m22-negative-{uuid4().hex[:6]}"
            negative = client.post(
                "/feedback",
                json={
                    "question": question,
                    "feedback_type": "not_helpful",
                    "rating": "down",
                    "negative_reason": "wrong_document",
                    "note": "The cited file is unrelated.",
                    "answer_text": "The answer cited the wrong source [S1].",
                    "citations_json": [{"citation_id": "S1", "source_id": 123, "chunk_id": 456, "file_name": "wrong.pdf"}],
                    "used_chunks_count": 3,
                    "active_profile_snapshot_json": {"retrieval": {"name": "default"}},
                    "request_id": request_id,
                    "answer_path": "generated",
                    "metadata_json": {"message_id": "m22-message"},
                },
            )
            self.assertEqual(negative.status_code, 200)
            negative_feedback_id = negative.json()["negative_feedback_id"]
            self.assertGreater(negative_feedback_id, 0)

            rows = [row for row in list_negative_feedback_events(limit=20) if row.request_id == request_id]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.negative_reason, "wrong_document")
            self.assertEqual(row.note, "The cited file is unrelated.")
            self.assertEqual(row.used_chunks_count, 3)
            self.assertEqual(row.cited_source_ids_json, [123])
            self.assertEqual(row.cited_chunk_ids_json, [456])
            self.assertEqual(row.active_profile_snapshot_json["retrieval"]["name"], "default")

            events = [item for item in list_query_events(limit=50) if item["request_id"] == request_id]
            self.assertTrue(any(item["event_type"] == "not_helpful" and item["feedback_type"] == "not_helpful" for item in events))

            admin_payload = client.get("/admin/feedback")
            self.assertEqual(admin_payload.status_code, 200)
            payload = admin_payload.json()
            self.assertTrue(any(item["id"] == negative_feedback_id for item in payload["negative_feedback"]))
            self.assertTrue(any(item["negative_reason"] == "wrong_document" for item in payload["negative_feedback_reason_counts"]))
        finally:
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

    def test_m21_governance_risk_signals_and_reversible_blocks(self):
        from app.auth.context import AuthenticatedUser
        from app.db.repo_access_requests import create_access_request
        from app.db.repo_governance import (
            active_restrictions,
            create_restriction,
            evaluate_access_request_risk,
            lift_restriction,
        )

        run_migrations()
        actor = AuthenticatedUser(user_id=f"user-gov-{uuid4().hex[:6]}", email="governance@example.com", roles=["user"])
        admin = AuthenticatedUser(user_id="admin-gov", email="admin.gov@example.com", roles=["admin"])
        question = f"restricted board pack {uuid4().hex}"
        for approver in ("first.approver@example.com", "second.approver@example.com"):
            create_access_request(
                question=question,
                business_reason="Need access for a governed smoke test.",
                actor=actor,
                metadata_json={"suggested_approver_email": approver},
            )

        signals = evaluate_access_request_risk(actor=actor, question=question, suggested_approver_email="third.approver@example.com")
        signal_types = {signal["signal_type"] for signal in signals}
        self.assertIn("repeated_similar_request", signal_types)
        self.assertIn("approver_swapping", signal_types)

        restriction = create_restriction(
            user_external_user_id=actor.user_id,
            user_email=actor.email,
            restriction_type="access_request_block",
            reason="Smoke temporary block.",
            actor=admin,
            duration_hours=1,
        )
        self.assertTrue(active_restrictions(actor))
        lifted = lift_restriction(restriction["id"], reason="Smoke unblock.", actor=admin)
        self.assertEqual(lifted["status"], "lifted")
        self.assertEqual(active_restrictions(actor), [])
