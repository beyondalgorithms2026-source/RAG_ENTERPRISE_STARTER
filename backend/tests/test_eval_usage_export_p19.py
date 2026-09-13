from __future__ import annotations

import unittest

from app.eval.usage_export import UsageExportError, build_usage_export


class EvalUsageExportP19Tests(unittest.TestCase):
    def _report(self):
        return {
            "rows": [
                {"case_id": "A", "backend_request_ids": ["r1", "r2"]},
                {"case_id": "B", "backend_request_ids": ["r3", "r1"]},
            ]
        }

    def test_aggregates_recovery_requests_without_exporting_content(self):
        payload = build_usage_export(
            self._report(),
            usage_rows={
                "r1": {
                    "cost_usd": 0.001,
                    "generation_call_count": 1,
                    "total_tokens": 100,
                    "any_estimated": False,
                },
                "r2": {
                    "cost_usd": 0.002,
                    "generation_call_count": 2,
                    "total_tokens": 220,
                    "any_estimated": True,
                },
            },
        )
        self.assertEqual(payload["query_count"], 2)
        self.assertEqual(payload["backend_request_count"], 3)
        self.assertEqual(payload["generation_request_count"], 2)
        self.assertEqual(payload["generation_call_count"], 3)
        self.assertAlmostEqual(payload["total_cost_usd"], 0.003)
        self.assertEqual(payload["requests"][2]["cost_usd"], 0.0)
        serialized = str(payload).lower()
        self.assertNotIn("question", serialized)
        self.assertNotIn("prompt", serialized)
        self.assertNotIn("actor", serialized)

    def test_requires_request_ids_on_every_case(self):
        with self.assertRaisesRegex(UsageExportError, "backend_request_ids"):
            build_usage_export({"rows": [{"case_id": "A"}]}, usage_rows={})

    def test_rejects_report_without_any_backend_request(self):
        with self.assertRaisesRegex(UsageExportError, "no backend request ids"):
            build_usage_export(
                {"rows": [{"case_id": "A", "backend_request_ids": []}]}, usage_rows={}
            )


if __name__ == "__main__":
    unittest.main()
