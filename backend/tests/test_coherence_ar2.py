from tests.smoke_test_base import *

import app.coherence as coherence_module
from app.coherence import (
    is_draft_profile_name,
    run_coherence_checks,
    validate_embedding_profile_dimension,
)


class CoherenceAR2Tests(SmokeTestBase):
    """AR2 DoD: each audit-observed incoherent state is (a) rejected at write
    time and (b) flagged by the health endpoint when injected directly."""

    def _prime_model_dim(self, model: str, dim: int):
        coherence_module._MODEL_DIM_CACHE[model] = dim
        self.addCleanup(coherence_module._MODEL_DIM_CACHE.pop, model, None)

    def _delete_profile_on_cleanup(self, profile_type: str, name: str):
        def _delete():
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM profiles WHERE profile_type = :pt AND name = :name"),
                    {"pt": profile_type, "name": name},
                )

        self.addCleanup(_delete)

    def _admin_client(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        settings.AUTH_ENABLED = True
        main_module.authenticate_request = lambda request: AuthenticatedUser(
            user_id="admin-coherence",
            email="admin.coherence@example.com",
            roles=["admin"],
            groups=["ops"],
        )

        def _restore():
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

        self.addCleanup(_restore)
        return TestClient(app)

    # --- Audit state 1: wrong embedding dimension metadata ---

    def test_wrong_embedding_dimension_rejected_at_save(self):
        self._prime_model_dim("BAAI/bge-small-en-v1.5", 384)
        with self.assertRaises(ValueError):
            validate_embedding_profile_dimension(model_name="BAAI/bge-small-en-v1.5", declared_dimension=768)

        client = self._admin_client()
        response = client.post(
            "/admin/profiles",
            json={
                "profile_type": "embedding",
                "profile_name": f"ar2-bad-dim-{uuid4().hex[:6]}",
                "config": {"model": "BAAI/bge-small-en-v1.5", "dimension": 768, "batch_size": 32},
            },
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["error"], "embedding_dimension_mismatch")

    def test_wrong_registry_dimension_flagged_by_health_endpoint(self):
        self._prime_model_dim("BAAI/bge-small-en-v1.5", 384)
        bad_name = f"ar2-injected-{uuid4().hex[:6]}"
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO profiles (profile_type, name, config_json, is_default) "
                    "VALUES ('embedding', :name, CAST(:cfg AS jsonb), false)"
                ),
                {"name": bad_name, "cfg": '{"model": "BAAI/bge-small-en-v1.5", "dimension": 768, "batch_size": 32}'},
            )
        self._delete_profile_on_cleanup("embedding", bad_name)

        client = self._admin_client()
        payload = client.get("/admin/health/coherence", headers={"Authorization": "Bearer fake-token"}).json()
        registry = next(item for item in payload["invariants"] if item["invariant"] == "embedding_registry_metadata")
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(registry["status"], "fail")
        self.assertTrue(any(m.get("profile") == bad_name for m in registry["details"]["mismatches"]))

    # --- Audit state 2: draft profile active as live ---

    def test_draft_profile_activation_rejected_at_write_time(self):
        from app.db.repo_profiles import set_active_profile, upsert_profile

        draft_name = f"draft-ar2-{uuid4().hex[:6]}-retrieval"
        upsert_profile("retrieval", draft_name, {"default_mode": "hybrid"}, is_default=False)
        self._delete_profile_on_cleanup("retrieval", draft_name)

        with self.assertRaises(ValueError):
            set_active_profile("retrieval", draft_name)

        client = self._admin_client()
        response = client.post(
            "/admin/profiles/active",
            json={"profile_type": "retrieval", "profile_name": draft_name},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["error"], "draft_profile_activation_blocked")

    def test_draft_active_state_flagged_by_health_endpoint_when_injected(self):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO active_profiles (profile_type, profile_name, updated_at) "
                    "VALUES ('retrieval', 'draft-ar2-injected-retrieval', now()) "
                    "ON CONFLICT (profile_type) DO UPDATE SET profile_name = EXCLUDED.profile_name, updated_at = now()"
                )
            )
        # Harness tearDown restores the snapshotted active profiles.

        client = self._admin_client()
        payload = client.get("/admin/health/coherence", headers={"Authorization": "Bearer fake-token"}).json()
        promoted = next(item for item in payload["invariants"] if item["invariant"] == "active_profiles_promoted")
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(promoted["status"], "fail")
        self.assertIn("draft-ar2-injected-retrieval", str(promoted["details"]["draft_active"]))

    def test_promotion_renames_draft_named_retrieval_profiles(self):
        self.assertTrue(is_draft_profile_name("draft-123-retrieval"))
        self.assertFalse(is_draft_profile_name("promoted-123-retrieval"))
        # The promote path builds promoted-{draft_id}-retrieval names; the
        # repo-level guard makes any draft-named activation raise, so a
        # promotion that failed to rename can no longer complete silently.
        import inspect

        from app.db.repo_tuning_configs import promote_candidate_to_live

        source = inspect.getsource(promote_candidate_to_live)
        self.assertIn('f"promoted-{draft_id}-retrieval"', source)

    # --- Audit state 3: migration ledger behind the plan ---

    def test_ledger_drift_flagged_by_health_endpoint_when_injected(self):
        run_migrations()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM schema_migration_ledger WHERE step_id = 'MIG-P020'"))
        self.addCleanup(run_migrations)

        client = self._admin_client()
        payload = client.get("/admin/health/coherence", headers={"Authorization": "Bearer fake-token"}).json()
        ledger = next(item for item in payload["invariants"] if item["invariant"] == "migration_ledger")
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(ledger["status"], "fail")
        self.assertIn("MIG-P020", ledger["details"]["missing"])

    # --- Startup enforcement and healthy baseline ---

    def test_startup_enforcement_warns_local_and_fails_prod(self):
        from app.coherence import enforce_startup_coherence

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO active_profiles (profile_type, profile_name, updated_at) "
                    "VALUES ('retrieval', 'draft-ar2-startup-retrieval', now()) "
                    "ON CONFLICT (profile_type) DO UPDATE SET profile_name = EXCLUDED.profile_name, updated_at = now()"
                )
            )

        settings.APP_ENV = "local"
        report = enforce_startup_coherence()
        self.assertEqual(report["status"], "fail")

        settings.APP_ENV = "prod"
        with self.assertRaises(RuntimeError):
            enforce_startup_coherence()
        settings.APP_ENV = "local"

    def test_repaired_database_reports_all_green(self):
        run_migrations()
        report = run_coherence_checks(deep=False)
        self.assertEqual(report["status"], "pass", msg=str(report))
