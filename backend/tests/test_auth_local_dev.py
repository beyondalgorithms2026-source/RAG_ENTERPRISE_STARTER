import unittest

from fastapi.testclient import TestClient

from app.auth.service import authenticate_local_dev_user, issue_local_dev_token, resolve_post_login_path, validate_local_dev_token
from app.core.config import settings
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
