from tests.smoke_test_base import *


class SmokeTestBaseline(SmokeTestBase):
    def test_m16_1_access_request_route_approve_and_grant_enables_retrieval(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_acl import assign_document_acl, sync_authenticated_user
        from app.db.repo_access_requests import (
            create_access_request,
            decide_inbox_item,
            grant_access_request,
            list_inbox_items,
            route_access_request,
        )

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
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
                    "file_name": f"m16-1-{suffix}.pdf",
                    "storage_path": f"tests/m16-1-{suffix}.pdf",
                    "hash_sha256": (suffix + "m16") * 4,
                    "metadata": json.dumps({"corpus": "legal"}),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Protected contract",
                    "section_path": "page:1",
                    "chunk_text": "contracttokenm161 protected answer text",
                    "token_count": 4,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m16_1"},
                }
            ],
        )
        self.addCleanup(self._delete_retrieval_records, [source_id])
        with engine.connect() as conn:
            chunk_id = conn.execute(text("SELECT id FROM chunks WHERE source_id = :source_id"), {"source_id": source_id}).scalar_one()
        update_chunk_embeddings([(chunk_id, basis_vector(1.0))])
        assign_document_acl(source_id=source_id, group_names=["legal-team"])

        requester = AuthenticatedUser(user_id=f"m161-user-{suffix}", email=f"m161-user-{suffix}@example.test", roles=["user"], groups=[])
        admin = AuthenticatedUser(user_id=f"m161-admin-{suffix}", email=f"m161-admin-{suffix}@example.test", roles=["admin", "user"], groups=["legal-admins"])
        approver = AuthenticatedUser(user_id=f"m161-approver-{suffix}", email=f"m161-approver-{suffix}@example.test", roles=["approver", "user"], groups=[])
        for actor in (requester, admin, approver):
            sync_authenticated_user(actor)

        token = set_current_user(requester)
        try:
            # Scope to this test's source: the shared dev DB may contain stale
            # leftovers from earlier aborted runs that also match the token.
            before = perform_search(
                SearchRequest(question="contracttokenm161", k=5, mode="keyword", filters=SearchFilters(source_id=source_id))
            )
            request_row = create_access_request(
                question="Need the protected contract terms",
                business_reason="Need temporary access for case review",
                source_hint="Protected contract",
                request_id=f"m16-1-{suffix}",
                answer_path="not_found",
                actor=requester,
                metadata_json={"test": True},
            )
        finally:
            reset_current_user(token)

        self.assertFalse(before.results)

        token = set_current_user(admin)
        try:
            routed = route_access_request(
                access_request_id=request_row.id,
                source_ids=[source_id],
                admin_actor=admin,
                business_approver={
                    "contact_external_user_id": approver.user_id,
                    "contact_email": approver.email,
                    "contact_display_name": "Approver",
                },
                acl_manager=None,
                requester_manager=None,
                review_reason="Route to source owner",
            )
        finally:
            reset_current_user(token)
        self.assertEqual(routed.status, "awaiting_business_approval")

        token = set_current_user(approver)
        try:
            inbox_items = list_inbox_items(actor=approver)
            self.assertTrue(inbox_items)
            approved = decide_inbox_item(
                inbox_item_id=inbox_items[0].id,
                actor=approver,
                decision="approve_24h",
                decision_reason="Approve temporary review access",
            )
        finally:
            reset_current_user(token)
        self.assertEqual(approved.status, "business_approved")
        self.assertEqual(approved.approved_duration_hours, 24)

        token = set_current_user(admin)
        try:
            granted = grant_access_request(access_request_id=request_row.id, actor=admin)
        finally:
            reset_current_user(token)
        self.assertEqual(granted.status, "grant_completed")
        self.assertIsNotNone(granted.expires_at)

        token = set_current_user(requester)
        try:
            after = perform_search(
                SearchRequest(question="contracttokenm161", k=5, mode="keyword", filters=SearchFilters(source_id=source_id))
            )
        finally:
            reset_current_user(token)

        self.assertTrue(after.results)
        self.assertEqual(after.results[0].source_id, source_id)

    def test_m16_1_clarification_marks_access_limited_no_answer_without_leak(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_acl import assign_document_acl, sync_authenticated_user
        from app.core_rag.answering import perform_ask

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
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
                    "file_name": f"hidden-{suffix}.pdf",
                    "storage_path": f"tests/hidden-{suffix}.pdf",
                    "hash_sha256": (suffix + "hidden") * 4,
                    "metadata": json.dumps({"corpus": "legal"}),
                },
            ).scalar_one()
        assign_document_acl(source_id=source_id, group_names=["finance"])

        requester = AuthenticatedUser(user_id=f"m161-clarify-{suffix}", email=f"m161-clarify-{suffix}@example.test", roles=["user"], groups=[])
        sync_authenticated_user(requester)
        token = set_current_user(requester)
        try:
            response = perform_ask(
                AskRequest(
                    question="Find the latest contract terms",
                    mode="keyword",
                    filters=SearchFilters(source_id=source_id),
                    dry_run=False,
                )
            )
        finally:
            reset_current_user(token)
            self._delete_retrieval_records([source_id])

        clarification = response.debug_info["clarification"]
        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertTrue(clarification["access_limited_possible"])
        self.assertTrue(clarification["request_access_supported"])
        self.assertNotIn("hidden-", str(clarification))

    def test_m16_1_route_without_source_ids_and_approver_maps_sources_on_approval(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_acl import assign_document_acl, sync_authenticated_user
        from app.db.repo_access_requests import (
            create_access_request,
            decide_inbox_item,
            get_access_request,
            grant_access_request,
            list_access_request_targets,
            list_inbox_items,
            route_access_request,
        )

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
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
                    "file_name": f"m16-1-sourcefree-{suffix}.pdf",
                    "storage_path": f"tests/m16-1-sourcefree-{suffix}.pdf",
                    "hash_sha256": (suffix + "srcfree") * 4,
                    "metadata": json.dumps({"corpus": "legal"}),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Protected contract",
                    "section_path": "page:1",
                    "chunk_text": "contracttokenm161sourcefree protected answer text",
                    "token_count": 4,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m16_1_sourcefree"},
                }
            ],
        )
        with engine.connect() as conn:
            chunk_id = conn.execute(text("SELECT id FROM chunks WHERE source_id = :source_id"), {"source_id": source_id}).scalar_one()
        update_chunk_embeddings([(chunk_id, basis_vector(1.0))])
        assign_document_acl(source_id=source_id, group_names=["legal-team"])

        requester = AuthenticatedUser(user_id=f"m161-requester-{suffix}", email=f"m161-requester-{suffix}@example.test", roles=["user"], groups=[])
        admin = AuthenticatedUser(user_id=f"m161-admin-{suffix}", email=f"m161-admin-{suffix}@example.test", roles=["admin", "user"], groups=["legal-admins"])
        approver = AuthenticatedUser(user_id=f"m161-approver-{suffix}", email=f"m161-approver-{suffix}@example.test", roles=["approver", "user"], groups=[])
        for actor in (requester, admin, approver):
            sync_authenticated_user(actor)

        request_row = create_access_request(
            question="Need the protected contract terms",
            business_reason="Need temporary access for contract review",
            source_hint=None,
            request_id=f"m16-1-sourcefree-{suffix}",
            answer_path="not_found",
            actor=requester,
            metadata_json={"suggested_approver_email": approver.email},
        )

        routed = route_access_request(
            access_request_id=request_row.id,
            source_ids=[],
            admin_actor=admin,
            business_approver={
                "contact_external_user_id": approver.user_id,
                "contact_email": approver.email,
                "contact_display_name": "Approver",
            },
            acl_manager=None,
            requester_manager=None,
            review_reason="Route without exact source id; approver will map source.",
        )
        self.assertEqual(routed.status, "awaiting_business_approval")
        self.assertEqual(list_access_request_targets(request_row.id), [])

        token = set_current_user(approver)
        try:
            inbox_items = list_inbox_items(actor=approver)
            approved = decide_inbox_item(
                inbox_item_id=inbox_items[0].id,
                actor=approver,
                decision="approve_24h",
                decision_reason="Approver mapped the correct protected source.",
                selected_source_ids=[source_id],
            )
        finally:
            reset_current_user(token)

        self.assertEqual(approved.status, "business_approved")
        self.assertEqual([target.source_id for target in list_access_request_targets(request_row.id)], [source_id])

        granted = grant_access_request(access_request_id=request_row.id, actor=admin)
        self.assertEqual(granted.status, "grant_completed")

        token = set_current_user(requester)
        try:
            after = perform_search(SearchRequest(question="contracttokenm161sourcefree", k=5, mode="keyword"))
        finally:
            reset_current_user(token)
        self.assertTrue(after.results)
        self.assertEqual(after.results[0].source_id, source_id)
        self._delete_retrieval_records([source_id])

    def test_m16_1_approver_can_return_request_with_alternate_approver_suggestion(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_acl import sync_authenticated_user
        from app.db.repo_access_requests import create_access_request, decide_inbox_item, get_access_request, list_inbox_items, route_access_request

        suffix = uuid4().hex[:8]
        requester = AuthenticatedUser(user_id=f"m161-requester-reroute-{suffix}", email=f"requester-reroute-{suffix}@example.test", roles=["user"], groups=[])
        admin = AuthenticatedUser(user_id=f"m161-admin-reroute-{suffix}", email=f"admin-reroute-{suffix}@example.test", roles=["admin", "user"], groups=["legal-admins"])
        wrong_approver = AuthenticatedUser(user_id=f"m161-wrong-{suffix}", email=f"wrong-{suffix}@example.test", roles=["approver", "user"], groups=[])
        for actor in (requester, admin, wrong_approver):
            sync_authenticated_user(actor)

        request_row = create_access_request(
            question="Need access to the Falcon contract",
            business_reason="Need temporary access for a contract review",
            source_hint="Falcon contract",
            request_id=f"m16-1-reroute-{suffix}",
            answer_path="not_found",
            actor=requester,
            metadata_json={"suggested_approver_email": wrong_approver.email},
        )
        routed = route_access_request(
            access_request_id=request_row.id,
            source_ids=[],
            admin_actor=admin,
            business_approver={
                "contact_external_user_id": wrong_approver.user_id,
                "contact_email": wrong_approver.email,
                "contact_display_name": "Wrong Approver",
            },
            acl_manager=None,
            requester_manager=None,
            review_reason="Initial route based on requester suggestion.",
        )
        self.assertEqual(routed.status, "awaiting_business_approval")

        token = set_current_user(wrong_approver)
        try:
            inbox_items = list_inbox_items(actor=wrong_approver)
            returned = decide_inbox_item(
                inbox_item_id=inbox_items[0].id,
                actor=wrong_approver,
                decision="return_reroute",
                decision_reason="Not the real owner. Route to legal owner instead.",
                alternate_business_approver={
                    "contact_email": f"legal-owner-{suffix}@example.test",
                    "contact_display_name": "Legal Owner",
                },
            )
        finally:
            reset_current_user(token)

        self.assertEqual(returned.status, "triaged")
        refreshed = get_access_request(request_row.id)
        self.assertEqual(refreshed.business_approval_status, "returned")
        self.assertEqual((refreshed.metadata_json.get("approver_return") or {}).get("decision"), "return_reroute")
        self.assertEqual(
            ((refreshed.metadata_json.get("approver_return") or {}).get("alternate_business_approver") or {}).get("contact_email"),
            f"legal-owner-{suffix}@example.test",
        )

    def test_m16_1_create_access_request_accepts_contact_shaped_requester_manager(self):
        from app.auth.context import AuthenticatedUser
        from app.db.repo_acl import sync_authenticated_user
        from app.db.repo_access_requests import create_access_request

        suffix = uuid4().hex[:8]
        requester = AuthenticatedUser(
            user_id=f"m161-requester-manager-{suffix}",
            email=f"requester-manager-{suffix}@example.test",
            roles=["user"],
            groups=[],
        )
        sync_authenticated_user(requester)

        row = create_access_request(
            question="Need access to protected legal material",
            business_reason="Required for project delivery",
            source_hint="Falcon contract",
            request_id=f"m16-1-manager-{suffix}",
            answer_path="not_found",
            actor=requester,
            requester_manager={
                "contact_email": f"manager-{suffix}@example.test",
                "contact_display_name": "Line Manager",
            },
            metadata_json={"test": "requester_manager_contact_shape"},
        )

        self.assertEqual(row.requester_manager_email, f"manager-{suffix}@example.test")
        self.assertEqual(row.requester_manager_display_name, "Line Manager")

    def test_m14_tool_policy_allows_and_denies_with_audit_rows(self):
        from app.api.actions import ToolInvokeRequest, invoke_tool
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_actions import list_tool_invocations

        suffix = uuid4().hex[:8]
        user = AuthenticatedUser(user_id=f"m14-user-{suffix}", email=f"m14-{suffix}@example.test", roles=["user"], groups=[])
        token = set_current_user(user)
        try:
            denied = invoke_tool(ToolInvokeRequest(tool_name="send_email", corpus_name="legal", payload={"to": "a@example.test"}), user)
            allowed = invoke_tool(ToolInvokeRequest(tool_name="generate_report", corpus_name="legal", payload={"artifact_type": "csv"}), user)
        finally:
            reset_current_user(token)

        self.assertEqual(denied.status, "denied")
        self.assertEqual(denied.denial_reason, "role_not_allowed")
        self.assertEqual(allowed.status, "completed")
        rows = list_tool_invocations(limit=10)
        self.assertTrue(any(row.id == denied.invocation_id and row.status == "denied" for row in rows))
        self.assertTrue(any(row.id == allowed.invocation_id and row.status == "completed" for row in rows))

    def test_m15_sensitive_answer_is_held_for_approval(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.core_rag import answering as answering_module
        from app.core_rag.answering import AskRequest
        from app.core_rag.retrieval import SearchResponse, SearchResultItem
        from app.db.repo_actions import get_approval_request

        suffix = uuid4().hex[:8]
        user = AuthenticatedUser(user_id=f"m15-user-{suffix}", email=f"m15-{suffix}@example.test", roles=["user"], groups=[])
        token = set_current_user(user)
        original_search = answering_module.perform_search
        original_generate = answering_module.generate_answer
        answering_module.perform_search = lambda request: SearchResponse(
            results=[
                SearchResultItem(
                    chunk_id=1,
                    source_id=1,
                    source_part_id=None,
                    file_name="hr.txt",
                    source_type="txt",
                    heading="HR",
                    locator=None,
                    snippet="Salary data exists.",
                    score=1.0,
                )
            ],
            latency_ms=1,
            mode="hybrid",
            debug_info={"request_id": f"m15-{suffix}"},
        )
        answering_module.generate_answer = lambda system, user: {"success": True, "content": '{"answer":"Salary is supported [S1]","citations":["S1"]}'}
        try:
            response = answering_module.perform_ask(AskRequest(question="What is the salary?", mode="hybrid"))
        finally:
            answering_module.perform_search = original_search
            answering_module.generate_answer = original_generate
            reset_current_user(token)

        approval = response.debug_info["approval"]
        self.assertIn("pending human approval", response.answer)
        self.assertEqual(response.citations, [])
        self.assertEqual(get_approval_request(approval["approval_id"]).status, "pending")

    def test_m16_missing_evidence_records_feedback_and_clarification_contract(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.core_rag import answering as answering_module
        from app.core_rag.answering import AskRequest
        from app.core_rag.retrieval import SearchResponse
        from app.db.repo_actions import list_query_feedback

        suffix = uuid4().hex[:8]
        user = AuthenticatedUser(user_id=f"m16-user-{suffix}", email=f"m16-{suffix}@example.test", roles=["user"], groups=[])
        token = set_current_user(user)
        original_search = answering_module.perform_search
        answering_module.perform_search = lambda request: SearchResponse(
            results=[],
            latency_ms=1,
            mode="hybrid",
            debug_info={"request_id": f"m16-{suffix}"},
        )
        try:
            response = answering_module.perform_ask(AskRequest(question="Where is the latest renewal plan?", mode="hybrid"))
        finally:
            answering_module.perform_search = original_search
            reset_current_user(token)

        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertTrue(response.debug_info["clarification"]["missing_source_supported"])
        self.assertTrue(any(row.request_id == f"m16-{suffix}" and row.feedback_type == "missing_evidence" for row in list_query_feedback(limit=20)))

    def test_m12_db_row_serialization_preserves_filter_metadata(self):
        from app.connectors.db import serialize_db_row
        from app.db.repo_connectors import DbConnectorRow

        connector = DbConnectorRow(
            id=12,
            name="support cases",
            connector_type="postgres",
            db_url="postgresql://example",
            table_name="customer_cases",
            id_column="id",
            updated_at_column="updated_at",
            text_columns_json=["title", "body"],
            metadata_columns_json=["customer_id", "region"],
            corpus_name="db_rows",
            acl_group_names_json=["support"],
            status="configured",
            last_cursor_updated_at=None,
            last_cursor_id=None,
            last_run_at=None,
            last_error=None,
            connector_metadata_json={},
        )

        parsed = serialize_db_row(
            connector,
            {
                "id": 42,
                "updated_at": "2026-04-20T10:00:00Z",
                "title": "Renewal blocker",
                "body": "Acme needs the EU data-processing addendum.",
                "customer_id": "acme",
                "region": "eu",
            },
        )
        chunks = chunk_parsed_document(parsed, policy_name="db_rows")

        self.assertEqual(parsed.source_type, "db_row")
        self.assertEqual(parsed.metadata["customer_id"], "acme")
        self.assertEqual(chunks[0]["locator_json"]["region"], "eu")
        self.assertEqual(chunks[0]["provenance_json"]["parser_route"], "structured_row_serialization")
        self.assertIn("Renewal blocker", chunks[0]["chunk_text"])

    def test_m12_db_connector_ingests_queryable_acl_scoped_rows(self):
        from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
        from app.db.repo_acl import sync_authenticated_user
        from app.db.repo_connectors import upsert_db_connector
        import app.connectors.db as db_connector_module

        suffix = uuid4().hex[:8]
        table_name = f"m12_cases_{suffix}"
        connector_id = None
        source_ids: list[int] = []
        user = AuthenticatedUser(user_id=f"m12-user-{suffix}", email=f"m12-{suffix}@example.test", groups=["support"])
        token = set_current_user(user)
        original_process_embeddings = db_connector_module.process_embeddings
        original_run_enrichment = db_connector_module.run_post_ingestion_enrichment
        db_connector_module.process_embeddings = lambda *, force=False, source_id=None: {"chunks_embedded": 1}
        db_connector_module.run_post_ingestion_enrichment = lambda **kwargs: None
        try:
            sync_authenticated_user(user)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        CREATE TABLE {table_name} (
                            id INTEGER PRIMARY KEY,
                            updated_at TIMESTAMPTZ NOT NULL,
                            title TEXT NOT NULL,
                            body TEXT NOT NULL,
                            customer_id TEXT NOT NULL,
                            region TEXT NOT NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(f"INSERT INTO {table_name} (id, updated_at, title, body, customer_id, region) VALUES (1, now(), 'Renewal blocker', 'Acme needs contract support', 'acme', 'eu')")
                )
            connector_id = upsert_db_connector(
                name=f"m12-{suffix}",
                connector_type="postgres",
                db_url=settings.DATABASE_URL,
                table_name=table_name,
                id_column="id",
                updated_at_column="updated_at",
                text_columns=["title", "body"],
                metadata_columns=["customer_id", "region"],
                corpus_name="db_rows",
                acl_group_names=["support"],
            )

            result = db_connector_module.ingest_db_connector(connector_id, row_limit=10)
            source_ids = result["source_ids"]
            response = perform_search(
                SearchRequest(
                    question="contract support",
                    k=5,
                    mode="keyword",
                    filters=SearchFilters(source_id=source_ids[0], metadata_filters={"customer_id": "acme", "region": "eu"}),
                    debug=True,
                )
            )

            self.assertEqual(result["rows_ingested"], 1)
            self.assertTrue(response.results)
            self.assertEqual(response.debug_info["structured_filters"], {"customer_id": "acme", "region": "eu"})
            self.assertEqual(response.results[0].source_type, "db_row")
        finally:
            db_connector_module.process_embeddings = original_process_embeddings
            db_connector_module.run_post_ingestion_enrichment = original_run_enrichment
            reset_current_user(token)
            for source_id in source_ids:
                self._delete_seed_source(source_id)
            with engine.begin() as conn:
                if connector_id is not None:
                    conn.execute(text("DELETE FROM db_connectors WHERE id = :connector_id"), {"connector_id": connector_id})
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

    def test_m12_connector_requests_can_be_reviewed(self):
        from app.db.repo_connectors import create_connector_request, list_connector_requests, update_connector_request_review

        suffix = uuid4().hex[:8]
        request_id = create_connector_request(
            connector_type="database",
            requested_system=f"m12-request-{suffix}",
            business_reason="Need governed case search.",
            requested_scope_json={"tables": ["customer_cases"]},
            requester_external_user_id=f"requester-{suffix}",
            requester_email=f"requester-{suffix}@example.test",
            requester_display_name="Requester",
        )
        try:
            requests = list_connector_requests(requester_external_user_id=f"requester-{suffix}")
            self.assertEqual(requests[0].id, request_id)
            self.assertEqual(requests[0].status, "submitted")

            reviewed = update_connector_request_review(
                request_id=request_id,
                status="approved",
                review_reason="Approved for DB connector setup.",
                reviewed_by_external_user_id="admin",
                reviewed_by_email="admin@example.test",
            )
            self.assertIsNotNone(reviewed)
            self.assertEqual(reviewed.status, "approved")
            self.assertEqual(reviewed.review_reason, "Approved for DB connector setup.")
        finally:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM connector_requests WHERE id = :request_id"), {"request_id": request_id})

    def test_m9_transcript_policy_adds_speaker_and_time_metadata(self):
        from app.adapters.models import ParsedSourceDocument, ParsedSourcePart

        parsed = ParsedSourceDocument(
            source_type="txt",
            metadata={"corpus_policy": "transcripts"},
            parts=[
                ParsedSourcePart(
                    part_type="text_block",
                    part_index=0,
                    title="Transcript Segment",
                    locator_json={"section": "body"},
                    content_text=(
                        "00:01 Alice: We need to finalize the roadmap and budget.\n"
                        "00:15 Bob: Agreed, let's cover the rollout plan next."
                    ),
                )
            ],
        )

        chunks = chunk_parsed_document(parsed, policy_name="transcripts")

        self.assertEqual(chunks[0]["provenance_json"]["corpus_policy"], "transcripts")
        self.assertEqual(chunks[0]["provenance_json"]["parser_route"], "transcript_speaker_windowing")
        self.assertEqual(chunks[0]["locator_json"]["speaker"], "Alice")
        self.assertEqual(chunks[0]["locator_json"]["time_start"], "00:01")
        self.assertIn("Bob", chunks[0]["locator_json"]["speakers"])

    def test_m9_legal_corpus_defaults_to_keyword_when_mode_omitted(self):
        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', 'public', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m9-legal-{suffix}.pdf",
                    "storage_path": f"tests/m9-legal-{suffix}.pdf",
                    "hash_sha256": (suffix + "l") * 4,
                    "source_metadata_json": json.dumps({"corpus": "legal", "corpus_policy": "legal"}),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Legal Clause",
                    "section_path": "page:1",
                    "chunk_text": "termination clause survives and legal remedy applies",
                    "token_count": 7,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m9-legal"},
                }
            ],
        )
        try:
            response = perform_search(
                SearchRequest(
                    question="termination clause",
                    k=3,
                    filters=SearchFilters(source_id=source_id),
                    debug=True,
                )
            )
        finally:
            self._delete_seed_source(source_id)

        self.assertEqual(response.mode, "keyword")
        self.assertEqual(response.debug_info["corpus_policy"]["name"], "legal")
        self.assertTrue(response.results)
        self.assertEqual(response.results[0].heading, "Legal Clause")

    def test_m9_db_rows_structured_metadata_filters_trim_results(self):
        suffix = uuid4().hex[:8]
        import app.core_rag.retrieval as retrieval_module

        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'xlsx', 'public', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m9-rows-{suffix}.xlsx",
                    "storage_path": f"tests/m9-rows-{suffix}.xlsx",
                    "hash_sha256": (suffix + "d") * 4,
                    "source_metadata_json": json.dumps({"corpus": "db_rows", "corpus_policy": "db_rows"}),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Customer Rows",
                    "section_path": "sheet:Customers",
                    "chunk_text": "Customer Acme Corp active ARR 120000",
                    "token_count": 6,
                    "locator_json": {"sheet": "Customers", "range": "Customers!rows 1-2"},
                    "provenance_json": {"row_group": "customers"},
                },
                {
                    "chunk_index": 1,
                    "heading": "Invoice Rows",
                    "section_path": "sheet:Invoices",
                    "chunk_text": "Invoice INV-001 paid by Acme Corp",
                    "token_count": 6,
                    "locator_json": {"sheet": "Invoices", "range": "Invoices!rows 1-2"},
                    "provenance_json": {"row_group": "invoices"},
                },
            ],
        )
        with engine.connect() as conn:
            chunk_rows = conn.execute(
                text("SELECT id FROM chunks WHERE source_id = :source_id ORDER BY chunk_index ASC"),
                {"source_id": source_id},
            ).fetchall()
        update_chunk_embeddings([(row[0], basis_vector(1.0)) for row in chunk_rows])
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            response = perform_search(
                SearchRequest(
                    question="Acme Corp",
                    k=5,
                    filters=SearchFilters(
                        source_id=source_id,
                        metadata_filters={"sheet": "Customers"},
                    ),
                    debug=True,
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(source_id)

        self.assertEqual(response.debug_info["structured_filters"], {"sheet": "Customers"})
        self.assertTrue(response.results)
        self.assertEqual([item.heading for item in response.results], ["Customer Rows"])

    def test_m9_corpus_policy_eval_matrix(self):
        cases = json.loads((EVAL_FIXTURE_DIR / "corpus_policy_cases.json").read_text(encoding="utf-8"))
        suffix = uuid4().hex[:8]
        import app.core_rag.retrieval as retrieval_module

        with engine.begin() as conn:
            legal_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'pdf', 'public', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m9-legal-matrix-{suffix}.pdf",
                    "storage_path": f"tests/m9-legal-matrix-{suffix}.pdf",
                    "hash_sha256": (suffix + "a") * 4,
                    "source_metadata_json": json.dumps({"corpus": "legal", "corpus_policy": "legal"}),
                },
            ).scalar_one()
            transcript_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'txt', 'public', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m9-transcript-matrix-{suffix}.txt",
                    "storage_path": f"tests/m9-transcript-matrix-{suffix}.txt",
                    "hash_sha256": (suffix + "b") * 4,
                    "source_metadata_json": json.dumps({"corpus": "transcripts", "corpus_policy": "transcripts"}),
                },
            ).scalar_one()
            db_rows_source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'xlsx', 'public', :hash_sha256, 120,
                        'embedded', 'not_started', CAST(:source_metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m9-dbrows-matrix-{suffix}.xlsx",
                    "storage_path": f"tests/m9-dbrows-matrix-{suffix}.xlsx",
                    "hash_sha256": (suffix + "c") * 4,
                    "source_metadata_json": json.dumps({"corpus": "db_rows", "corpus_policy": "db_rows"}),
                },
            ).scalar_one()
        insert_chunks(
            legal_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Legal Clause",
                    "section_path": "page:1",
                    "chunk_text": "termination clause survives and legal remedy applies",
                    "token_count": 7,
                    "locator_json": {"page": 1},
                    "provenance_json": {"test": "m9-matrix"},
                }
            ],
        )
        insert_chunks(
            transcript_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Transcript Segment",
                    "section_path": "text:body",
                    "chunk_text": "00:01 Alice: We should ship the roadmap update this quarter.",
                    "token_count": 10,
                    "locator_json": {"section": "body", "speaker": "Alice", "time_start": "00:01"},
                    "provenance_json": {"test": "m9-matrix", "corpus_policy": "transcripts"},
                }
            ],
        )
        insert_chunks(
            db_rows_source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": "Customer Rows",
                    "section_path": "sheet:Customers",
                    "chunk_text": "Customer Acme Corp active ARR 120000",
                    "token_count": 6,
                    "locator_json": {"sheet": "Customers", "range": "Customers!rows 1-2"},
                    "provenance_json": {"test": "m9-matrix", "row_group": "customers"},
                }
            ],
        )
        update_chunk_embeddings(
            [
                (self._chunk_id_for_source(transcript_source_id), basis_vector(1.0)),
                (self._chunk_id_for_source(db_rows_source_id), basis_vector(1.0)),
            ]
        )
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            source_ids = {
                "legal": legal_source_id,
                "transcripts": transcript_source_id,
                "db_rows": db_rows_source_id,
            }
            observed = []
            for case in cases:
                response = perform_search(
                    SearchRequest(
                        question=case["question"],
                        k=3,
                        filters=SearchFilters(
                            source_id=source_ids[case["policy"]],
                            metadata_filters=case.get("metadata_filters"),
                        ),
                    )
                )
                observed.append((case["id"], response.mode, response.results[0].heading if response.results else None))
                self.assertEqual(response.mode, case["expected_mode"], case["id"])
                self.assertEqual(response.results[0].heading if response.results else None, case["expected_heading"], case["id"])
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_seed_source(legal_source_id)
            self._delete_seed_source(transcript_source_id)
            self._delete_seed_source(db_rows_source_id)

        self.assertEqual(len(observed), 3)

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
        self.assertTrue(SECOND_PASS_PROMPT)

        second_pass_prompt = generate_second_pass_prompt(
            question="What is this?",
            context_blocks=[
                {
                    "citation_id": "S1",
                    "file_name": "example.pdf",
                    "source_type": "pdf",
                    "heading": "Intro",
                    "locator": "page=1",
                    "snippet": "Snippet text",
                }
            ],
            prior_answer="fragment [S1]",
            fallback_reason="answer_too_short",
        )
        self.assertIn("PRIOR ANSWER TO REPAIR", second_pass_prompt)
        self.assertIn("REPAIR REASON: answer_too_short", second_pass_prompt)

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
        self.assertTrue(callable(generate_second_pass_prompt))
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
        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0]["locator_json"]["page"], 1)
        self.assertEqual(chunks[1]["locator_json"]["page"], 2)
        self.assertIn("Page One Text", chunks[0]["chunk_text"])
        self.assertIn("page:1", chunks[0]["section_path"])
        stitched = [chunk for chunk in chunks if chunk["provenance_json"].get("chunk_strategy") == "pdf_cross_page"]
        self.assertTrue(stitched)
        self.assertEqual(stitched[0]["locator_json"]["pages"], [1, 2])

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
                self.assertGreaterEqual(result["chunk_count"], 3)
            finally:
                jobs_module.REPO_ROOT = original_root

    def test_deep_research_trace_reports_anchor_scan_details_for_source_scoped_query(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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

        self.assertTrue(response.debug_info["source_scoped_scan_used"])
        self.assertEqual(response.debug_info["source_scoped_scan_reason"], "ok")
        self.assertIn(str(seeded["source_id"]), response.debug_info["anchor_frequency_by_source"])
        self.assertTrue(response.debug_info["rare_anchor_candidates"])
        self.assertGreaterEqual(response.debug_info["window_candidates_added"], 1)
        self.assertTrue(response.debug_info["window_debug"])

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
        self.assertTrue(checks["db_connectors table exists"])

    def test_migration_plan_exposes_ordered_patch_steps(self):
        from app.db.migrate import describe_migration_plan

        plan = describe_migration_plan()
        self.assertEqual(
            [item["step_id"] for item in plan],
            [
                "MIG-P001",
                "MIG-P002",
                "MIG-P003",
                "MIG-P004",
                "MIG-P005",
                "MIG-P006",
                "MIG-P007",
                "MIG-P008",
                "MIG-P009",
                "MIG-P010",
                "MIG-P011",
                "MIG-P012",
                "MIG-P013",
                "MIG-P014",
                "MIG-P015",
                "MIG-P016",
                "MIG-P017",
                "MIG-P018",
                "MIG-P019",
                "MIG-P020",
            ],
        )
        self.assertTrue(all(item["description"] for item in plan))

    def test_synthetic_vectors_match_live_embedding_dimension(self):
        # AR1: the harness must derive vector dimension from the live DB column,
        # never hardcode a model's dimension (audit: 55 errors from 384 vs 768).
        from tests.smoke_test_base import basis_vector, expected_vector_dim

        dim = expected_vector_dim()
        self.assertGreater(dim, 0)
        self.assertEqual(len(basis_vector(1.0)), dim)
        self.assertEqual(len(basis_vector(0.0, 1.0)), dim)
        source_id = self._seed_chunk_records()
        try:
            chunk_id = self._chunk_id_for_source(source_id)
            update_chunk_embeddings([(chunk_id, basis_vector(1.0))])
        finally:
            self._delete_seed_source(source_id)

    def test_migration_ledger_matches_plan_after_migrations(self):
        # AR1: the DB ledger must record every applied plan step; drift between
        # ledger and plan (audit: P012 recorded vs P020 expected) must fail loudly.
        from app.db.migrate import describe_migration_plan, recorded_migration_steps, verify_migration_ledger

        run_migrations()
        plan_ids = [item["step_id"] for item in describe_migration_plan()]
        self.assertEqual(recorded_migration_steps(), sorted(plan_ids))
        report = verify_migration_ledger()
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["unknown"], [])

    def test_vector_mode_returns_embedded_chunk_match(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            response = perform_search(SearchRequest(question="keywordbanana alpha", k=5, mode="hybrid", debug=True))
        finally:
            retrieval_module.embed_texts = original_embed_texts
            self._delete_retrieval_records(seeded.values())

        self.assertGreaterEqual(len(response.results), 2)
        self.assertEqual(response.mode, "hybrid")
        self.assertTrue(all(result.combined_score is not None for result in response.results[:2]))

    def test_m6_rrf_fusion_promotes_balanced_hits_and_emits_score_details(self):
        from app.core_rag.retrieval import _build_score_diagnostics, merge_hybrid_results

        vector_results = [
            {
                "chunk_id": 101,
                "source_id": 1,
                "source_part_id": None,
                "file_name": "fusion-a.pdf",
                "source_type": "pdf",
                "heading": "Vector First",
                "locator": "page=1",
                "snippet": "vector dominant hit",
                "distance": 0.0,
                "chunk_index": 0,
            },
            {
                "chunk_id": 103,
                "source_id": 1,
                "source_part_id": None,
                "file_name": "fusion-c.pdf",
                "source_type": "pdf",
                "heading": "Balanced Hit",
                "locator": "page=2",
                "snippet": "balanced hit",
                "distance": 0.6,
                "chunk_index": 1,
            },
        ]
        keyword_results = [
            {
                "chunk_id": 102,
                "source_id": 1,
                "source_part_id": None,
                "file_name": "fusion-b.pdf",
                "source_type": "pdf",
                "heading": "Keyword First",
                "locator": "page=3",
                "snippet": "keyword dominant hit",
                "rank_score": 100.0,
                "chunk_index": 2,
            },
            {
                "chunk_id": 103,
                "source_id": 1,
                "source_part_id": None,
                "file_name": "fusion-c.pdf",
                "source_type": "pdf",
                "heading": "Balanced Hit",
                "locator": "page=2",
                "snippet": "balanced hit",
                "rank_score": 40.0,
                "chunk_index": 1,
            },
        ]

        linear = merge_hybrid_results(vector_results=vector_results, keyword_results=keyword_results, k=3, alpha=0.65)
        rrf = merge_hybrid_results(
            vector_results=vector_results,
            keyword_results=keyword_results,
            k=3,
            alpha=0.65,
            fusion_method="rrf",
            rrf_k=60,
        )
        diagnostics = _build_score_diagnostics(rrf)

        self.assertEqual(linear[0]["chunk_id"], 101)
        self.assertEqual(rrf[0]["chunk_id"], 103)
        self.assertEqual(diagnostics[0]["fusion_method"], "rrf")
        self.assertEqual(diagnostics[0]["vector_rank"], 2)
        self.assertEqual(diagnostics[0]["keyword_rank"], 2)
        self.assertIsNotNone(diagnostics[0]["fusion_rrf_score"])


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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
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

    def test_answering_recovers_inline_citations_when_citation_array_is_empty(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module
        import app.core_rag.answering as answering_module

        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
        answering_module.generate_answer = lambda system_prompt, user_prompt: {
            "success": True,
            "content": json.dumps(
                {
                    "answer": "The market is saturated and large aggregators dominate search results, making it difficult for a newcomer to rank [S1].",
                    "citations": [],
                }
            ),
        }
        try:
            response = answering_module.perform_ask(
                AskRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k_chunks=3,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer
            self._delete_seed_source(seeded["source_id"])

        self.assertIn("aggregators", response.answer.lower())
        self.assertTrue(response.citations)

    def test_answering_uses_second_pass_repair_for_fragmented_initial_answer(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module
        import app.core_rag.answering as answering_module

        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        calls = []

        def fake_generate_answer(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                return {
                    "success": True,
                    "content": json.dumps(
                        {
                            "answer": "large aggregators dominate search [S1]",
                            "citations": ["S1"],
                        }
                    ),
                }
            return {
                "success": True,
                "content": json.dumps(
                    {
                        "answer": "Large aggregators dominate search visibility, which makes it difficult for a newcomer to rank through SEO [S1].",
                        "citations": ["S1"],
                    }
                ),
            }

        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
        answering_module.generate_answer = fake_generate_answer
        try:
            response = answering_module.perform_ask(
                AskRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k_chunks=3,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer
            self._delete_seed_source(seeded["source_id"])

        self.assertEqual(len(calls), 2)
        self.assertIn("repairing a grounded answer", calls[1][0].lower())
        self.assertIn("difficult for a newcomer", response.answer.lower())
        self.assertEqual(response.debug_info["answer_generation_path"], "repair")
        self.assertEqual(response.debug_info["fallback_reason"], "answer_starts_mid_sentence")

    def test_answering_returns_not_found_when_repair_cannot_produce_grounded_answer(self):
        seeded = self._seed_seo_anomaly_records()
        import app.core_rag.retrieval as retrieval_module
        import app.core_rag.answering as answering_module

        original_embed_texts = retrieval_module.embed_texts
        original_generate_answer = answering_module.generate_answer
        calls = []

        def fake_generate_answer(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                return {
                    "success": True,
                    "content": json.dumps(
                        {
                            "answer": "fragment [S1]",
                            "citations": ["S1"],
                        }
                    ),
                }
            return {
                "success": True,
                "content": json.dumps(
                    {
                        "answer": "still fragment [S1]",
                        "citations": ["S1"],
                    }
                ),
            }

        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0, 0.0) for _ in texts]
        answering_module.generate_answer = fake_generate_answer
        try:
            response = answering_module.perform_ask(
                AskRequest(
                    question="Why is it hard for a newcomer to enter this space through SEO?",
                    k_chunks=3,
                    mode="hybrid",
                    filters=SearchFilters(source_id=seeded["source_id"]),
                )
            )
        finally:
            retrieval_module.embed_texts = original_embed_texts
            answering_module.generate_answer = original_generate_answer
            self._delete_seed_source(seeded["source_id"])

        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertEqual(response.citations, [])
        self.assertEqual(response.debug_info["answer_generation_path"], "not_found")
        self.assertIn("repair_unsuitable", response.debug_info["fallback_reason"])

    def test_source_type_filter_works(self):
        seeded = self._seed_retrieval_records()
        import app.core_rag.retrieval as retrieval_module

        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
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
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
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

        from app.profiles.resolver import get_effective_llm

        effective_model = get_effective_llm().model

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"object": "list", "data": [{"id": effective_model}]}

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

    def test_m13_email_connector_record_normalizes_to_email_document(self):
        from app.connectors.email import EmailAttachmentRecord, EmailMessageRecord, parsed_document_from_email_record

        parsed = parsed_document_from_email_record(
            EmailMessageRecord(
                subject="Case escalation",
                body_text="Please review the renewal attachment.",
                from_email="sender@example.test",
                to_email="support@example.test",
                message_id="<m13@example.test>",
                mailbox="support",
                folder="Escalations",
                attachments=[
                    EmailAttachmentRecord(
                        file_name="notes.txt",
                        content_type="text/plain",
                        content_bytes=b"renewal attachment text",
                    )
                ],
            )
        )

        self.assertEqual(parsed.source_type, "email_message")
        self.assertEqual(parsed.metadata["source_kind"], "mailbox_archive")
        self.assertEqual(parsed.metadata["attachment_count"], 1)
        self.assertEqual(parsed.parts[0].locator_json["mailbox"], "support")
        self.assertEqual(parsed.attachments[0].content_bytes, b"renewal attachment text")

    def test_m13_ingestion_sanitizes_nul_text_before_persistence(self):
        from app.adapters import ParsedAttachment, ParsedSourceDocument, ParsedSourcePart
        from app.ingestion.jobs import _sanitize_parsed_document

        parsed = _sanitize_parsed_document(
            ParsedSourceDocument(
                source_type="pdf",
                title="Invoice\x00receipt",
                metadata={"invoice": "JQLBJNIL\x000002", "nested": ["2296\x001887"]},
                parts=[
                    ParsedSourcePart(
                        part_type="page",
                        part_index=0,
                        title="Page\x001",
                        locator_json={"label": "Page\x001"},
                        content_text="Invoice number JQLBJNIL\x000002",
                        provenance_json={"parser": "pdf\x00extractor"},
                    )
                ],
                attachments=[
                    ParsedAttachment(
                        file_name="receipt\x00.pdf",
                        content_type="application/pdf\x00",
                        content_bytes=b"raw\x00bytes remain raw",
                    )
                ],
                warnings=["warn\x00ing"],
            )
        )

        self.assertEqual(parsed.title, "Invoicereceipt")
        self.assertEqual(parsed.metadata["invoice"], "JQLBJNIL0002")
        self.assertEqual(parsed.metadata["nested"][0], "22961887")
        self.assertEqual(parsed.parts[0].content_text, "Invoice number JQLBJNIL0002")
        self.assertEqual(parsed.parts[0].locator_json["label"], "Page1")
        self.assertEqual(parsed.parts[0].provenance_json["parser"], "pdfextractor")
        self.assertEqual(parsed.attachments[0].file_name, "receipt.pdf")
        self.assertEqual(parsed.attachments[0].content_type, "application/pdf")
        self.assertEqual(parsed.attachments[0].content_bytes, b"raw\x00bytes remain raw")
        self.assertEqual(parsed.warnings[0], "warning")

    def test_m13_email_upload_creates_searchable_attachment_child_source(self):
        from email.message import EmailMessage
        import app.ingestion.jobs as jobs_module

        message = EmailMessage()
        message["From"] = "sender@example.test"
        message["To"] = "support@example.test"
        message["Subject"] = "Attachment case"
        message["Message-ID"] = f"<m13-{uuid4().hex}@example.test>"
        message.set_content("The attachment has the implementation details.")
        message.add_attachment("M13 child attachment searchable text.", subtype="plain", filename="m13-notes.txt")

        upload = UploadFile(
            filename=f"m13-{uuid4().hex[:8]}.eml",
            file=BytesIO(message.as_bytes()),
            headers={"content-type": "message/rfc822"},
        )
        original_process_embeddings = jobs_module.process_embeddings
        original_run_enrichment = jobs_module.run_post_ingestion_enrichment
        jobs_module.process_embeddings = lambda *, force=False, source_id=None: {"chunks_embedded": 99}
        jobs_module.run_post_ingestion_enrichment = lambda **kwargs: None
        result = None
        child_source_ids: list[int] = []
        try:
            result = asyncio.run(process_upload(upload))
            with engine.connect() as conn:
                attachment_rows = conn.execute(
                    text("SELECT child_source_id FROM attachments WHERE parent_source_id = :source_id"),
                    {"source_id": result["source_id"]},
                ).fetchall()
            self.assertEqual(len(attachment_rows), 1)
            child_source_ids = [int(row[0]) for row in attachment_rows]
            child_source = get_source_by_id(child_source_ids[0])
            self.assertIsNotNone(child_source)
            self.assertEqual(child_source.source_type, "txt")
            self.assertEqual(child_source.ingestion_status, "embedded")
        finally:
            jobs_module.process_embeddings = original_process_embeddings
            jobs_module.run_post_ingestion_enrichment = original_run_enrichment
            for child_source_id in child_source_ids:
                self._delete_seed_source(child_source_id)
            if result:
                self._delete_seed_source(result["source_id"])

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
