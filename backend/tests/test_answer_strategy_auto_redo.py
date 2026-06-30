import json
from types import SimpleNamespace
import unittest

import app.core_rag.answering as answering_module
import app.core_rag.answer_strategy as strategy_module
from app.core_rag.answering import AskRequest
from app.core_rag.answer_strategy import select_answer_strategy, try_structured_aggregation
from app.core_rag.retrieval import SearchRequest, SearchResponse, SearchResultItem, _resolve_query_text


class AnswerStrategyAutoRedoTests(unittest.TestCase):
    def test_selects_structured_aggregation_for_sales_by_region(self):
        decision = select_answer_strategy("What is total sales by region?")

        self.assertEqual(decision.strategy, "structured_aggregation")
        self.assertEqual(decision.answer_safety, "requires_complete_table")
        self.assertTrue(decision.aggregation)

    def test_refuses_aggregation_without_complete_xlsx_sheet(self):
        result = try_structured_aggregation(
            question="What is total sales by region?",
            raw_chunks=[],
            make_citation=lambda part, heading: None,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.debug["answer_safety"], "insufficient_evidence")
        self.assertEqual(result.citations, [])
        self.assertIn("cannot safely calculate", result.answer)

    def test_computes_total_sales_by_region_from_complete_sheet_part(self):
        original_list_source_parts = strategy_module.list_source_parts
        part = SimpleNamespace(
            id=20,
            source_id=10,
            part_type="sheet",
            title="Sales",
            locator_json={"sheet": "Sales", "range": "A1:B3"},
            content_text="\n".join(
                [
                    "Row 1: A1=Region | B1=Sales",
                    "Row 2: A2=East | B2=100",
                    "Row 3: A3=West | B3=250",
                    "Row 4: A4=East | B4=50",
                ]
            ),
        )
        chunk = SimpleNamespace(source_id=10, source_part_id=20, source_type="xlsx")
        try:
            strategy_module.list_source_parts = lambda source_id: [part]
            result = try_structured_aggregation(
                question="What is total sales by region?",
                raw_chunks=[chunk],
                make_citation=lambda source_part, heading: {"source_part_id": source_part.id, "heading": heading},
            )
        finally:
            strategy_module.list_source_parts = original_list_source_parts

        self.assertEqual(result.debug["answer_safety"], "computed_from_complete_table")
        self.assertIn("East: 150", result.answer)
        self.assertIn("West: 250", result.answer)
        self.assertEqual(result.citations[0]["source_part_id"], 20)

    def test_retries_top_chunk_when_llm_says_not_found_despite_retrieved_evidence(self):
        original_perform_search = answering_module.perform_search
        original_generate_answer = answering_module.generate_answer
        original_maybe_gate_sensitive_answer = answering_module._maybe_gate_sensitive_answer
        calls = []

        answering_module.perform_search = lambda request: SearchResponse(
            results=[
                SearchResultItem(
                    chunk_id=101,
                    source_id=11,
                    source_part_id=None,
                    file_name="walmart.txt",
                    source_type="txt",
                    heading="Sam Walton biography",
                    locator=None,
                    snippet="Sam Walton enrolled himself in an IBM seminar in Poughkeepsie, New York, to learn how computing technology could be used in business.",
                    score=1.0,
                )
            ],
            latency_ms=1,
            mode="hybrid",
            debug_info={"request_id": "retry-unit"},
        )

        def fake_generate_answer(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                return {"success": True, "content": json.dumps({"answer": "Not found in provided sources.", "citations": []})}
            return {
                "success": True,
                "content": json.dumps(
                    {
                        "answer": "Sam Walton enrolled himself in an IBM seminar in Poughkeepsie, New York [S1].",
                        "citations": ["S1"],
                    }
                ),
            }

        answering_module.generate_answer = fake_generate_answer
        answering_module._maybe_gate_sensitive_answer = lambda **kwargs: None
        try:
            response = answering_module._perform_ask_internal(
                AskRequest(question="What seminar did Sam Walton enroll himself in in Poughkeepsie New York?", mode="hybrid")
            )
        finally:
            answering_module.perform_search = original_perform_search
            answering_module.generate_answer = original_generate_answer
            answering_module._maybe_gate_sensitive_answer = original_maybe_gate_sensitive_answer

        self.assertEqual(len(calls), 2)
        self.assertIn("IBM seminar", response.answer)
        self.assertEqual(response.debug_info["answer_generation_path"], "evidence_repair")
        self.assertEqual(response.citations[0].chunk_id, 101)

    def test_repair_can_use_boosted_non_top_chunk(self):
        original_perform_search = answering_module.perform_search
        original_generate_answer = answering_module.generate_answer
        original_maybe_gate_sensitive_answer = answering_module._maybe_gate_sensitive_answer
        calls = []

        answering_module.perform_search = lambda request: SearchResponse(
            results=[
                SearchResultItem(
                    chunk_id=201,
                    source_id=11,
                    source_part_id=None,
                    file_name="walmart.txt",
                    source_type="txt",
                    heading="Ben Franklin store",
                    locator=None,
                    snippet="Sam Walton studied Ben Franklin store layouts and merchandising.",
                    score=1.0,
                ),
                SearchResultItem(
                    chunk_id=202,
                    source_id=11,
                    source_part_id=None,
                    file_name="walmart.txt",
                    source_type="txt",
                    heading="Ben Franklin rent",
                    locator=None,
                    snippet="No one paid 5 percent of sales for rent on a Ben Franklin store.",
                    score=0.9,
                ),
            ],
            latency_ms=1,
            mode="keyword",
            debug_info={
                "request_id": "rent-repair-unit",
                "exact_numeric_boost": {"hits": [{"chunk_id": 202, "score": 2.4, "terms": ["rent", "sales"]}]},
            },
        )

        def fake_generate_answer(system_prompt, user_prompt):
            calls.append((system_prompt, user_prompt))
            if len(calls) == 1:
                return {"success": True, "content": json.dumps({"answer": "Not found in provided sources.", "citations": []})}
            self.assertIn("5 percent of sales", user_prompt)
            return {
                "success": True,
                "content": json.dumps(
                    {
                        "answer": "Sam Walton's first Ben Franklin cost 5 percent of sales for rent [S2].",
                        "citations": ["S2"],
                    }
                ),
            }

        answering_module.generate_answer = fake_generate_answer
        answering_module._maybe_gate_sensitive_answer = lambda **kwargs: None
        try:
            response = answering_module._perform_ask_internal(
                AskRequest(question="What Percentage of Rent to Sales did Sam Waltons first Ben Franklin cost?", mode="keyword")
            )
        finally:
            answering_module.perform_search = original_perform_search
            answering_module.generate_answer = original_generate_answer
            answering_module._maybe_gate_sensitive_answer = original_maybe_gate_sensitive_answer

        self.assertEqual(len(calls), 2)
        self.assertIn("5 percent of sales", response.answer)
        self.assertEqual(response.debug_info["answer_generation_path"], "evidence_repair")
        self.assertEqual(response.citations[0].chunk_id, 202)

    def test_search_instruction_is_additive_not_custom_override(self):
        request = SearchRequest(
            question="What Percentage of Rent to Sales did Sam Waltons first Ben Franklin cost?",
            mode="keyword",
            search_instruction="give preference to keyword rent and ben franklin",
        )

        self.assertIsNone(request.custom_query)
        resolved = _resolve_query_text(request)
        self.assertIn("What Percentage of Rent to Sales", resolved)
        self.assertIn("give preference to keyword rent", resolved)

    def test_custom_query_remains_override(self):
        request = SearchRequest(
            question="original question",
            mode="keyword",
            custom_query="custom retrieval query",
            search_instruction="additive instruction",
        )

        self.assertEqual(_resolve_query_text(request), "custom retrieval query")

    def test_no_retrieved_chunks_still_returns_safe_not_found(self):
        original_perform_search = answering_module.perform_search
        original_generate_answer = answering_module.generate_answer
        answering_module.perform_search = lambda request: SearchResponse(
            results=[],
            latency_ms=1,
            mode="hybrid",
            debug_info={"request_id": "no-evidence-unit"},
        )
        answering_module.generate_answer = lambda system_prompt, user_prompt: {
            "success": True,
            "content": json.dumps({"answer": "Unsupported answer", "citations": []}),
        }
        try:
            response = answering_module._perform_ask_internal(AskRequest(question="What seminar did Sam Walton enroll in?", mode="hybrid"))
        finally:
            answering_module.perform_search = original_perform_search
            answering_module.generate_answer = original_generate_answer

        self.assertEqual(response.answer, "Not found in provided sources.")
        self.assertEqual(response.used_chunks_count, 0)
        self.assertEqual(response.citations, [])


if __name__ == "__main__":
    unittest.main()
