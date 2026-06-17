from tests.smoke_test_base import *

import json
from pathlib import Path

from app.eval.metrics import (
    aggregate_case_metrics,
    citation_faithfulness,
    evaluate_ranking,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.eval.pack_builder import PACKS_DIR, is_junk_mined_question, synthesize_question_variants
from app.eval.pack_eval import DEGRADED_RETRIEVAL_OVERRIDES, evaluate_case, evaluate_gate


class EvalMetricsAR3Tests(SmokeTestBase):
    """AR3: graded metrics with exact-value unit tests (audit: no recall/MRR/nDCG existed)."""

    def test_recall_and_mrr_exact_values(self):
        grades = {1: 3, 2: 1, 9: 2}
        ranked = [5, 1, 7, 2, 8]
        self.assertAlmostEqual(recall_at_k(ranked, grades, 5), 2 / 3)
        self.assertAlmostEqual(recall_at_k(ranked, grades, 2), 1 / 3)
        self.assertAlmostEqual(reciprocal_rank(ranked, grades), 1 / 2)
        self.assertEqual(reciprocal_rank([5, 7], grades), 0.0)
        self.assertIsNone(recall_at_k(ranked, {}, 5))

    def test_ndcg_orders_graded_relevance(self):
        grades = {1: 3, 2: 1}
        perfect = ndcg_at_k([1, 2, 5], grades, 5)
        inverted = ndcg_at_k([2, 1, 5], grades, 5)
        self.assertAlmostEqual(perfect, 1.0)
        self.assertLess(inverted, perfect)
        self.assertGreater(inverted, 0.0)

    def test_citation_faithfulness_contract(self):
        grades = {1: 3, 2: 2}
        self.assertAlmostEqual(
            citation_faithfulness(cited_chunk_ids=[1, 99], relevant_grades=grades, answered_not_found=False), 0.5
        )
        self.assertEqual(citation_faithfulness(cited_chunk_ids=[], relevant_grades=grades, answered_not_found=False), 0.0)
        self.assertEqual(citation_faithfulness(cited_chunk_ids=[], relevant_grades={}, answered_not_found=True), 1.0)
        self.assertEqual(citation_faithfulness(cited_chunk_ids=[], relevant_grades=grades, answered_not_found=True), 0.0)

    def test_aggregation_skips_missing_values(self):
        aggregated = aggregate_case_metrics([{"mrr": 1.0}, {"mrr": 0.0}, {"mrr": None}])
        self.assertAlmostEqual(aggregated["mrr"], 0.5)


class PackBuilderAR3Tests(SmokeTestBase):
    def test_junk_mined_question_filter(self):
        self.assertTrue(is_junk_mined_question("missing payroll policy 19db69e6f66e4711a30547331e0763b1"))
        self.assertTrue(is_junk_mined_question("[redacted by retention policy]"))
        self.assertTrue(is_junk_mined_question("hi"))
        self.assertFalse(is_junk_mined_question("What are the termination clauses in the master agreement?"))

    def test_question_variants_are_grounded_and_distinct(self):
        variants = synthesize_question_variants(
            heading="Termination",
            chunk_text=(
                "Either party may terminate this agreement with ninety days written notice. "
                "Termination obligations include the return of confidential materials."
            ),
            file_name="msa.pdf",
        )
        styles = {variant["style"] for variant in variants}
        self.assertIn("lead_sentence", styles)
        self.assertIn("salient_terms", styles)
        self.assertTrue(all(variant["question"].strip() for variant in variants))

    def test_committed_flagship_pack_exists_with_100_plus_graded_cases(self):
        path = PACKS_DIR / "pack_general.json"
        self.assertTrue(path.exists(), msg="flagship pack missing; run python -m app.eval.pack_builder")
        pack = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(pack["case_counts"]["total"], 100)
        for case in pack["cases"][:50]:
            self.assertTrue(case["question"].strip())
            self.assertTrue(case["relevant"], msg=f"case {case['id']} has no graded relevance")
            self.assertIn(case["review_status"], {"auto_labeled", "unreviewed", "reviewed"})


class PackEvalGateAR3Tests(SmokeTestBase):
    """AR3 DoD: a deliberately degraded configuration must fail the gate a
    healthy configuration passes — proven deterministically on a seeded corpus."""

    def _seed_graded_corpus(self):
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
                {"f": f"ar3-gate-{suffix}.pdf", "p": f"tests/ar3-gate-{suffix}.pdf", "h": (suffix + "ar3") * 4},
            ).scalar_one()
        self.addCleanup(self._delete_retrieval_records, [source_id])
        token = f"gradedtoken{suffix}"
        insert_chunks(
            source_id,
            [
                {
                    "chunk_index": index,
                    "heading": f"Section {index}",
                    "section_path": f"page:{index}",
                    "chunk_text": f"{token} graded evidence passage number {index} about retrieval quality.",
                    "token_count": 9,
                    "locator_json": {"page": index},
                    "provenance_json": {"test": "ar3"},
                }
                for index in range(4)
            ],
        )
        with engine.connect() as conn:
            chunk_rows = conn.execute(
                text("SELECT id, chunk_index FROM chunks WHERE source_id = :s ORDER BY chunk_index"),
                {"s": source_id},
            ).fetchall()
        # All four chunks are relevant; descending similarity to the query vector.
        similarities = [0.95, 0.9, 0.85, 0.8]
        update_chunk_embeddings(
            [
                (chunk_id, basis_vector(similarities[index], (1 - similarities[index] ** 2) ** 0.5))
                for chunk_id, index in chunk_rows
            ]
        )
        cases = [
            {
                "id": f"ar3-case-{suffix}",
                "question": f"{token} graded evidence passage",
                "provenance": "synthetic_chunk_grounded",
                "review_status": "auto_labeled",
                "relevant": {str(chunk_id): (3 if index == 0 else 2) for chunk_id, index in chunk_rows},
            }
        ]
        return cases

    def test_degraded_profile_fails_gate_that_healthy_profile_passes(self):
        import app.core_rag.retrieval as retrieval_module
        from app.profiles.models import RetrievalProfileConfig

        cases = self._seed_graded_corpus()
        original_embed_texts = retrieval_module.embed_texts
        retrieval_module.embed_texts = lambda texts: [basis_vector(1.0) for _ in texts]
        try:
            healthy = [evaluate_case(case, mode="hybrid") for case in cases]
            degraded_profile = RetrievalProfileConfig(**DEGRADED_RETRIEVAL_OVERRIDES)
            original_resolver = retrieval_module.get_effective_retrieval
            retrieval_module.get_effective_retrieval = lambda: degraded_profile
            try:
                degraded = [evaluate_case(case, mode="hybrid") for case in cases]
            finally:
                retrieval_module.get_effective_retrieval = original_resolver
        finally:
            retrieval_module.embed_texts = original_embed_texts

        healthy_aggregates = aggregate_case_metrics(healthy)
        degraded_aggregates = aggregate_case_metrics(degraded)
        thresholds = {"recall_at_5": 0.6}
        self.assertEqual(evaluate_gate(healthy_aggregates, thresholds)["status"], "pass", msg=str(healthy_aggregates))
        self.assertEqual(evaluate_gate(degraded_aggregates, thresholds)["status"], "fail", msg=str(degraded_aggregates))
        self.assertLess(degraded_aggregates["recall_at_5"], healthy_aggregates["recall_at_5"])

    def test_unreviewed_cases_never_gate(self):
        aggregates_with_failures = {"recall_at_5": 0.0}
        gate = evaluate_gate(aggregates_with_failures, {"recall_at_5": 0.6})
        self.assertEqual(gate["status"], "fail")
        # Gate construction in run_pack_eval excludes unreviewed cases; the
        # filter is part of the runner contract:
        from app.eval.pack_eval import run_pack_eval
        import inspect

        self.assertIn('review_status"] != "unreviewed"', inspect.getsource(run_pack_eval))

    def test_committed_baseline_and_degraded_reference_reports(self):
        baseline_path = PACKS_DIR / "AR3_baseline_report.json"
        degraded_path = PACKS_DIR / "AR3_degraded_control_report.json"
        self.assertTrue(baseline_path.exists(), msg="baseline report missing; run python -m app.eval.pack_eval")
        self.assertTrue(degraded_path.exists(), msg="degraded report missing; run python -m app.eval.pack_eval --degraded")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        degraded = json.loads(degraded_path.read_text(encoding="utf-8"))
        self.assertEqual(baseline["gate"]["status"], "pass", msg=str(baseline["gate"]))
        self.assertEqual(degraded["gate"]["status"], "fail", msg=str(degraded["gate"]))
        self.assertIn("active_profiles", baseline)
        self.assertIn("metrics_by_mode", baseline["packs"][0])
