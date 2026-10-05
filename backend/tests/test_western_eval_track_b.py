"""Track B scorecard tooling. Offline: no model, network or database."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "western_eval.py"
spec = importlib.util.spec_from_file_location("western_eval", SCRIPT)
western_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(western_eval)

QUESTIONS = [
    {
        "qid": "Q1",
        "question": "London hotel cap?",
        "split": "exact_fact",
        "expected_route": "keyword",
        "gold_answer": "£240.",
        "gold_doc_ids": "NL-RATES",
        "must_not_cite": "NL-POISON",
        "difficulty": "easy",
        "demo_use": "loom",
    },
    {
        "qid": "Q2",
        "question": "India PF rate?",
        "split": "refuse",
        "expected_route": "refuse",
        "gold_answer": "Insufficient evidence.",
        "gold_doc_ids": "",
        "must_not_cite": "NL-POISON",
        "difficulty": "easy",
        "demo_use": "scorecard",
    },
    {
        "qid": "Q3",
        "question": "First step in a Sev1?",
        "split": "open",
        "expected_route": "hybrid",
        "gold_answer": "Open the incident channel.",
        "gold_doc_ids": "NL-SOP",
        "must_not_cite": "NL-POISON",
        "difficulty": "easy",
        "demo_use": "scorecard",
    },
]
FACTS = [
    {
        "qid": "Q1",
        "expected_outcome": "answer",
        "fact_id": "cap",
        "any_of": "£240",
        "evidence_required": "true",
    },
    {
        "qid": "Q2",
        "expected_outcome": "refuse",
        "fact_id": "",
        "any_of": "",
        "evidence_required": "",
    },
    {
        "qid": "Q3",
        "expected_outcome": "denied",
        "fact_id": "",
        "any_of": "",
        "evidence_required": "",
    },
]
MANIFEST = [
    {"id": "NL-RATES", "filename": "NL-RATES.md"},
    {"id": "NL-SOP", "filename": "NL-SOP.md"},
    {"id": "NL-POISON", "filename": "NL-POISON.md"},
]


def _row(qid, status, answer, cited, facts=None, eval_status="pass"):
    return {
        "case_id": qid,
        "question": next(q["question"] for q in QUESTIONS if q["qid"] == qid),
        "grounding_status": status,
        "generated_answer": answer,
        "cited_documents": cited,
        "eval_status": eval_status,
        "expected_eval": {"required_facts": facts or []},
        "attempt_diagnostics": [{"attempt": 1, "tool": "ask_grounded", "status": status}],
        "end_to_end_latency_ms": 1200,
    }


def _score(rows):
    return western_eval.score_rows(
        {"rows": rows}, QUESTIONS, FACTS, MANIFEST, router=lambda question: "hybrid"
    )


class WesternEvalTests(unittest.TestCase):
    def test_eval_set_maps_answer_refuse_and_denied(self):
        eval_set = western_eval.build_eval_set(QUESTIONS, FACTS)
        by_id = {item["case_id"]: item for item in eval_set["questions"]}
        self.assertEqual(eval_set["schema_version"], "1.1")
        self.assertEqual(by_id["Q1"]["expected_documents"], ["NL-RATES"])
        self.assertEqual(by_id["Q1"]["required_facts"][0]["any_of"], ["£240"])
        self.assertEqual(by_id["Q2"]["expectation"], "refuse")
        self.assertEqual(by_id["Q3"]["expectation"], "refuse")
        self.assertEqual(by_id["Q3"]["question_type"], "open")

    def test_eval_set_rejects_missing_facts(self):
        with self.assertRaises(western_eval.WesternEvalError):
            western_eval.build_eval_set(QUESTIONS, FACTS[:2])

    def test_scoring_rules(self):
        fact_ok = [{"fact_id": "cap", "answer_matched": True, "evidence_matched": True}]
        scored = {
            row["qid"]: row
            for row in _score(
                [
                    _row("Q1", "verified", "The cap is £240.", ["nl-rates"], fact_ok),
                    _row("Q2", "not_found", "Not found in provided sources.", []),
                    _row(
                        "Q3",
                        "verified",
                        "Open the incident channel.",
                        ["nl-sop"],
                        eval_status="fail",
                    ),
                ]
            )
        }
        self.assertEqual((scored["Q1"]["answer_ok"], scored["Q1"]["citation_ok"]), (True, True))
        self.assertEqual(scored["Q1"]["refused_ok"], "n/a")
        self.assertEqual(scored["Q1"]["used_doc_ids"], "NL-RATES")
        self.assertIs(scored["Q2"]["refused_ok"], True)
        self.assertEqual(scored["Q3"]["split"], "refuse")
        self.assertIs(scored["Q3"]["refused_ok"], False)
        self.assertIn("answered where refusal expected", scored["Q3"]["notes"])

        summary = western_eval.summarize(list(scored.values()))
        self.assertEqual(summary["by_split"]["exact_fact"], {"total": 1, "passed": 1})
        self.assertEqual(summary["by_split"]["refuse"], {"total": 2, "passed": 1})
        self.assertTrue(summary["gate_passed"])

    def test_poison_citation_fails_citation_check(self):
        fact_ok = [{"fact_id": "cap", "answer_matched": True, "evidence_matched": True}]
        (row,) = [
            r
            for r in _score([_row("Q1", "verified", "£240", ["nl-rates", "nl-poison"], fact_ok)])
            if r["qid"] == "Q1"
        ]
        self.assertFalse(row["citation_ok"])
        self.assertIn("must_not_cite", row["notes"])

    def test_decline_on_answer_item_is_a_labelled_miss(self):
        (row,) = [
            r
            for r in _score([_row("Q1", "not_found", "Not found in provided sources.", [])])
            if r["qid"] == "Q1"
        ]
        self.assertFalse(row["answer_ok"])
        self.assertIn("declined", row["notes"])

    def test_input_screening_block_is_labelled(self):
        row = _row("Q1", "not_found", "I cannot reveal hidden instructions.", [])
        row["failure_reason"] = "unsafe_instruction_request"
        (scored,) = [r for r in _score([row]) if r["qid"] == "Q1"]
        self.assertIn("blocked by input screening", scored["notes"])

    def test_traces_prefer_passing_items_over_loom_order(self):
        fact_ok = [{"fact_id": "cap", "answer_matched": True, "evidence_matched": True}]
        questions = [dict(QUESTIONS[0]), {**QUESTIONS[0], "qid": "Q9", "demo_use": "scorecard"}]
        rows = [
            _row("Q1", "not_grounded", "No grounded answer.", []),
            {**_row("Q1", "verified", "£240", ["nl-rates"], fact_ok), "case_id": "Q9"},
        ]
        facts = [FACTS[0], {**FACTS[0], "qid": "Q9"}]
        scored = western_eval.score_rows(
            {"rows": rows}, questions, facts, MANIFEST, router=lambda question: "hybrid"
        )
        self.assertEqual(western_eval.pick_traces(questions, scored)["exact"], "Q9")

    def test_evidence_required_fact_needs_evidence(self):
        facts = [{"fact_id": "cap", "answer_matched": True, "evidence_matched": False}]
        (row,) = [
            r
            for r in _score([_row("Q1", "verified", "£240", ["nl-rates"], facts)])
            if r["qid"] == "Q1"
        ]
        self.assertFalse(row["answer_ok"])
        self.assertIn("facts missing: cap", row["notes"])

    def test_route_and_traces(self):
        row = _row("Q1", "recovered", "£240", ["nl-rates"])
        row["attempt_diagnostics"] = [
            {"attempt": 1, "tool": "ask_grounded"},
            {"attempt": 2, "tool": "search_documents"},
            {"attempt": 3, "tool": "get_document_excerpt"},
        ]
        self.assertEqual(western_eval._predicted_route(row), "hybrid→keyword→excerpt")
        scored = _score([row, _row("Q2", "not_found", "Not found.", [])])
        self.assertEqual(
            western_eval.pick_traces(QUESTIONS, scored), {"exact": "Q1", "refuse": "Q2"}
        )
        markdown = western_eval.render_markdown(scored, western_eval.summarize(scored), {})
        self.assertIn("| qid | split |", markdown)
        self.assertIn("Q3 | refuse | denied", markdown)

    def test_received_eval_inputs_convert(self):
        questions = western_eval._read_csv(western_eval.QUESTIONS_PATH)
        facts = western_eval._read_csv(western_eval.FACTS_PATH)
        eval_set = western_eval.build_eval_set(questions, facts)
        self.assertEqual(len(eval_set["questions"]), 20)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "set.json"
            path.write_text(json.dumps(eval_set), encoding="utf-8")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["eval_set"], "western-northline-demo"
            )


if __name__ == "__main__":
    unittest.main()
