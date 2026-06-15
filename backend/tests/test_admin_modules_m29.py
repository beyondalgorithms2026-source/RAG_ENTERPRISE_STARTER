import unittest

from fastapi.testclient import TestClient

import app.main as main_module
from app.auth.admin_modules import admin_modules_payload, enabled_admin_modules
from app.auth.context import AuthenticatedUser
from app.auth.service import AuthError, validate_security_posture
from app.core.config import settings
from app.db.repo_runtime_settings import delete_setting, get_setting, set_setting
from app.main import app


class AdminModulesM29Tests(unittest.TestCase):
    def setUp(self):
        self.original = {
            "SCENARIO_PROFILE": settings.SCENARIO_PROFILE,
            "ADMIN_MODULES_ENABLED": settings.ADMIN_MODULES_ENABLED,
            "AUTH_MODE": settings.AUTH_MODE,
            "APP_ENV": settings.APP_ENV,
        }
        self.original_authenticate = main_module.authenticate_request
        self.original_sync = main_module.sync_authenticated_user
        self.original_runtime_modules = get_setting("admin_modules_enabled")
        delete_setting("admin_modules_enabled")
        settings.AUTH_MODE = "dev"
        settings.APP_ENV = "local"
        self.admin = AuthenticatedUser(user_id="m29-admin", email="m29-admin@example.test", roles=["admin"])
        main_module.authenticate_request = lambda request: self.admin
        main_module.sync_authenticated_user = lambda user: None

    def tearDown(self):
        if self.original_runtime_modules is None:
            delete_setting("admin_modules_enabled")
        else:
            set_setting("admin_modules_enabled", self.original_runtime_modules)
        for key, value in self.original.items():
            setattr(settings, key, value)
        main_module.authenticate_request = self.original_authenticate
        main_module.sync_authenticated_user = self.original_sync

    def test_enterprise_profile_keeps_full_admin_surface(self):
        settings.SCENARIO_PROFILE = "enterprise_oidc_acl"
        payload = admin_modules_payload()

        self.assertIn("tuning", payload["enabled_modules"])
        self.assertIn("governance", payload["enabled_modules"])
        self.assertIn("connectors", payload["enabled_modules"])
        self.assertFalse(payload["disabled_modules"])

    def test_small_enterprise_hides_tuning_governance_and_connectors(self):
        settings.SCENARIO_PROFILE = "small_enterprise_corpus_acl"
        payload = admin_modules_payload()

        self.assertIn("sources", payload["enabled_modules"])
        self.assertIn("corpora", payload["enabled_modules"])
        self.assertIn("access", payload["enabled_modules"])
        self.assertIn("tuning", payload["disabled_modules"])
        self.assertIn("governance", payload["disabled_modules"])
        self.assertIn("connectors", payload["disabled_modules"])
        self.assertNotIn("/console/admin/connectors", {item["href"] for item in payload["navigation"]})

    def test_disabled_admin_module_direct_api_returns_403(self):
        settings.SCENARIO_PROFILE = "small_enterprise_corpus_acl"
        client = TestClient(app)

        tuning_response = client.get("/admin/tuning/configurations")
        connector_response = client.get("/connectors/db")

        self.assertEqual(tuning_response.status_code, 403)
        self.assertEqual(tuning_response.json()["detail"]["error"], "module_disabled")
        self.assertEqual(tuning_response.json()["detail"]["module"], "tuning")
        self.assertEqual(connector_response.status_code, 403)
        self.assertEqual(connector_response.json()["detail"]["module"], "connectors")

    def test_admin_modules_override_is_explicit_and_validated(self):
        settings.SCENARIO_PROFILE = "research_no_auth"
        settings.ADMIN_MODULES_ENABLED = "sources,corpora"

        self.assertEqual(enabled_admin_modules(), {"overview", "sources", "corpora"})

        settings.ADMIN_MODULES_ENABLED = "sources,unknown"
        with self.assertRaises(AuthError):
            validate_security_posture()

    def test_admin_modules_endpoint_returns_scenario_inventory(self):
        settings.SCENARIO_PROFILE = "research_no_auth"
        client = TestClient(app)

        response = client.get("/admin/modules")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["scenario_profile"], "research_no_auth")
        self.assertIn("sources", payload["enabled_modules"])
        self.assertIn("actions", payload["disabled_modules"])


if __name__ == "__main__":
    unittest.main()
