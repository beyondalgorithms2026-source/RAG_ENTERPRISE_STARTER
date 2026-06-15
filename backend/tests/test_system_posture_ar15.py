from tests.smoke_test_base import *

from app.system_posture import system_posture


class SystemPostureAR15Tests(SmokeTestBase):
    """AR15: an admin can see every operationally relevant default/flag without
    reading the environment or the database."""

    REQUIRED_SECTIONS = {"serving", "cache", "retrieval_defaults", "eval_enforcement", "workers", "rate_limits", "cost_governance"}

    def test_posture_has_all_sections_with_editable_metadata(self):
        posture = system_posture()
        self.assertEqual(self.REQUIRED_SECTIONS, set(posture.keys()))
        for section in posture.values():
            for item in section.get("items", []):
                self.assertIn("label", item)
                self.assertIn("value", item)
                self.assertIn("editable_via", item)
                self.assertIn("requires_restart", item)

    def test_workers_report_single_process(self):
        posture = system_posture()
        self.assertTrue(posture["workers"]["single_process"])

    def test_eval_enforcement_mode_surfaced(self):
        posture = system_posture()
        self.assertIn(posture["eval_enforcement"]["mode"], {"require", "warn"})

    def test_cache_off_headline_when_no_active_policy(self):
        # With no active cache policy the posture states the OFF condition plainly.
        from app.db.repo_semantic_cache import cache_health

        if cache_health().get("active_policy"):
            self.skipTest("an active cache policy exists in this DB; off-state path not exercised")
        cache = system_posture()["cache"]
        self.assertFalse(cache["enabled"])
        self.assertEqual(cache["reason"], "no_active_policy")
        self.assertIn("globally OFF", cache["headline"])

    def test_endpoint_returns_posture(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        client = TestClient(app)
        original_auth = settings.AUTH_ENABLED
        original_fn = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(user_id="ar15-admin", email="ar15@example.com", roles=["admin"], groups=["ops"])
            response = client.get("/admin/system/posture", headers={"Authorization": "Bearer t"})
        finally:
            settings.AUTH_ENABLED = original_auth
            main_module.authenticate_request = original_fn
        self.assertEqual(response.status_code, 200, msg=response.text)
        self.assertEqual(self.REQUIRED_SECTIONS, set(response.json().keys()))

    def test_health_dashboard_cache_off_tile_warns(self):
        # AR15: the dashboard's semantic_cache tile warns (not silently passes) when off.
        from app.db.repo_semantic_cache import cache_health
        from app.health import semantic_cache_tile

        if cache_health().get("active_policy"):
            self.skipTest("active cache policy present")
        tile = semantic_cache_tile()
        self.assertEqual(tile["status"], "warn")
        self.assertIn("globally OFF", tile["reason"])
