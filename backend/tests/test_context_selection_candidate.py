import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core_rag.context_selection import bounded_excerpt, compound_question, select_candidates


def chunk(i, heading, text):
    return SimpleNamespace(
        chunk_id=i,
        source_id=1,
        source_part_id=None,
        heading=heading,
        snippet=text,
        file_name="policy.md",
        source_type="md",
        locator=heading,
        freshness=None,
    )


class CandidateContextTests(unittest.TestCase):
    def test_real_manual_trigger_row_survives_table_shortening(self):
        import re
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2]
            / "corpus/source_documents/northwind-operations-manual-v3.2.md"
        ).read_text()
        definitions = re.search(r"^## 1.2 Definitions\n(.*?)^## 1.3 ", source, re.M | re.S)[0]
        result = bounded_excerpt(
            definitions, question="Is that a Temperature Excursion?", cap=1200
        )
        self.assertIn("more than 5 consecutive minutes", result)
        self.assertIn("|Term|Defined meaning|", result)
        self.assertLessEqual(len(result), 1200)

    def test_ordered_list_is_complete_or_excluded(self):
        sequence = "1. Stop safely.\n\n2. Call emergency services.\n\n3. Notify Fleet Control."
        result = bounded_excerpt(
            "Unrelated filler. " * 100 + "\n\n" + sequence,
            question="List the ordered Fleet steps",
            cap=100,
        )
        self.assertIn(sequence, result)
        self.assertEqual(bounded_excerpt(sequence, question="Fleet", cap=30), "")

    def test_exception_survives_long_table(self):
        text = (
            "Drivers must not operate a vehicle with a safety-critical defect. "
            + "Inspection table |" * 300
            + ". "
        )
        exception = "A safety-critical vehicle may move less than 500 metres to leave live traffic if this can be done safely."
        result = bounded_excerpt(
            text + exception, question="May a safety-critical vehicle move at all?", cap=4000
        )
        self.assertIn(exception, result)
        self.assertLessEqual(len(result), 4000)
        self.assertNotIn("excep", result[-6:])

    def test_indivisible_oversized_unit_is_not_cut(self):
        self.assertEqual(bounded_excerpt("x" * 100, question="x", cap=50), "")

    def test_late_operative_section_is_selected(self):
        headings = [
            "6.4 Disciplinary Framework",
            "Appendix Amendment Log",
            "Document ownership",
            "6.3 Substance Testing",
            "Purpose and Scope",
            "Retention Schedule",
            "Definitions",
            "5.5.1 Accident response",
        ]
        chunks = [chunk(i, h, h + " evidence.") for i, h in enumerate(headings)]
        selected, trace = select_candidates(
            chunks,
            question="Which sections jointly govern a post-accident substance test and conduct process?",
            limit=6,
        )
        self.assertTrue({0, 3, 7} <= {c.chunk_id for c in selected})
        self.assertTrue(any(d["reason"] == "selection_limit" for d in trace))

    def test_duplicate_suppression_does_not_fetch_other_sources(self):
        selected, trace = select_candidates(
            [chunk(1, "a", "Same."), chunk(2, "a", "Same."), chunk(3, "b", "Other.")],
            question="a",
            limit=3,
        )
        self.assertEqual([c.chunk_id for c in selected], [1, 3])
        self.assertEqual(sum(d["reason"] == "duplicate" for d in trace), 1)

    def test_complete_shorter_later_chunk_fits_after_oversized_one(self):
        from app.core.config import settings
        from app.core_rag.answering import _build_context_blocks

        chunks = [
            chunk(1, "first", "A" * 80 + "."),
            chunk(2, "large", "B" * 80 + "."),
            chunk(3, "later", "A complete short rule."),
        ]
        trace = []
        with (
            patch.object(settings, "ANSWER_CONTEXT_SELECTION_ENABLED", True),
            patch.object(settings, "ANSWER_CONTEXT_CHUNK_CAP_CHARS", 100),
            patch("app.core_rag.answering.MAX_TOTAL_CONTEXT_CHARS", 110),
        ):
            blocks = _build_context_blocks(chunks, question="rule", decisions=trace)
        self.assertEqual([b["chunk_id"] for b in blocks], [1, 3])
        self.assertEqual([b["citation_id"] for b in blocks], ["S1", "S2"])
        self.assertEqual(blocks[1]["snippet"], "A complete short rule.")
        self.assertTrue(any(d["reason"] == "total_budget_exclusion" for d in trace))

    def test_candidate_prompt_hash_and_default_compatibility(self):
        from app.core.config import settings
        from app.llm.prompt_registry import load_prompt
        from app.llm.prompts import SYSTEM_PROMPT, effective_system_prompt

        self.assertIn("governing trigger", load_prompt("starter_answer", candidate=True))
        with patch.object(settings, "ANSWER_PROMPT_CANDIDATE", False):
            self.assertEqual(effective_system_prompt(), SYSTEM_PROMPT)
        with patch.object(settings, "ANSWER_PROMPT_CANDIDATE", True):
            self.assertIn("strict versus inclusive", effective_system_prompt())

    def test_only_compound_questions_are_widened(self):
        self.assertTrue(compound_question("Which sections jointly govern this process?"))
        self.assertFalse(compound_question("What is the meal allowance?"))
