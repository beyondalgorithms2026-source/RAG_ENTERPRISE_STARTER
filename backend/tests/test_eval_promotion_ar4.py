from tests.smoke_test_base import *

import json

from app.eval.pack_eval import DEGRADED_RETRIEVAL_OVERRIDES


class _Ar4Base(SmokeTestBase):
    """AR4: promotion requires evidence (audit: 'the single biggest missed
    integration' — the promotion path never invoked evaluation)."""

    def _admin_client(self, *, user_suffix: str):
        from fastapi.testclient import TestClient

        import app.main as main_module
        from app.auth.context import AuthenticatedUser

        run_migrations()
        client = TestClient(app)
        original_auth_enabled = settings.AUTH_ENABLED
        original_authenticate = main_module.authenticate_request
        settings.AUTH_ENABLED = True
        main_module.authenticate_request = lambda request: AuthenticatedUser(
            user_id=f"admin-ar4-{user_suffix}",
            email=f"admin.ar4.{user_suffix}@example.com",
            roles=["admin", "user"],
            groups=["ops"],
        )

        def _restore():
            settings.AUTH_ENABLED = original_auth_enabled
            main_module.authenticate_request = original_authenticate

        self.addCleanup(_restore)
        return client

    def _pin_enforcement(self, mode: str):
        original = settings.TUNING_EVAL_ENFORCEMENT
        settings.TUNING_EVAL_ENFORCEMENT = mode
        self.addCleanup(lambda: setattr(settings, "TUNING_EVAL_ENFORCEMENT", original))

    def _create_draft(self, *, retrieval_override_config=None):
        from app.auth.context import AuthenticatedUser
        from app.db.repo_profiles import get_active_profile_map, seed_default_profiles
        from app.db.repo_tuning_configs import create_candidate_draft

        seed_default_profiles(settings)
        actor = AuthenticatedUser(user_id="ar4-draft-author", email="ar4@example.com", roles=["admin"])
        selected_profiles = get_active_profile_map(["embedding", "reranker", "llm", "retrieval"])
        return create_candidate_draft(
            name=f"ar4-candidate-{uuid4().hex[:6]}",
            description="AR4 eval-before-promotion candidate.",
            selected_profiles=selected_profiles,
            retrieval_override_config=retrieval_override_config,
            actor=actor,
        )

    def _seed_graded_corpus_and_pack(self):
        """Seeded chunks + a temp pack inside PACKS_DIR so the eval-run
        endpoint (pack names only, no caller paths) can address it."""
        from app.eval.pack_builder import PACKS_DIR

        suffix = uuid4().hex[:8]
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (
                        file_name, storage_path, source_type, sensitivity_label, hash_sha256, file_size_bytes,
                        ingestion_status, enrichment_status, source_metadata_json
                    )
                    VALUES (:f, :p, 'pdf', 'public', :h, 100, 'embedded', 'not_started', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {"f": f"ar4-gate-{suffix}.pdf", "p": f"tests/ar4-gate-{suffix}.pdf", "h": (suffix + "ar4") * 4},
            ).scalar_one()
        self.addCleanup(self._delete_retrieval_records, [source_id])
        token = f"promotiontoken{suffix}"
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": index,
                    "heading": f"Section {index}",
                    "section_path": f"page:{index}",
                    "chunk_text": f"{token} promotion evidence passage number {index} about retrieval quality.",
                    "token_count": 9,
                    "locator_json": {"page": index},
                    "provenance_json": {"test": "ar4"},
                }
                for index in range(4)
            ],
        )
        with engine.connect() as conn:
            chunk_rows = conn.execute(
                text("SELECT id, chunk_index FROM chunks WHERE source_id = :s ORDER BY chunk_index"),
                {"s": source_id},
            ).fetchall()
        similarities = [0.95, 0.9, 0.85, 0.8]
        update_chunk_embeddings(
            [
                (chunk_id, basis_vector(similarities[index], (1 - similarities[index] ** 2) ** 0.5))
                for chunk_id, index in chunk_rows
            ]
        )
        pack_name = f"pack_ar4_{suffix}"
        pack_path = PACKS_DIR / f"{pack_name}.json"
        pack_path.parent.mkdir(parents=True, exist_ok=True)
        pack_path.write_text(
            json.dumps(
                {
                    "pack": pack_name,
                    "corpus": "ar4-test",
                    "builder_version": "ar4-test",
                    "case_counts": {"total": 1},
                    "cases": [
                        {
                            "id": f"ar4-case-{suffix}",
                            "question": f"{token} promotion evidence passage",
                            "provenance": "synthetic_chunk_grounded",
                            "review_status": "auto_labeled",
                            "relevant": {str(chunk_id): (3 if index == 0 else 2) for chunk_id, index in chunk_rows},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.addCleanup(pack_path.unlink, missing_ok=True)
        return pack_name

    def _pin_embed_texts(self):
        import app.core_rag.retrieval as retrieval_module

        original = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        self.addCleanup(lambda: setattr(retrieval_module, "embed_texts", original))


class EvalEnforcementModeAR4Tests(_Ar4Base):
    def test_enforcement_mode_defaults_and_override(self):
        from app.eval.promotion_evidence import resolve_enforcement_mode

        original_env = settings.APP_ENV
        self._pin_enforcement("")
        try:
            settings.APP_ENV = "local"
            self.assertEqual(resolve_enforcement_mode(), "warn")
            settings.APP_ENV = "prod"
            self.assertEqual(resolve_enforcement_mode(), "require")
            settings.TUNING_EVAL_ENFORCEMENT = "warn"
            self.assertEqual(resolve_enforcement_mode(), "warn")
        finally:
            settings.APP_ENV = original_env


class EvalBeforePromotionAR4Tests(_Ar4Base):
    def test_require_mode_blocks_promotion_without_eval(self):
        self._pin_enforcement("require")
        client = self._admin_client(user_suffix="noeval")
        draft = self._create_draft()
        response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft["id"], "promotion_note": "No evidence attached."},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(response.status_code, 422, msg=response.text)
        self.assertEqual(response.json()["detail"]["error"], "eval_evidence_required")

    def test_degraded_candidate_fails_gate_and_cannot_be_promoted(self):
        # AR4 DoD: the AR3 degraded-profile control cannot be promoted in require mode.
        self._pin_enforcement("require")
        client = self._admin_client(user_suffix="degraded")
        pack_name = self._seed_graded_corpus_and_pack()
        self._pin_embed_texts()
        draft = self._create_draft(retrieval_override_config=dict(DEGRADED_RETRIEVAL_OVERRIDES))

        eval_response = client.post(
            "/admin/tuning/eval-runs",
            json={"draft_id": draft["id"], "pack_names": [pack_name], "sample_size": 5},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(eval_response.status_code, 200, msg=eval_response.text)
        eval_run = eval_response.json()["eval_run"]
        self.assertEqual(eval_run["gate_status"], "fail", msg=str(eval_run["gate_aggregates"]))

        promote_response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft["id"], "promotion_note": "Attempting degraded promote.", "eval_run_id": eval_run["id"]},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(promote_response.status_code, 422, msg=promote_response.text)
        self.assertEqual(promote_response.json()["detail"]["error"], "eval_gate_failed")

    def test_eval_promote_rollback_round_trip_persists_deltas(self):
        # AR4 re-run check: draft -> eval -> promote -> rollback with persisted deltas.
        self._pin_enforcement("require")
        client = self._admin_client(user_suffix="roundtrip")
        pack_name = self._seed_graded_corpus_and_pack()
        self._pin_embed_texts()

        baseline_response = client.post(
            "/admin/tuning/eval-runs",
            json={"draft_id": None, "pack_names": [pack_name], "sample_size": 5},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(baseline_response.status_code, 200, msg=baseline_response.text)
        self.assertEqual(baseline_response.json()["eval_run"]["run_label"], "live")

        draft = self._create_draft()
        candidate_response = client.post(
            "/admin/tuning/eval-runs",
            json={"draft_id": draft["id"], "pack_names": [pack_name], "sample_size": 5},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(candidate_response.status_code, 200, msg=candidate_response.text)
        candidate_run = candidate_response.json()["eval_run"]
        self.assertEqual(candidate_run["gate_status"], "pass", msg=str(candidate_run["gate_aggregates"]))
        self.assertIn("deltas_vs_live_baseline", candidate_run)
        self.assertIsNotNone(candidate_run["deltas_vs_live_baseline"]["recall_at_5"])

        promote_response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft["id"], "promotion_note": "Eval-gated promotion.", "eval_run_id": candidate_run["id"]},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(promote_response.status_code, 200, msg=promote_response.text)
        promoted = promote_response.json()
        evidence = promoted["eval_evidence"]
        self.assertEqual(evidence["eval_run_id"], candidate_run["id"])
        self.assertEqual(evidence["gate_status"], "pass")
        self.assertEqual(evidence["enforcement_mode"], "require")
        self.assertEqual(evidence["warnings"], [])
        self.assertIsNotNone(evidence["deltas_vs_live_baseline"]["mrr"])
        promoted_label = promoted["promoted_version"]["version_label"]

        rollback_response = client.post(
            "/admin/tuning/rollback",
            json={"version_label": promoted_label, "reason": "AR4 round-trip rollback.", "eval_run_id": candidate_run["id"]},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(rollback_response.status_code, 200, msg=rollback_response.text)
        self.assertEqual(rollback_response.json()["eval_evidence"]["eval_run_id"], candidate_run["id"])

        history = client.get("/admin/tuning/history", headers={"Authorization": "Bearer fake-token"}).json()
        promote_events = [
            event
            for event in history["promotion_events"]
            if event["action"] == "promote" and (event.get("eval_evidence_json") or {}).get("eval_run_id") == candidate_run["id"]
        ]
        self.assertTrue(promote_events, msg="promotion event must persist eval evidence")
        self.assertIn("deltas_vs_live_baseline", promote_events[0]["eval_evidence_json"])
        rollback_events = [
            event
            for event in history["promotion_events"]
            if event["action"] == "rollback" and (event.get("eval_evidence_json") or {}).get("eval_run_id") == candidate_run["id"]
        ]
        self.assertTrue(rollback_events, msg="rollback event must link eval evidence")

        runs_response = client.get(
            f"/admin/tuning/eval-runs?draft_id={draft['id']}", headers={"Authorization": "Bearer fake-token"}
        )
        self.assertTrue(any(run["id"] == candidate_run["id"] for run in runs_response.json()["eval_runs"]))

    def test_warn_mode_annotates_promotion_without_eval(self):
        self._pin_enforcement("warn")
        client = self._admin_client(user_suffix="warn")
        draft = self._create_draft()
        response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft["id"], "promotion_note": "Warn-mode promotion without evidence."},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(response.status_code, 200, msg=response.text)
        evidence = response.json()["eval_evidence"]
        self.assertEqual(evidence["enforcement_mode"], "warn")
        self.assertIn("promoted_without_eval", evidence["warnings"])
        self.assertIsNone(evidence["eval_run_id"])

        history = client.get("/admin/tuning/history", headers={"Authorization": "Bearer fake-token"}).json()
        annotated = [
            event
            for event in history["promotion_events"]
            if "promoted_without_eval" in ((event.get("eval_evidence_json") or {}).get("warnings") or [])
        ]
        self.assertTrue(annotated, msg="warn-mode promotion must be loudly annotated in history")

    def test_stale_eval_run_rejected_in_require_mode(self):
        from app.db.repo_tuning_configs import update_candidate_draft

        self._pin_enforcement("require")
        client = self._admin_client(user_suffix="stale")
        pack_name = self._seed_graded_corpus_and_pack()
        self._pin_embed_texts()
        draft = self._create_draft()
        eval_response = client.post(
            "/admin/tuning/eval-runs",
            json={"draft_id": draft["id"], "pack_names": [pack_name], "sample_size": 5},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(eval_response.status_code, 200, msg=eval_response.text)
        eval_run = eval_response.json()["eval_run"]

        update_candidate_draft(draft["id"], description="Changed after the eval run; evidence is stale.")
        promote_response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft["id"], "promotion_note": "Stale evidence.", "eval_run_id": eval_run["id"]},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(promote_response.status_code, 422, msg=promote_response.text)
        self.assertEqual(promote_response.json()["detail"]["error"], "stale_eval_run")

    def test_eval_run_mismatched_draft_rejected(self):
        self._pin_enforcement("require")
        client = self._admin_client(user_suffix="mismatch")
        pack_name = self._seed_graded_corpus_and_pack()
        self._pin_embed_texts()
        draft_a = self._create_draft()
        draft_b = self._create_draft()
        eval_response = client.post(
            "/admin/tuning/eval-runs",
            json={"draft_id": draft_a["id"], "pack_names": [pack_name], "sample_size": 5},
            headers={"Authorization": "Bearer fake-token"},
        )
        self.assertEqual(eval_response.status_code, 200, msg=eval_response.text)
        promote_response = client.post(
            "/admin/tuning/promote",
            json={"draft_id": draft_b["id"], "promotion_note": "Wrong draft evidence.", "eval_run_id": eval_response.json()["eval_run"]["id"]},
            headers={"Authorization": "Bearer fake-token", "X-Admin-Approval": "approved"},
        )
        self.assertEqual(promote_response.status_code, 422, msg=promote_response.text)
        self.assertEqual(promote_response.json()["detail"]["error"], "eval_run_draft_mismatch")
