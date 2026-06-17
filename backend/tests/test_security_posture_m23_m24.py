import unittest

from fastapi.testclient import TestClient

import app.api.search as search_api
import app.api.upload as upload_api
import app.main as main_module
from app.auth.context import AuthenticatedUser
from app.auth.service import AuthError, validate_security_posture
from app.core.config import settings
from app.core.rate_limit import _buckets
from app.core_rag.retrieval import SearchResponse
from app.main import app


class SecurityPostureM23M24Tests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "APP_ENV": settings.APP_ENV,
            "AUTH_ENABLED": settings.AUTH_ENABLED,
            "AUTH_MODE": settings.AUTH_MODE,
            "AUTH_STATE_SIGNING_SECRET": settings.AUTH_STATE_SIGNING_SECRET,
            "DEV_LOCAL_JWT_SECRET": settings.DEV_LOCAL_JWT_SECRET,
            "AUTH_NONE_ALLOW_UPLOAD": settings.AUTH_NONE_ALLOW_UPLOAD,
            "MAX_UPLOAD_SIZE_BYTES": settings.MAX_UPLOAD_SIZE_BYTES,
            "RATE_LIMIT_ENABLED": settings.RATE_LIMIT_ENABLED,
            "RATE_LIMIT_SEARCH_PER_MINUTE": settings.RATE_LIMIT_SEARCH_PER_MINUTE,
        }
        self.original_authenticate = main_module.authenticate_request
        self.original_sync = main_module.sync_authenticated_user
        self.original_search = search_api.perform_search
        self.original_process_upload = upload_api.process_upload
        main_module.sync_authenticated_user = lambda user: None
        _buckets.clear()

    def tearDown(self):
        for key, value in self.original.items():
            setattr(settings, key, value)
        main_module.authenticate_request = self.original_authenticate
        main_module.sync_authenticated_user = self.original_sync
        search_api.perform_search = self.original_search
        upload_api.process_upload = self.original_process_upload
        _buckets.clear()

    def test_m23_startup_guard_rejects_unsafe_prod_modes_and_weak_secrets(self):
        settings.APP_ENV = "prod"
        settings.AUTH_MODE = "none"
        with self.assertRaises(AuthError):
            validate_security_posture()

        settings.AUTH_MODE = "dev"
        with self.assertRaises(AuthError):
            validate_security_posture()

        settings.AUTH_MODE = "oidc"
        settings.AUTH_STATE_SIGNING_SECRET = "rag-enterprise-starter-dev-state-secret"
        settings.DEV_LOCAL_JWT_SECRET = "rag-enterprise-local-dev-jwt-secret"
        with self.assertRaises(AuthError):
            validate_security_posture()

    def test_m23_local_dev_endpoints_404_outside_local_dev_mode(self):
        settings.APP_ENV = "prod"
        settings.AUTH_MODE = "oidc"
        settings.AUTH_STATE_SIGNING_SECRET = "x" * 40
        settings.DEV_LOCAL_JWT_SECRET = "y" * 40
        client = TestClient(app)

        response = client.post(
            "/auth/local-dev-login",
            json={"email": "test-admin@ragenterprise.local", "password": "password123"},
        )

        self.assertEqual(response.status_code, 404)

    def test_m24_search_and_upload_fail_closed_in_secured_mode(self):
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "dev"
        main_module.authenticate_request = lambda request: None
        client = TestClient(app)

        search_response = client.post("/search", json={"question": "private", "k": 1, "mode": "keyword"})
        upload_response = client.post("/upload", files={"file": ("note.txt", b"hello", "text/plain")})

        self.assertEqual(search_response.status_code, 401)
        self.assertEqual(upload_response.status_code, 401)

    def test_m24_upload_requires_admin_or_editor_in_secured_mode(self):
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "dev"
        actor = AuthenticatedUser(user_id="user-1", email="user@example.test", roles=["user"])
        main_module.authenticate_request = lambda request: actor
        client = TestClient(app)

        response = client.post("/upload", files={"file": ("note.txt", b"hello", "text/plain")})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "upload_role_required")

    def test_m24_no_auth_upload_is_disabled_unless_explicitly_allowed(self):
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "none"
        settings.AUTH_NONE_ALLOW_UPLOAD = False
        client = TestClient(app)

        response = client.post("/upload", files={"file": ("note.txt", b"hello", "text/plain")})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "upload_disabled")

    def test_m24_upload_rejects_oversized_request_before_processing(self):
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "dev"
        settings.MAX_UPLOAD_SIZE_BYTES = 4
        actor = AuthenticatedUser(user_id="admin-1", email="admin@example.test", roles=["admin"])
        main_module.authenticate_request = lambda request: actor
        client = TestClient(app)

        response = client.post("/upload", files={"file": ("note.txt", b"hello", "text/plain")})

        self.assertEqual(response.status_code, 413)

    def test_m24_search_rate_limit_returns_429(self):
        settings.APP_ENV = "local"
        settings.AUTH_MODE = "dev"
        settings.RATE_LIMIT_ENABLED = True
        settings.RATE_LIMIT_SEARCH_PER_MINUTE = 1
        actor = AuthenticatedUser(user_id="admin-1", email="admin@example.test", roles=["admin"])
        main_module.authenticate_request = lambda request: actor
        search_api.perform_search = lambda request: SearchResponse(results=[], latency_ms=1, mode="keyword")
        client = TestClient(app)

        first = client.post("/search", json={"question": "alpha", "k": 1, "mode": "keyword"})
        second = client.post("/search", json={"question": "alpha", "k": 1, "mode": "keyword"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)


if __name__ == "__main__":
    unittest.main()
