from tests.smoke_test_base import *

from app.health import P0_TILES, eval_gate_tile, health_dashboard, reranker_warmup_tile, semantic_cache_tile


class HealthDashboardAR10Tests(SmokeTestBase):
    """AR10: incoherence must be visible at a glance — the dashboard composes the
    AR2 invariants plus warm-up/cache/eval into one banner with P0 escalation."""

    def _tile(self, dashboard, name):
        return next(t for t in dashboard["tiles"] if t["tile"] == name)

    def test_healthy_dev_db_shows_all_p0_green(self):
        dashboard = health_dashboard()
        for name in P0_TILES:
            with self.subTest(tile=name):
                self.assertEqual(self._tile(dashboard, name)["status"], "pass", msg=self._tile(dashboard, name)["reason"])
        self.assertFalse(dashboard["p0_breached"])
        self.assertIn(dashboard["banner"], {"pass", "warn"})  # warn allowed (e.g. no baseline eval yet)

    def test_injected_draft_active_profile_turns_tile_red_and_breaches_p0(self):
        # AR2-style incoherence injected directly into the DB (bypassing the API
        # guard): a real draft-named profile made active, as draft-645-retrieval
        # was. The harness restores active profiles in tearDown.
        from app.db.repo_profiles import get_active_profile_name, get_profile, upsert_profile

        base = get_profile("retrieval", get_active_profile_name("retrieval"))["config_json"] or {}
        upsert_profile("retrieval", "draft-ar10-injected", dict(base), is_default=False)
        self.addCleanup(self._delete_profile, "retrieval", "draft-ar10-injected")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO active_profiles (profile_type, profile_name) VALUES ('retrieval', 'draft-ar10-injected') "
                    "ON CONFLICT (profile_type) DO UPDATE SET profile_name = EXCLUDED.profile_name"
                )
            )
        dashboard = health_dashboard()
        tile = self._tile(dashboard, "active_profiles_promoted")
        self.assertEqual(tile["status"], "fail")
        self.assertEqual(dashboard["banner"], "fail")
        self.assertTrue(dashboard["p0_breached"])
        self.assertIn("active_profiles_promoted", dashboard["p0_failures"])

    def test_reranker_warmup_tile_reflects_failed_warmup(self):
        from app.db.repo_tuning_configs import record_model_warmup

        warmup = record_model_warmup(
            model_type="reranker",
            model_name="cross-encoder/ar10-test",
            status="failure",
            latency_ms=None,
            error_message="could not load",
        )
        self.addCleanup(self._delete_warmup, warmup["id"])
        tile = reranker_warmup_tile()
        self.assertEqual(tile["status"], "fail")
        self.assertIn("warm-up failed", tile["reason"])

    def _delete_warmup(self, warmup_id):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM model_warmup_runs WHERE id = :id"), {"id": warmup_id})

    def _delete_profile(self, profile_type, name):
        # Restore active retrieval to a non-draft promoted profile before deleting
        # the injected draft, so live-config sync (which resolves active profiles)
        # never references a missing row during teardown.
        from app.db.repo_profiles import set_active_profile
        from app.profiles.resolver import invalidate_cache

        snapshot = getattr(self, "_active_profiles_snapshot", {})
        restore_name = snapshot.get(profile_type)
        if restore_name and restore_name != name:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE active_profiles SET profile_name = :n WHERE profile_type = :t"),
                    {"n": restore_name, "t": profile_type},
                )
            invalidate_cache(profile_type)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM profiles WHERE profile_type = :t AND name = :n"), {"t": profile_type, "n": name})

    def test_eval_gate_tile_reports_baseline_or_warns(self):
        tile = eval_gate_tile()
        self.assertIn(tile["status"], {"pass", "fail", "warn"})
        if tile["status"] == "warn":
            self.assertIn("No live baseline", tile["reason"])
        else:
            self.assertIn("gate_status", tile.get("details", {}))

    def test_semantic_cache_tile_present(self):
        # AR15: pass when an active policy exists, else warn "globally OFF".
        tile = semantic_cache_tile()
        self.assertEqual(tile["tile"], "semantic_cache")
        self.assertIn(tile["status"], {"pass", "warn"})
        if tile["status"] == "warn":
            self.assertIn("globally OFF", tile["reason"])

    def test_dashboard_endpoint_returns_banner_and_tiles(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        client = TestClient(app)
        original_auth = settings.AUTH_ENABLED
        original_fn = main_module.authenticate_request
        try:
            settings.AUTH_ENABLED = True
            main_module.authenticate_request = lambda request: AuthenticatedUser(user_id="ar10-admin", email="ar10@example.com", roles=["admin"], groups=["ops"])
            response = client.get("/admin/health/dashboard", headers={"Authorization": "Bearer t"})
        finally:
            settings.AUTH_ENABLED = original_auth
            main_module.authenticate_request = original_fn
        self.assertEqual(response.status_code, 200, msg=response.text)
        body = response.json()
        self.assertIn("banner", body)
        tile_names = {t["tile"] for t in body["tiles"]}
        self.assertTrue(P0_TILES.issubset(tile_names))
        self.assertIn("reranker_warmup", tile_names)
        self.assertIn("eval_gate", tile_names)
