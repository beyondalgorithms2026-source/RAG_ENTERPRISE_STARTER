from tests.smoke_test_base import *

import json

from app.eval.feedback_flywheel import (
    PROVENANCE,
    append_cases_to_pack,
    pack_passrate_trend,
    propose_cases_from_cluster,
    quarantine_summary,
    review_pack_case,
)
from app.eval.pack_builder import PACKS_DIR


class FeedbackFlywheelAR12Tests(SmokeTestBase):
    """AR12: operational feedback becomes regression protection — a thumbs-down
    event travels into a pack, is quarantined, reviewed, then gates."""

    def _temp_pack(self):
        name = f"ar12_{uuid4().hex[:8]}"
        path = PACKS_DIR / f"pack_{name}.json"
        path.write_text(json.dumps({"pack": name, "corpus": "general", "builder_version": "ar12-test", "case_counts": {"total": 0}, "cases": []}) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return name

    def _seed_chunk_and_thumbsdown(self):
        suffix = uuid4().hex[:8]
        token = f"flywheel{suffix}"
        question = f"What is the {token} escalation policy?"
        with engine.begin() as conn:
            source_id = conn.execute(
                text(
                    """
                    INSERT INTO sources (file_name, storage_path, source_type, sensitivity_label, hash_sha256,
                        file_size_bytes, ingestion_status, enrichment_status, source_metadata_json)
                    VALUES (:f, :p, 'pdf', 'public', :h, 100, 'embedded', 'not_started', '{}'::jsonb)
                    RETURNING id
                    """
                ),
                {"f": f"ar12-{suffix}.pdf", "p": f"tests/ar12-{suffix}.pdf", "h": (suffix + "ar12") * 4},
            ).scalar_one()
        self.addCleanup(self._delete_retrieval_records, [source_id])
        insert_chunks(source_id, [{"chunk_index": 0, "heading": "Escalation", "section_path": "p:0", "chunk_text": f"{token} escalation policy: contact the duty manager within one hour.", "token_count": 10, "locator_json": {}, "provenance_json": {}}])
        with engine.connect() as conn:
            chunk_id = conn.execute(text("SELECT id FROM chunks WHERE source_id = :s ORDER BY chunk_index"), {"s": source_id}).scalar_one()
        update_chunk_embeddings([(chunk_id, basis_vector(1.0))])

        # A recorded trace that cited the chunk, then a thumbs-down event on it.
        request_id = f"ar12-req-{suffix}"
        from app.db.repo_traces import insert_trace
        from app.db.repo_query_mining import record_query_event

        insert_trace(
            request_id=request_id, question=question, requested_mode="hybrid", resolved_mode="hybrid",
            retrieval_path="hybrid", candidate_counts={}, fallback_reason=None, answer_path="llm",
            latency_ms={}, score_diagnostics=[], trace_json={"cited_chunk_ids": [chunk_id], "acl": {"accessed_doc_ids": [source_id]}},
            active_profiles={},
        )
        event_id = record_query_event(question=question, event_type="not_helpful", answer_path="llm", request_id=request_id, retrieval_mode="hybrid", feedback_type="not_helpful")
        self.addCleanup(self._delete_event, event_id, request_id)
        return question, chunk_id

    def _delete_event(self, event_id, request_id):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM query_events WHERE id = :id"), {"id": event_id})
            conn.execute(text("DELETE FROM retrieval_traces WHERE request_id = :r"), {"r": request_id})
            conn.execute(text("DELETE FROM query_failure_clusters WHERE label = (SELECT label FROM query_failure_clusters WHERE id = id LIMIT 0)"))

    def _cluster_for(self, question):
        from app.db.repo_query_mining import build_failure_clusters

        clusters = build_failure_clusters()
        from app.db.repo_query_mining import normalize_question

        target = normalize_question(question)
        match = next((c for c in clusters if normalize_question(c["label"]) == target or target in json.dumps(c.get("sample_questions_json") or c.get("sample_questions") or [])), None)
        self.assertIsNotNone(match, msg="failure cluster not built from thumbs-down event")
        self.addCleanup(self._delete_cluster, match["id"])
        return match["id"]

    def _delete_cluster(self, cluster_id):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM query_failure_clusters WHERE id = :id"), {"id": cluster_id})

    def test_full_path_thumbsdown_to_gating_eval_case(self):
        question, chunk_id = self._seed_chunk_and_thumbsdown()
        cluster_id = self._cluster_for(question)

        # Propose — prefilled from the cited chunk in the trace.
        proposed = propose_cases_from_cluster(cluster_id)
        self.assertTrue(proposed["proposed_cases"])
        case = proposed["proposed_cases"][0]
        self.assertEqual(case["provenance"], PROVENANCE)
        self.assertEqual(case["review_status"], "unreviewed")
        self.assertIn(str(chunk_id), case["relevant"])  # evidence prefilled

        # Append — quarantined into the pack.
        pack_name = self._temp_pack()
        append_cases_to_pack(pack_name, proposed["proposed_cases"])
        summary = quarantine_summary(pack_name)
        self.assertEqual(summary["by_review_status"].get("unreviewed"), len(proposed["proposed_cases"]))

        # Before review: the case does NOT gate (quarantine guardrail).
        import app.core_rag.retrieval as retrieval_module

        original_embed = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            from app.eval.pack_eval import run_pack_eval

            before = run_pack_eval(pack_paths=[PACKS_DIR / f"pack_{pack_name}.json"], modes=("hybrid",), gate_mode="hybrid")
            self.assertEqual(before["packs"][0]["gating_case_count"], 0)

            # Review + label → reviewed (gates).
            review_pack_case(pack_name, case["id"], relevant={str(chunk_id): 3}, reviewer="reviewer@example.com")

            after = run_pack_eval(pack_paths=[PACKS_DIR / f"pack_{pack_name}.json"], modes=("hybrid",), gate_mode="hybrid")
            self.assertEqual(after["packs"][0]["gating_case_count"], 1)
            gated_ids = [c["case_id"] for c in after["packs"][0]["cases"] if c["mode"] == "hybrid" and c["review_status"] != "unreviewed"]
            self.assertIn(case["id"], gated_ids)
        finally:
            retrieval_module.embed_texts = original_embed

    def test_reviewed_case_requires_relevance_map(self):
        question, chunk_id = self._seed_chunk_and_thumbsdown()
        cluster_id = self._cluster_for(question)
        pack_name = self._temp_pack()
        append_cases_to_pack(pack_name, propose_cases_from_cluster(cluster_id)["proposed_cases"])
        case_id = quarantine_summary(pack_name)["quarantined_feedback_cases"][0]["id"]
        with self.assertRaisesRegex(ValueError, "non-empty graded relevance"):
            review_pack_case(pack_name, case_id, relevant={}, review_status="reviewed")

    def test_passrate_trend_reads_eval_run_history(self):
        trend = pack_passrate_trend()
        self.assertIn("points", trend)
        self.assertIn("overall_pass_rate", trend)
        for point in trend["points"]:
            self.assertIn(point["gate_status"], {"pass", "fail"})
            self.assertIn("cumulative_pass_rate", point)
