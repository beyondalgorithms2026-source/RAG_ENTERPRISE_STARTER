import unittest

from fastapi.testclient import TestClient

from app.auth.context import AuthenticatedUser
from app.core_rag.answering import AskRequest
from app.auth.service import authenticate_local_dev_user, issue_local_dev_token, resolve_post_login_path, validate_local_dev_token
from app.core.config import settings
from app.db.repo_acl import local_dev_acl_bypass_enabled
from app.main import app


class DevAuthTests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "AUTH_ENABLED": settings.AUTH_ENABLED,
            "AUTH_MODE": settings.AUTH_MODE,
        }
        settings.AUTH_ENABLED = True
        settings.AUTH_MODE = "dev"

    def tearDown(self):
        settings.AUTH_ENABLED = self.original["AUTH_ENABLED"]
        settings.AUTH_MODE = self.original["AUTH_MODE"]

    def test_local_dev_user_token_round_trip(self):
        user = authenticate_local_dev_user("test-admin@ragenterprise.local", "password123")
        self.assertIsNotNone(user)
        token = issue_local_dev_token(user)
        decoded = validate_local_dev_token(token)
        self.assertEqual(decoded.email, "test-admin@ragenterprise.local")
        self.assertIn("admin", decoded.roles)

    def test_local_dev_post_login_path_defaults_by_role(self):
        user = authenticate_local_dev_user("test-user@ragenterprise.local", "password123")
        admin = authenticate_local_dev_user("test-admin@ragenterprise.local", "password123")
        self.assertEqual(resolve_post_login_path(user), "/console/workspace/chat")
        self.assertEqual(resolve_post_login_path(admin), "/console/admin")
        self.assertEqual(resolve_post_login_path(user, "/console/workspace/sources"), "/console/workspace/sources")

    def test_local_dev_login_endpoint_sets_cookie(self):
        client = TestClient(app)
        response = client.post(
            "/auth/local-dev-login",
            json={
                "email": "test-user@ragenterprise.local",
                "password": "password123",
                "next_path": "/console",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect_path"], "/console/workspace/chat")
        self.assertIn(settings.AUTH_COOKIE_NAME, response.headers.get("set-cookie", ""))

    def test_auth_providers_degrades_gracefully_in_local_dev_mode(self):
        client = TestClient(app)
        response = client.get("/auth/providers")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["auth_enabled"])
        self.assertEqual(payload["auth_mode"], "dev")
        self.assertTrue(payload["local_dev_enabled"])
        self.assertFalse(payload["oidc_configured"])
        self.assertFalse(payload["sso_available"])
        self.assertEqual(payload["providers"], [])

    def test_auth_login_redirects_back_to_frontend_login_when_local_dev_only(self):
        client = TestClient(app)
        response = client.get("/auth/login", params={"next_path": "/console/admin"}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=%2Fconsole%2Fadmin&dev_login=1", response.headers["location"])

    def test_dev_test_identities_enable_local_dev_acl_bypass(self):
        test_user = AuthenticatedUser(user_id="dev-test-user", email="test-user@ragenterprise.local", roles=["user"], groups=["dev-users"])
        test_admin = AuthenticatedUser(user_id="dev-test-admin", email="test-admin@ragenterprise.local", roles=["admin", "user"], groups=["dev-admins"])
        regular_user = AuthenticatedUser(user_id="someone-else", email="someone@example.com", roles=["user"], groups=["dev-users"])
        self.assertTrue(local_dev_acl_bypass_enabled(test_user))
        self.assertTrue(local_dev_acl_bypass_enabled(test_admin))
        self.assertFalse(local_dev_acl_bypass_enabled(regular_user))

    def test_streamed_ask_restores_authenticated_user_inside_worker_thread(self):
        import app.api.ask as ask_module
        import app.main as main_module

        observed: dict[str, object] = {}
        original_impl = ask_module._perform_ask_internal
        original_verify = ask_module.verify_llm_ready
        original_sync = main_module.sync_authenticated_user

        def fake_perform(request: AskRequest, progress_callback=None):
            from app.auth.context import get_current_user

            user = get_current_user()
            observed["user_id"] = user.user_id if user else None
            observed["email"] = user.email if user else None
            observed["groups"] = list(user.groups) if user else []
            if progress_callback:
                progress_callback(42, "Checked auth context")
            return ask_module.AskResponse(answer="ok", citations=[], used_chunks_count=0, latency_ms=1, mode="hybrid")

        ask_module._perform_ask_internal = fake_perform
        ask_module.verify_llm_ready = lambda: True
        main_module.sync_authenticated_user = lambda user: None

        try:
            client = TestClient(app)
            login = client.post(
                "/auth/local-dev-login",
                json={
                    "email": "test-user@ragenterprise.local",
                    "password": "password123",
                    "next_path": "/console/workspace/chat",
                },
            )
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/ask/stream",
                json={
                    "question": "Who is Sam Walton?",
                    "k_chunks": 2,
                    "mode": "hybrid",
                    "dry_run": False,
                },
            )
        finally:
            ask_module._perform_ask_internal = original_impl
            ask_module.verify_llm_ready = original_verify
            main_module.sync_authenticated_user = original_sync

        self.assertEqual(response.status_code, 200)
        self.assertIn('"type": "progress"', response.text)
        self.assertIn('"type": "result"', response.text)
        self.assertEqual(observed["user_id"], "dev-test-user")
        self.assertEqual(observed["email"], "test-user@ragenterprise.local")
        self.assertEqual(observed["groups"], ["dev-users"])
