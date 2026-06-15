from tests.smoke_test_base import *


class RuntimeSettingsAR17Tests(SmokeTestBase):
    """AR17: cost budget, price table, and eval enforcement become console-editable
    (DB-backed) and override the environment, with an allowlist + validation."""

    def setUp(self):
        super().setUp()
        run_migrations()
        self._profile_names = []
        self._clear()

    def tearDown(self):
        self._clear()
        super().tearDown()

    def _clear(self):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM runtime_settings WHERE key = ANY(:k)"), {"k": ["llm_cost_alert_usd", "llm_price_table", "tuning_eval_enforcement"]})
            if self._profile_names:
                conn.execute(text("DELETE FROM profiles WHERE name = ANY(:names)"), {"names": self._profile_names})

    def _client(self):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        original_auth = settings.AUTH_ENABLED
        original_fn = main_module.authenticate_request
        settings.AUTH_ENABLED = True
        main_module.authenticate_request = lambda request: AuthenticatedUser(
            user_id="ar17", email="ar17@example.com", roles=["admin"], groups=["ops"]
        )
        return TestClient(app), lambda: (
            setattr(settings, "AUTH_ENABLED", original_auth),
            setattr(main_module, "authenticate_request", original_fn),
        )

    def test_allowlist_and_validation(self):
        from app.db.repo_runtime_settings import set_setting

        with self.assertRaisesRegex(ValueError, "not runtime-editable"):
            set_setting("APP_ENV", "prod")
        with self.assertRaisesRegex(ValueError, ">= 0"):
            set_setting("llm_cost_alert_usd", -1)
        with self.assertRaisesRegex(ValueError, "require"):
            set_setting("tuning_eval_enforcement", "fuzzy")
        with self.assertRaisesRegex(ValueError, "input_per_1k"):
            set_setting("llm_price_table", {"m": [1.0]})
        with self.assertRaisesRegex(ValueError, "non-negative"):
            set_setting("llm_price_table", {"m": [-1.0, 2.0]})
        with self.assertRaisesRegex(ValueError, "not be empty"):
            set_setting("llm_price_table", {"": [1.0, 2.0]})

    def test_cost_alert_runtime_overrides_env(self):
        from app.db.repo_runtime_settings import set_setting
        from app.llm.pricing import cost_alert_usd

        original = settings.LLM_COST_ALERT_USD
        try:
            settings.LLM_COST_ALERT_USD = 0.10
            self.assertAlmostEqual(cost_alert_usd(), 0.10)
            set_setting("llm_cost_alert_usd", 0.99)
            self.assertAlmostEqual(cost_alert_usd(), 0.99)  # runtime wins
        finally:
            settings.LLM_COST_ALERT_USD = original

    def test_price_table_runtime_overrides_and_costs(self):
        from app.db.repo_runtime_settings import set_setting
        from app.llm.pricing import cost_usd, price_for

        set_setting("llm_price_table", {"acme-model": [0.002, 0.004]})
        self.assertEqual(price_for("acme-model"), (0.002, 0.004))
        self.assertEqual(cost_usd("acme-model", 1000, 1000), round(0.002 + 0.004, 6))

    def test_enforcement_runtime_overrides_env(self):
        from app.db.repo_runtime_settings import set_setting
        from app.eval.promotion_evidence import resolve_enforcement_mode

        original = settings.TUNING_EVAL_ENFORCEMENT
        try:
            settings.TUNING_EVAL_ENFORCEMENT = "warn"
            self.assertEqual(resolve_enforcement_mode(), "warn")
            set_setting("tuning_eval_enforcement", "require")
            self.assertEqual(resolve_enforcement_mode(), "require")  # runtime wins
        finally:
            settings.TUNING_EVAL_ENFORCEMENT = original

    def test_endpoints_get_and_patch_with_audit(self):
        client, restore = self._client()
        try:
            patch = client.patch("/admin/runtime-settings", json={"key": "llm_cost_alert_usd", "value": 0.5}, headers={"Authorization": "Bearer t"})
            self.assertEqual(patch.status_code, 200, msg=patch.text)
            get = client.get("/admin/runtime-settings", headers={"Authorization": "Bearer t"})
            self.assertEqual(get.status_code, 200, msg=get.text)
            setting = get.json()["settings"]["llm_cost_alert_usd"]
            self.assertAlmostEqual(setting["effective"], 0.5)
            self.assertEqual(setting["source"], "runtime")
            bad = client.patch("/admin/runtime-settings", json={"key": "APP_ENV", "value": "x"}, headers={"Authorization": "Bearer t"})
            self.assertEqual(bad.status_code, 422)
            reset = client.patch("/admin/runtime-settings", json={"key": "llm_cost_alert_usd", "value": None}, headers={"Authorization": "Bearer t"})
            self.assertEqual(reset.status_code, 200, msg=reset.text)
            self.assertIsNone(reset.json()["settings"]["llm_cost_alert_usd"]["override"])
        finally:
            restore()

    def test_runtime_setting_requires_distinct_approval_actor_in_prod(self):
        client, restore = self._client()
        original = (settings.APP_ENV, settings.SEGREGATION_OF_DUTIES_ENABLED)
        try:
            settings.APP_ENV = "prod"
            settings.SEGREGATION_OF_DUTIES_ENABLED = True
            denied = client.patch(
                "/admin/runtime-settings",
                json={"key": "llm_cost_alert_usd", "value": 0.25},
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(denied.status_code, 409)
            allowed = client.patch(
                "/admin/runtime-settings",
                json={"key": "llm_cost_alert_usd", "value": 0.25},
                headers={"Authorization": "Bearer t", "X-Approval-Actor": "approver-2"},
            )
            self.assertEqual(allowed.status_code, 200, msg=allowed.text)
            with engine.connect() as conn:
                event = conn.execute(
                    text("SELECT event_json FROM admin_audit_events WHERE action = 'runtime_settings.update' ORDER BY id DESC LIMIT 1")
                ).scalar_one()
            self.assertEqual(event["approval_actor"], "approver-2")
        finally:
            settings.APP_ENV, settings.SEGREGATION_OF_DUTIES_ENABLED = original
            restore()

    def test_llm_provider_validation_on_profile_write(self):
        client, restore = self._client()
        name = f"ar17-bad-{uuid4().hex[:6]}"
        self._profile_names.append(name)
        try:
            resp = client.post(
                "/admin/profiles",
                json={"profile_type": "llm", "profile_name": name, "config": {"provider": "not-a-provider", "model": "x", "base_url": "http://x"}},
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(resp.status_code, 422, msg=resp.text)
            self.assertEqual(resp.json()["detail"]["error"], "unknown_llm_provider")
        finally:
            restore()

    def test_legacy_unknown_provider_cannot_activate(self):
        from app.db.repo_profiles import upsert_profile

        client, restore = self._client()
        name = f"ar17-legacy-{uuid4().hex[:6]}"
        self._profile_names.append(name)
        upsert_profile("llm", name, {"provider": "removed-provider", "model": "x", "base_url": "http://x"})
        try:
            resp = client.post(
                "/admin/profiles/active",
                json={"profile_type": "llm", "profile_name": name},
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(resp.status_code, 422, msg=resp.text)
            self.assertEqual(resp.json()["detail"]["error"], "unknown_llm_provider")
        finally:
            restore()

    def test_llm_verify_uses_overrides_not_live(self):
        import app.llm.client as client_module

        client, restore = self._client()
        original_verify = client_module.verify_llm_connection
        original_ready = client_module._llm_ready
        try:
            seen = {}

            def fake_verify(*, update_global=True):
                from app.profiles.resolver import get_effective_llm

                llm = get_effective_llm()
                seen["model"] = llm.model
                seen["update_global"] = update_global
                return {"ready": True, "reason": "verified"}

            client_module._llm_ready = False
            client_module.verify_llm_connection = fake_verify
            resp = client.post(
                "/admin/llm/verify",
                json={"config": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "http://x"}},
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(resp.status_code, 200, msg=resp.text)
            self.assertTrue(resp.json()["ready"])
            self.assertEqual(resp.json()["reason"], "verified")
            self.assertEqual(seen["model"], "gpt-4o-mini")
            self.assertFalse(seen["update_global"])
            self.assertFalse(client_module.is_llm_ready())
        finally:
            restore()
            client_module.verify_llm_connection = original_verify
            client_module._llm_ready = original_ready

    def test_api_key_is_write_only_and_never_audited(self):
        client, restore = self._client()
        name = f"ar17-secret-{uuid4().hex[:6]}"
        secret = f"secret-{uuid4().hex}"
        self._profile_names.append(name)
        try:
            created = client.post(
                "/admin/profiles",
                json={
                    "profile_type": "llm",
                    "profile_name": name,
                    "config": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "https://example.invalid", "api_key": secret},
                },
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(created.status_code, 200, msg=created.text)
            self.assertNotIn(secret, created.text)
            config = created.json()["profile"]["config"]
            self.assertEqual(config["api_key"], "")
            self.assertTrue(config["api_key_configured"])

            listed = client.get("/admin/profiles?profile_type=llm", headers={"Authorization": "Bearer t"})
            self.assertNotIn(secret, listed.text)
            tuning = client.get("/admin/tuning/configurations", headers={"Authorization": "Bearer t"})
            self.assertNotIn(secret, tuning.text)
            with engine.connect() as conn:
                stored = conn.execute(text("SELECT config_json->>'api_key' FROM profiles WHERE name = :name"), {"name": name}).scalar_one()
                audit = conn.execute(
                    text("SELECT before_json, after_json, event_json FROM admin_audit_events WHERE resource_id = :resource ORDER BY id"),
                    {"resource": f"llm:{name}"},
                ).fetchall()
            self.assertEqual(stored, secret)
            self.assertNotIn(secret, json.dumps([list(row) for row in audit]))
        finally:
            restore()

    def test_blank_api_key_update_preserves_existing_secret(self):
        client, restore = self._client()
        name = f"ar17-preserve-{uuid4().hex[:6]}"
        secret = f"secret-{uuid4().hex}"
        self._profile_names.append(name)
        try:
            create = client.post(
                "/admin/profiles",
                json={
                    "profile_type": "llm",
                    "profile_name": name,
                    "config": {"provider": "openai", "model": "old", "base_url": "https://example.invalid", "api_key": secret},
                },
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(create.status_code, 200, msg=create.text)
            updated = client.patch(
                f"/admin/profiles/llm/{name}",
                json={"config": {"model": "new"}},
                headers={"Authorization": "Bearer t"},
            )
            self.assertEqual(updated.status_code, 200, msg=updated.text)
            with engine.connect() as conn:
                stored = conn.execute(text("SELECT config_json FROM profiles WHERE name = :name"), {"name": name}).scalar_one()
            self.assertEqual(stored["api_key"], secret)
            self.assertEqual(stored["model"], "new")
        finally:
            restore()

    def test_runtime_budget_drives_summary_and_alert_event(self):
        from app.core_rag.answering import _attach_generation_usage
        from app.db.repo_runtime_settings import set_setting
        from app.llm.pricing import usage_from_counts
        from app.llm.usage import add_usage, reset_usage

        client, restore = self._client()
        request_id = f"ar17-cost-{uuid4().hex}"
        try:
            set_setting("llm_cost_alert_usd", 0.000001)
            set_setting("llm_price_table", {"gpt-4o-mini": [1.0, 1.0]})
            reset_usage()
            add_usage(usage_from_counts("gpt-4o-mini", prompt_tokens=100, completion_tokens=100))
            _attach_generation_usage({}, request_id=request_id, retrieval_mode="hybrid", answer_path="llm", ask_latency_ms=5)
            summary = client.get("/admin/cost/summary?group_by=model", headers={"Authorization": "Bearer t"})
            self.assertEqual(summary.status_code, 200, msg=summary.text)
            governance = summary.json()["governance"]
            self.assertEqual(governance["llm_cost_alert_usd"]["source"], "runtime")
            self.assertEqual(governance["llm_price_table"]["effective"]["gpt-4o-mini"], [1.0, 1.0])
            with engine.connect() as conn:
                over_budget = conn.execute(
                    text("SELECT over_budget FROM generation_usage_events WHERE request_id = :request_id"), {"request_id": request_id}
                ).scalar_one()
                alert = conn.execute(
                    text("SELECT event_json FROM admin_audit_events WHERE action = 'cost.budget_exceeded' AND resource_id = :request_id"),
                    {"request_id": request_id},
                ).scalar_one()
            self.assertTrue(over_budget)
            self.assertEqual(float(alert["threshold_usd"]), 0.000001)
        finally:
            reset_usage()
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM generation_usage_events WHERE request_id = :request_id"), {"request_id": request_id})
            restore()
