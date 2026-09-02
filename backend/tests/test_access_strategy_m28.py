import json
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

import app.main as main_module
from app.auth.access_strategy import clear_corpus_access_grants, grant_corpus_access
from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
from app.core.config import settings
from app.core_rag.retrieval import SearchRequest, perform_search
from app.db.db import engine
from app.db.migrate import run_migrations
from app.db.repo_acl import assign_document_acl, sync_authenticated_user
from app.db.repo_chunks import insert_chunks
from app.main import app




def setUpModule():
    """Skip this module when no database is reachable."""
    from tests.db_guard import require_database

    require_database()

class AccessStrategyM28Tests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "ACCESS_STRATEGY": settings.ACCESS_STRATEGY,
            "AUTH_MODE": settings.AUTH_MODE,
            "APP_ENV": settings.APP_ENV,
            "RATE_LIMIT_ENABLED": settings.RATE_LIMIT_ENABLED,
        }
        self.original_authenticate = main_module.authenticate_request
        self.original_sync = main_module.sync_authenticated_user
        self.created_source_ids: list[int] = []
        settings.RATE_LIMIT_ENABLED = False
        main_module.sync_authenticated_user = lambda user: None

    def tearDown(self):
        for source_id in self.created_source_ids:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM sources WHERE id = :source_id"), {"source_id": source_id})
        for key, value in self.original.items():
            setattr(settings, key, value)
        main_module.authenticate_request = self.original_authenticate
        main_module.sync_authenticated_user = self.original_sync

    def _seed_source(self, *, corpus: str, token_text: str, sensitivity_label: str = "internal") -> int:
        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256,
                        file_size_bytes, ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (
                        :file_name, :storage_path, 'db_row', :sensitivity_label, :hash_sha256,
                        100, 'embedded', 'not_started', CAST(:metadata AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "file_name": f"m28-{corpus}-{suffix}.txt",
                    "storage_path": f"tests/m28-{corpus}-{suffix}.txt",
                    "sensitivity_label": sensitivity_label,
                    "hash_sha256": (suffix + corpus)[:16] * 4,
                    "metadata": json.dumps({"corpus": corpus}),
                },
            ).scalar_one()
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": 0,
                    "heading": f"{corpus} heading",
                    "section_path": "m28",
                    "chunk_text": f"{token_text} secured scenario access text",
                    "token_count": 6,
                    "locator_json": {"row": 1},
                    "provenance_json": {"test": "m28"},
                }
            ],
        )
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO source_parts (source_id, part_type, part_index, title, content_text)
                    VALUES (:source_id, 'row', 0, 'row', :content_text)
                    ON CONFLICT (source_id, part_type, part_index) DO NOTHING
                    """
                ),
                {"source_id": source_id, "content_text": f"{token_text} file body"},
            )
        self.created_source_ids.append(source_id)
        return int(source_id)

    def test_none_strategy_allows_trusted_no_auth_research_retrieval(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "none"
        settings.AUTH_MODE = "none"
        source_id = self._seed_source(corpus="research", token_text="m28noneonly")

        response = perform_search(SearchRequest(question="m28noneonly", k=5, mode="keyword"))

        self.assertTrue(any(item.source_id == source_id for item in response.results))

    def test_employee_all_strategy_requires_authenticated_user_and_allows_all_sources(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "employee_all"
        settings.AUTH_MODE = "dev"
        source_id = self._seed_source(corpus="employees", token_text="m28employeeonly")

        no_user_response = perform_search(SearchRequest(question="m28employeeonly", k=5, mode="keyword"))
        self.assertFalse(any(item.source_id == source_id for item in no_user_response.results))

        actor = AuthenticatedUser(user_id="m28-employee", email="m28-employee@example.test", roles=["user"], groups=[])
        token = set_current_user(actor)
        try:
            user_response = perform_search(SearchRequest(question="m28employeeonly", k=5, mode="keyword"))
        finally:
            reset_current_user(token)

        self.assertTrue(any(item.source_id == source_id for item in user_response.results))

    def test_corpus_level_strategy_allows_only_granted_corpus_and_source_context(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "corpus_level"
        settings.AUTH_MODE = "dev"
        allowed_source = self._seed_source(corpus="finance-m28", token_text="m28financeonly")
        blocked_source = self._seed_source(corpus="legal-m28", token_text="m28legalonly")
        actor = AuthenticatedUser(user_id="m28-corpus-user", email="m28-corpus@example.test", roles=["user"], groups=["finance-team"])
        sync_authenticated_user(actor)
        clear_corpus_access_grants("finance-m28")
        grant_corpus_access(corpus_name="finance-m28", group_name="finance-team")

        token = set_current_user(actor)
        try:
            allowed = perform_search(SearchRequest(question="m28financeonly", k=5, mode="keyword"))
            blocked = perform_search(SearchRequest(question="m28legalonly", k=5, mode="keyword"))
            main_module.authenticate_request = lambda request: actor
            client = TestClient(app)
            list_response = client.get("/corpus", headers={"Authorization": "Bearer fake-token"})
            context_response = client.get(
                f"/corpus/{allowed_source}/chunks/{self._chunk_id_for_source(allowed_source)}/context",
                headers={"Authorization": "Bearer fake-token"},
            )
            blocked_context = client.get(
                f"/corpus/{blocked_source}/chunks/{self._chunk_id_for_source(blocked_source)}/context",
                headers={"Authorization": "Bearer fake-token"},
            )
        finally:
            reset_current_user(token)

        self.assertTrue(any(item.source_id == allowed_source for item in allowed.results))
        self.assertFalse(any(item.source_id == blocked_source for item in blocked.results))
        listed_ids = {item["id"] for item in list_response.json()}
        self.assertIn(allowed_source, listed_ids)
        self.assertNotIn(blocked_source, listed_ids)
        self.assertEqual(context_response.status_code, 200)
        self.assertEqual(blocked_context.status_code, 404)

    def test_document_acl_strategy_excludes_time_bound_direct_grants(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "document_acl"
        settings.AUTH_MODE = "dev"
        source_id = self._seed_source(corpus="direct-m28", token_text="m28directonly")
        actor = AuthenticatedUser(user_id="m28-direct-user", email="m28-direct@example.test", roles=["user"], groups=[])
        sync_authenticated_user(actor)
        self._grant_direct_source(source_id, actor)

        token = set_current_user(actor)
        try:
            response = perform_search(SearchRequest(question="m28directonly", k=5, mode="keyword"))
        finally:
            reset_current_user(token)

        self.assertFalse(any(item.source_id == source_id for item in response.results))

    def test_document_acl_with_time_bound_grants_preserves_existing_direct_grants(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"
        settings.AUTH_MODE = "dev"
        source_id = self._seed_source(corpus="direct-m28", token_text="m28directgrantonly")
        actor = AuthenticatedUser(user_id="m28-direct-grant-user", email="m28-direct-grant@example.test", roles=["user"], groups=[])
        sync_authenticated_user(actor)
        self._grant_direct_source(source_id, actor)

        token = set_current_user(actor)
        try:
            response = perform_search(SearchRequest(question="m28directgrantonly", k=5, mode="keyword"))
        finally:
            reset_current_user(token)

        self.assertTrue(any(item.source_id == source_id for item in response.results))

    def test_document_acl_group_behavior_still_trims_forbidden_sources(self):
        run_migrations()
        settings.ACCESS_STRATEGY = "document_acl_with_time_bound_grants"
        settings.AUTH_MODE = "dev"
        allowed_source = self._seed_source(corpus="alpha-m28", token_text="m28alphaonly")
        blocked_source = self._seed_source(corpus="beta-m28", token_text="m28betaonly")
        assign_document_acl(source_id=allowed_source, group_names=["alpha-m28"])
        assign_document_acl(source_id=blocked_source, group_names=["beta-m28"])
        actor = AuthenticatedUser(user_id="m28-alpha-user", email="m28-alpha@example.test", roles=["user"], groups=["alpha-m28"])
        sync_authenticated_user(actor)

        token = set_current_user(actor)
        try:
            allowed = perform_search(SearchRequest(question="m28alphaonly", k=5, mode="keyword"))
            blocked = perform_search(SearchRequest(question="m28betaonly", k=5, mode="keyword"))
        finally:
            reset_current_user(token)

        self.assertTrue(any(item.source_id == allowed_source for item in allowed.results))
        self.assertFalse(any(item.source_id == blocked_source for item in blocked.results))

    def _chunk_id_for_source(self, source_id: int) -> int:
        with engine.connect() as conn:
            return int(conn.execute(text("SELECT id FROM chunks WHERE source_id = :source_id LIMIT 1"), {"source_id": source_id}).scalar_one())

    def _grant_direct_source(self, source_id: int, actor: AuthenticatedUser) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO user_source_access_grants (
                        source_id, grantee_external_user_id, grantee_email, grant_reason, expires_at
                    )
                    VALUES (:source_id, :user_id, :email, 'm28 test grant', now() + interval '1 hour')
                    """
                ),
                {"source_id": source_id, "user_id": actor.user_id, "email": actor.email},
            )


if __name__ == "__main__":
    unittest.main()
