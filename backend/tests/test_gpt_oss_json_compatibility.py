import unittest
from unittest.mock import patch

from app.core_rag.answering import _parse_llm_json, _repair_llm_json
from app.llm.client import generate_answer
from app.llm.prompts import generate_json_repair_prompt
from app.profiles.models import LLMProfileConfig


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"answer":"Supported [S1].","citations":["S1"]}',
                    }
                }
            ]
        }


class _FakeClient:
    def __init__(self, recorder, **_kwargs):
        self.recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, json, headers):
        self.recorder.update({"url": url, "json": json, "headers": headers})
        return _FakeResponse()


class _FakeHttpx:
    class TimeoutException(Exception):
        pass

    def __init__(self, recorder):
        self.recorder = recorder

    def Client(self, **kwargs):
        return _FakeClient(self.recorder, **kwargs)


class GptOssJsonCompatibilityTests(unittest.TestCase):
    def test_parser_accepts_fenced_json(self):
        parsed = _parse_llm_json(
            '```json\n{"answer":"Supported [S1].","citations":["S1"]}\n```'
        )
        self.assertEqual(parsed["answer"], "Supported [S1].")
        self.assertEqual(parsed["citations"], ["S1"])

    def test_parser_extracts_balanced_json_after_reasoning(self):
        parsed = _parse_llm_json(
            'I will format the result now.\n{"answer":"A brace { remains text } [S1].","citations":["S1"]}\nDone.'
        )
        self.assertEqual(parsed["citations"], ["S1"])
        self.assertIn("brace { remains text }", parsed["answer"])

    def test_parser_rejects_wrong_schema_and_truncated_json(self):
        self.assertIsNone(_parse_llm_json('{"answer":42,"citations":["S1"]}'))
        self.assertIsNone(_parse_llm_json('{"answer":"Incomplete","citations":["S1"]'))

    def test_repair_prompt_includes_question_context_and_valid_ids(self):
        prompt = generate_json_repair_prompt(
            question="What is the policy?",
            context_blocks=[
                {
                    "citation_id": "S1",
                    "file_name": "policy.txt",
                    "heading": "Policy",
                    "locator": "line 1",
                    "snippet": "The policy is active.",
                }
            ],
            invalid_content="The policy is active [S1].",
        )
        self.assertIn("What is the policy?", prompt)
        self.assertIn("VALID CITATION IDS: S1", prompt)
        self.assertIn("The policy is active.", prompt)
        self.assertIn("INVALID RESPONSE TO REPAIR", prompt)

    def test_repair_call_preserves_grounding_context(self):
        captured = {}

        def fake_generate_answer(system_prompt, user_prompt):
            captured.update({"system_prompt": system_prompt, "user_prompt": user_prompt})
            return {
                "success": True,
                "content": 'Result: {"answer":"The policy is active [S1].","citations":["S1"]}',
            }

        with patch("app.core_rag.answering.generate_answer", side_effect=fake_generate_answer):
            parsed = _repair_llm_json(
                raw_content="The policy is active.",
                question="What is the policy?",
                context_blocks=[
                    {
                        "citation_id": "S1",
                        "file_name": "policy.txt",
                        "heading": "Policy",
                        "locator": "line 1",
                        "snippet": "The policy is active.",
                    }
                ],
            )

        self.assertEqual(parsed["citations"], ["S1"])
        self.assertIn("What is the policy?", captured["user_prompt"])
        self.assertIn("VALID CITATION IDS: S1", captured["user_prompt"])
        self.assertIn("The policy is active.", captured["user_prompt"])

    def test_gpt_oss_prompt_json_mode_forces_deterministic_payload(self):
        recorder = {}
        profile = LLMProfileConfig(
            provider="ollama",
            model="gpt-oss:20b-cloud",
            base_url="http://localhost:11434",
            temperature=1.4,
            top_p=0.9,
            structured_output_mode="prompt_json_only",
            reasoning_effort="none",
        )
        with patch("app.profiles.resolver.get_effective_llm", return_value=profile):
            with patch("app.llm.client._get_httpx", return_value=_FakeHttpx(recorder)):
                response = generate_answer("system", "user")

        self.assertTrue(response["success"])
        self.assertEqual(recorder["json"]["temperature"], 0.0)
        self.assertEqual(recorder["json"]["reasoning_effort"], "none")
        self.assertNotIn("response_format", recorder["json"])

    def test_native_json_mode_keeps_response_format(self):
        recorder = {}
        profile = LLMProfileConfig(
            provider="ollama",
            model="llama3.2:3b",
            base_url="http://localhost:11434",
            temperature=0.3,
            structured_output_mode="native_json",
        )
        with patch("app.profiles.resolver.get_effective_llm", return_value=profile):
            with patch("app.llm.client._get_httpx", return_value=_FakeHttpx(recorder)):
                response = generate_answer("system", "user")

        self.assertTrue(response["success"])
        self.assertEqual(recorder["json"]["temperature"], 0.3)
        self.assertEqual(recorder["json"]["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
