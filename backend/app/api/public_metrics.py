from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.db.repo_generation_usage import live_usage_summary
from app.db.repo_sources import list_sources

router = APIRouter()

EXPECTED_DEMO_SOURCE_COUNT = 28
MINIMUM_SAMPLES = 5
CACHE_SECONDS = 60
THRESHOLDS = {
    "p95_latency_ms": 5000.0,
    "mean_latency_ms": 3000.0,
    "average_cost_usd_per_query": 0.02,
    "recovery_rate": 0.25,
}
_cache: tuple[float, dict[str, Any]] | None = None


def _metric_status(value: float, limit: float) -> str:
    if value > limit:
        return "breach"
    if value >= limit * 0.8:
        return "warn"
    return "pass"


def build_live_metrics_snapshot(
    *, sources: list[Any] | None = None, usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    readiness = "ready"
    try:
        source_rows = list_sources() if sources is None else sources
        usage_values = live_usage_summary(hours=24) if usage is None else usage
    except Exception:
        source_rows = []
        usage_values = {}
        readiness = "unavailable"

    demo_sources = [
        source
        for source in source_rows
        if isinstance(getattr(source, "source_metadata_json", None), dict)
        and source.source_metadata_json.get("seed_pack") == "public_demo"
    ]
    embedded_demo_sources = [
        source
        for source in demo_sources
        if getattr(source, "ingestion_status", None) == "embedded"
    ]
    public_sources = [
        source for source in demo_sources if getattr(source, "sensitivity_label", None) == "public"
    ]
    if readiness == "ready" and (
        len(demo_sources) < EXPECTED_DEMO_SOURCE_COUNT
        or len(embedded_demo_sources) != len(demo_sources)
    ):
        readiness = "not_ready"

    sample_size = int(usage_values.get("sample_size") or 0)
    metrics = {
        "mean_latency_ms": usage_values.get("mean_latency_ms"),
        "p50_latency_ms": usage_values.get("p50_latency_ms"),
        "p95_latency_ms": usage_values.get("p95_latency_ms"),
        "max_latency_ms": usage_values.get("max_latency_ms"),
        "average_cost_usd_per_query": usage_values.get("average_cost_usd_per_query"),
        "recovery_rate": usage_values.get("recovery_rate"),
    }
    metric_status: dict[str, str] = {}
    if sample_size < MINIMUM_SAMPLES or any(value is None for value in metrics.values()):
        status = "insufficient_data"
    else:
        metric_status = {
            name: _metric_status(float(metrics[name]), limit) for name, limit in THRESHOLDS.items()
        }
        status = (
            "breach"
            if "breach" in metric_status.values()
            else "warn"
            if "warn" in metric_status.values()
            else "pass"
        )

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "window_hours": 24,
        "sample_size": sample_size,
        "minimum_samples": MINIMUM_SAMPLES,
        "readiness": readiness,
        "public_source_count": len(public_sources),
        "demo_source_count": len(demo_sources),
        "expected_demo_source_count": EXPECTED_DEMO_SOURCE_COUNT,
        "metrics": metrics,
        "thresholds": THRESHOLDS,
        "metric_status": metric_status,
        "status": status,
        "configuration": {
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "retrieval_mode": settings.RETRIEVAL_MODE,
            "rerank_enabled": settings.RERANK_ENABLED,
        },
    }


@router.get("/metrics/live")
def live_metrics():
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    snapshot = build_live_metrics_snapshot()
    _cache = (now, snapshot)
    return snapshot
