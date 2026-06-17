from tests.smoke_test_base import *


class AdminModularityAR18Tests(SmokeTestBase):
    def setUp(self):
        super().setUp()
        run_migrations()
        from app.db.repo_runtime_settings import delete_setting, get_setting

        self.original_runtime_modules = get_setting("admin_modules_enabled")
        delete_setting("admin_modules_enabled")
        self.original_module_settings = (
            settings.SCENARIO_PROFILE,
            settings.ADMIN_MODULES_ENABLED,
            settings.APP_ENV,
            settings.SEGREGATION_OF_DUTIES_ENABLED,
        )
        settings.SCENARIO_PROFILE = "enterprise_oidc_acl"
        settings.ADMIN_MODULES_ENABLED = ""
        settings.APP_ENV = "local"
        settings.SEGREGATION_OF_DUTIES_ENABLED = False

    def tearDown(self):
        from app.db.repo_runtime_settings import delete_setting, set_setting

        delete_setting("admin_modules_enabled")
        if self.original_runtime_modules is not None:
            set_setting("admin_modules_enabled", self.original_runtime_modules)
        (
            settings.SCENARIO_PROFILE,
            settings.ADMIN_MODULES_ENABLED,
            settings.APP_ENV,
            settings.SEGREGATION_OF_DUTIES_ENABLED,
        ) = self.original_module_settings
        super().tearDown()

    def _client(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        original_auth = settings.AUTH_ENABLED
        original_fn = main_module.authenticate_request
        original_sync = main_module.sync_authenticated_user
        settings.AUTH_ENABLED = True
        main_module.authenticate_request = lambda request: AuthenticatedUser(
            user_id="ar18-admin", email="ar18@example.test", roles=["admin"], groups=["ops"]
        )
        main_module.sync_authenticated_user = lambda user: None
        return TestClient(app), lambda: (
            setattr(settings, "AUTH_ENABLED", original_auth),
            setattr(main_module, "authenticate_request", original_fn),
            setattr(main_module, "sync_authenticated_user", original_sync),
        )

    def test_first_class_modules_are_in_inventory_and_navigation(self):
        from app.auth.admin_modules import admin_modules_payload

        payload = admin_modules_payload()
        for module in {"health", "cost", "flywheel", "embedding", "providers"}:
            self.assertIn(module, payload["enabled_modules"])
            self.assertIn(module, {item["module"] for item in payload["navigation"]})
        self.assertIn("/console/admin/modules", {item["href"] for item in payload["navigation"]})

    def test_formerly_ungated_endpoint_groups_return_403(self):
        from app.db.repo_runtime_settings import set_setting

        client, restore = self._client()
        try:
            set_setting("admin_modules_enabled", ["overview"])
            cases = (
                ("/admin/embedding/serving", "embedding"),
                ("/admin/llm/providers", "providers"),
                ("/admin/retrieval/evidence", "tuning"),
            )
            for path, module in cases:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 403, msg=response.text)
                    self.assertEqual(response.json()["detail"]["module"], module)
        finally:
            restore()

    def test_disabling_cost_hides_navigation_and_blocks_endpoint(self):
        from app.db.repo_runtime_settings import set_setting

        client, restore = self._client()
        try:
            set_setting("admin_modules_enabled", ["overview", "health"])
            modules = client.get("/admin/modules")
            self.assertEqual(modules.status_code, 200, msg=modules.text)
            self.assertNotIn("cost", {item["module"] for item in modules.json()["navigation"]})
            response = client.get("/admin/cost/summary")
            self.assertEqual(response.status_code, 403, msg=response.text)
            self.assertEqual(response.json()["detail"]["module"], "cost")
        finally:
            restore()

    def test_runtime_override_precedence_empty_override_and_reset(self):
        from app.auth.admin_modules import admin_modules_payload
        from app.db.repo_runtime_settings import delete_setting, set_setting

        settings.SCENARIO_PROFILE = "research_no_auth"
        settings.ADMIN_MODULES_ENABLED = "sources,cost"
        self.assertEqual(admin_modules_payload()["source"], "environment")
        set_setting("admin_modules_enabled", ["providers"])
        runtime = admin_modules_payload()
        self.assertEqual(runtime["source"], "runtime")
        self.assertEqual(runtime["enabled_modules"], ["overview", "providers"])
        set_setting("admin_modules_enabled", [])
        self.assertEqual(admin_modules_payload()["enabled_modules"], ["overview"])
        delete_setting("admin_modules_enabled")
        restored = admin_modules_payload()
        self.assertEqual(restored["source"], "environment")
        self.assertEqual(restored["enabled_modules"], ["cost", "overview", "sources"])

    def test_unknown_modules_rejected_and_overview_locked(self):
        from app.db.repo_runtime_settings import set_setting

        with self.assertRaisesRegex(ValueError, "Unsupported admin modules"):
            set_setting("admin_modules_enabled", ["unknown"])
        result = set_setting("admin_modules_enabled", ["sources"])
        self.assertEqual(result["value"], ["overview", "sources"])

    def test_patch_persists_audits_and_reset_restores_preset(self):
        from app.db.repo_admin_audit import list_admin_audit_events

        client, restore = self._client()
        try:
            saved = client.patch("/admin/modules", json={"enabled_modules": ["sources", "health"]})
            self.assertEqual(saved.status_code, 200, msg=saved.text)
            self.assertEqual(saved.json()["source"], "runtime")
            self.assertEqual(saved.json()["enabled_modules"], ["health", "overview", "sources"])
            reloaded = client.get("/admin/modules")
            self.assertEqual(reloaded.json()["runtime_override"], ["health", "overview", "sources"])
            events = list_admin_audit_events(action="admin_modules.update", actor_external_user_id="ar18-admin")
            self.assertTrue(events)
            self.assertEqual(events[0]["after_json"]["source"], "runtime")
            reset = client.patch("/admin/modules", json={"enabled_modules": None})
            self.assertEqual(reset.status_code, 200, msg=reset.text)
            self.assertEqual(reset.json()["source"], "scenario")
            self.assertIsNone(reset.json()["runtime_override"])
        finally:
            restore()

    def test_production_patch_requires_distinct_approval_actor(self):
        client, restore = self._client()
        settings.APP_ENV = "prod"
        settings.SEGREGATION_OF_DUTIES_ENABLED = True
        try:
            missing = client.patch("/admin/modules", json={"enabled_modules": ["overview"]})
            self.assertEqual(missing.status_code, 409, msg=missing.text)
            same = client.patch(
                "/admin/modules",
                json={"enabled_modules": ["overview"]},
                headers={"X-Approval-Actor": "ar18-admin"},
            )
            self.assertEqual(same.status_code, 409, msg=same.text)
            approved = client.patch(
                "/admin/modules",
                json={"enabled_modules": ["overview"]},
                headers={"X-Approval-Actor": "ar18-approver"},
            )
            self.assertEqual(approved.status_code, 200, msg=approved.text)
        finally:
            restore()


if __name__ == "__main__":
    unittest.main()
