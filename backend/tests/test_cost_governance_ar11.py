from tests.smoke_test_base import *

import app.llm.client as llm_client
from app.llm.pricing import cost_usd, estimate_tokens, usage_from_counts, usage_from_texts
from app.llm.providers import AnthropicProvider, OpenAICompatibleProvider
from app.llm.usage import add_usage, current_usage, reset_usage


class PricingAR11Tests(SmokeTestBase):
    def test_token_estimator_and_cost(self):
        self.assertEqual(estimate_tokens("a" * 40), 10)
        self.assertEqual(cost_usd("gpt-4o-mini", 1000, 1000), round(0.00015 + 0.0006, 6))
        self.assertEqual(cost_usd("some-local-model", 1000, 1000), 0.0)  # unknown = free

    def test_estimated_usage_is_flagged(self):
        usage = usage_from_texts("gpt-4o", prompt_text="x" * 8, completion_text="y" * 4)
        self.assertTrue(usage["estimated"])
        self.assertEqual(usage["prompt_tokens"], 2)
        self.assertEqual(usage["completion_tokens"], 1)

    def test_reported_usage_is_not_flagged(self):
        usage = usage_from_counts("gpt-4o", prompt_tokens=100, completion_tokens=50, estimated=False)
        self.assertFalse(usage["estimated"])
        self.assertEqual(usage["total_tokens"], 150)


class ProviderUsageExtractionAR11Tests(SmokeTestBase):
    def test_openai_usage_parsed_when_present(self):
        provider = OpenAICompatibleProvider()
        self.assertEqual(provider.extract_usage({"usage": {"prompt_tokens": 12, "completion_tokens": 7}}), (12, 7))
        self.assertIsNone(provider.extract_usage({"choices": []}))

    def test_anthropic_usage_parsed(self):
        provider = AnthropicProvider()
        self.assertEqual(provider.extract_usage({"usage": {"input_tokens": 30, "output_tokens": 9}}), (30, 9))


class UsageAccumulatorAR11Tests(SmokeTestBase):
    def test_usage_accumulates_across_calls(self):
        reset_usage()
        add_usage(usage_from_counts("gpt-4o", prompt_tokens=10, completion_tokens=5))
        add_usage(usage_from_counts("gpt-4o", prompt_tokens=4, completion_tokens=2))
        agg = current_usage()
        self.assertEqual(agg["call_count"], 2)
        self.assertEqual(agg["total_tokens"], 21)


class GenerateAnswerUsageAR11Tests(SmokeTestBase):
    def _fake_httpx(self, payload):
        capture = {}

        class _Resp:
            def json(self):
                return payload

            def raise_for_status(self):
                pass

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, url, json=None, headers=None):
                capture["payload"] = json
                return _Resp()

        class _Httpx:
            TimeoutException = RuntimeError

            def Client(self, timeout=None):
                return _Client()

        return _Httpx(), capture

    def _pin_llm(self, llm):
        import app.profiles.resolver as resolver

        original = resolver.get_effective_llm
        resolver.get_effective_llm = lambda: llm
        self.addCleanup(lambda: setattr(resolver, "get_effective_llm", original))

    def test_generate_answer_returns_reported_usage(self):
        from app.profiles.models import LLMProfileConfig

        reset_usage()
        httpx, _ = self._fake_httpx({"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 20, "completion_tokens": 8}})
        original = llm_client._get_httpx
        llm_client._get_httpx = lambda: httpx
        self.addCleanup(lambda: setattr(llm_client, "_get_httpx", original))
        self._pin_llm(LLMProfileConfig(provider="openai", model="gpt-4o-mini", base_url="https://api.openai.example", api_key="k"))
        result = llm_client.generate_answer("sys", "user")
        self.assertTrue(result["success"])
        self.assertFalse(result["usage"]["estimated"])
        self.assertEqual(result["usage"]["total_tokens"], 28)
        self.assertEqual(current_usage()["total_tokens"], 28)

    def test_generate_answer_estimates_when_usage_absent(self):
        from app.profiles.models import LLMProfileConfig

        reset_usage()
        httpx, _ = self._fake_httpx({"choices": [{"message": {"content": "abcd"}}]})
        original = llm_client._get_httpx
        llm_client._get_httpx = lambda: httpx
        self.addCleanup(lambda: setattr(llm_client, "_get_httpx", original))
        self._pin_llm(LLMProfileConfig(provider="vllm", model="mistral", base_url="http://vllm.local"))
        result = llm_client.generate_answer("system prompt", "user prompt")
        self.assertTrue(result["usage"]["estimated"])
        self.assertGreater(result["usage"]["total_tokens"], 0)


class CostSummaryAndBudgetAR11Tests(SmokeTestBase):
    def setUp(self):
        super().setUp()
        self._seeded_ids = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        if self._seeded_ids:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM generation_usage_events WHERE id = ANY(:ids)"), {"ids": self._seeded_ids})

    def _seed(self, *, mode, model, cost, over_budget=False):
        from app.db.repo_generation_usage import record_generation_usage_event

        event = record_generation_usage_event(
            request_id=f"ar11-{uuid4().hex[:8]}",
            provider="openai",
            model=model,
            retrieval_mode=mode,
            answer_path="llm",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated=False,
            cost_usd=cost,
            latency_ms=1200,
            call_count=1,
            over_budget=over_budget,
        )
        self._seeded_ids.append(event["id"])
        return event

    def test_cost_summary_distinguishes_deep_research_from_fast_mode(self):
        # AR11 DoD: an operator can answer "deep research vs fast mode cost".
        self._seed(mode="deep_research", model="gpt-4o", cost=0.05)
        self._seed(mode="deep_research", model="gpt-4o", cost=0.05)
        self._seed(mode="hybrid", model="gpt-4o", cost=0.01)
        from app.db.repo_generation_usage import cost_summary

        summary = cost_summary(group_by="retrieval_mode")
        buckets = {b["bucket"]: b for b in summary["buckets"]}
        self.assertIn("deep_research", buckets)
        self.assertIn("hybrid", buckets)
        self.assertGreater(float(buckets["deep_research"]["total_cost_usd"]), float(buckets["hybrid"]["total_cost_usd"]))
        self.assertEqual(int(buckets["deep_research"]["request_count"]), 2)

    def test_budget_alert_flag_recorded(self):
        event = self._seed(mode="hybrid", model="gpt-4o", cost=0.99, over_budget=True)
        self.assertTrue(event["over_budget"])
        from app.db.repo_generation_usage import cost_summary

        summary = cost_summary(group_by="model")
        gpt = next(b for b in summary["buckets"] if b["bucket"] == "gpt-4o")
        self.assertGreaterEqual(int(gpt["over_budget_count"]), 1)
