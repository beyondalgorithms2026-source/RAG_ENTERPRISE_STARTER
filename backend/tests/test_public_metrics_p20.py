from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.api.public_metrics import build_live_metrics_snapshot


def _sources(count: int = 28):
    return [
        SimpleNamespace(
            source_metadata_json={"seed_pack": "public_demo"},
            ingestion_status="embedded",
            sensitivity_label="public" if index < 14 else "internal",
        )
        for index in range(count)
    ]


class PublicMetricsP20Tests(unittest.TestCase):
    def test_reports_ready_sanitized_live_metrics(self):
        payload = build_live_metrics_snapshot(
            sources=_sources(),
            usage={
                "sample_size": 8,
                "mean_latency_ms": 900.0,
                "p50_latency_ms": 850,
                "p95_latency_ms": 1200,
                "max_latency_ms": 1500,
                "average_cost_usd_per_query": 0.004,
                "recovery_rate": 0.125,
            },
        )
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["readiness"], "ready")
        self.assertEqual(payload["demo_source_count"], 28)
        self.assertEqual(payload["public_source_count"], 14)
        self.assertEqual(payload["status"], "pass")
        serialized = str(payload).lower()
        for forbidden in ("question", "prompt", "user", "raw_trace", "total_spend"):
            self.assertNotIn(forbidden, serialized)

    def test_requires_five_samples_before_status(self):
        payload = build_live_metrics_snapshot(
            sources=_sources(),
            usage={"sample_size": 4},
        )
        self.assertEqual(payload["status"], "insufficient_data")
        self.assertEqual(payload["metric_status"], {})

    def test_warns_and_breaches_at_declared_thresholds(self):
        warning = build_live_metrics_snapshot(
            sources=_sources(),
            usage={
                "sample_size": 5,
                "mean_latency_ms": 2500,
                "p50_latency_ms": 1000,
                "p95_latency_ms": 4100,
                "max_latency_ms": 4500,
                "average_cost_usd_per_query": 0.005,
                "recovery_rate": 0.1,
            },
        )
        self.assertEqual(warning["status"], "warn")
        breached = build_live_metrics_snapshot(
            sources=_sources(),
            usage={**warning["metrics"], "sample_size": 5, "p95_latency_ms": 5100},
        )
        self.assertEqual(breached["status"], "breach")

    def test_incomplete_demo_seed_is_not_ready(self):
        payload = build_live_metrics_snapshot(sources=_sources(27), usage={"sample_size": 0})
        self.assertEqual(payload["readiness"], "not_ready")


if __name__ == "__main__":
    unittest.main()
