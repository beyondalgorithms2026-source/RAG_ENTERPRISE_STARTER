"""Read-only operator posture surface (AR15).

The follow-up console review found that an admin had no in-UI way to know the
things they must know: that the semantic cache is globally off unless a policy
is active, the retrieval default flags, the eval enforcement mode, the
single-process worker posture, the rate limits, and the cost-alert threshold —
all reachable today only by reading the environment or the database.

This composes one structured posture payload. Each item carries how it is
changed (`editable_via`) and whether a restart is required, so the console can
tell the operator exactly what to edit and where, including settings that — by
design — can only be changed via the environment.
"""
from typing import Any

from app.core.config import settings


def _item(label: str, value: Any, *, editable_via: str, requires_restart: bool = False) -> dict[str, Any]:
    return {"label": label, "value": value, "editable_via": editable_via, "requires_restart": requires_restart}


def system_posture() -> dict[str, Any]:
    from app.coherence import vector_serving_state
    from app.core.runtime_safety import configured_worker_count
    from app.db.repo_semantic_cache import cache_health
    from app.eval.promotion_evidence import resolve_enforcement_mode
    from app.profiles.resolver import get_effective_reranker, get_effective_retrieval

    serving = vector_serving_state()
    cache = cache_health()
    cache_policy = cache.get("active_policy")
    retrieval = get_effective_retrieval()
    reranker = get_effective_reranker()
    enforcement_explicit = str(settings.TUNING_EVAL_ENFORCEMENT or "").strip().lower() in {"require", "warn"}

    return {
        "serving": {
            "vector_search_serviceable": serving["serviceable"],
            "items": [
                _item("Vector search", "serviceable" if serving["serviceable"] else f"degraded — {serving.get('reason')}", editable_via="lifecycle:embedding_swap"),
                _item("Profile dimension", serving.get("profile_dimension"), editable_via="lifecycle:embedding_swap"),
                _item("Index dimension", serving.get("index_dimension"), editable_via="lifecycle:embedding_swap"),
            ],
        },
        "cache": {
            "enabled": bool(cache_policy),
            "reason": "active" if cache_policy else "no_active_policy",
            "headline": "Active cache policy in {} mode.".format(cache.get("match_mode", "exact")) if cache_policy else "Semantic cache is globally OFF (no active policy).",
            "items": [
                _item("Semantic cache", "active" if cache_policy else "globally OFF (no active policy)", editable_via="policy"),
                _item("Match mode", cache.get("match_mode") if cache_policy else None, editable_via="policy"),
            ],
        },
        "retrieval_defaults": {
            "items": [
                _item("Default retrieval mode", retrieval.default_mode, editable_via="profile"),
                _item("Query transformation", "on" if retrieval.query_transform_enabled else "off (default)", editable_via="profile"),
                _item("Multi-query fan-out", "on" if retrieval.multi_query_enabled else "off (default)", editable_via="profile"),
                _item("Reranker", "on" if reranker.enabled else "off (default)", editable_via="profile"),
            ],
        },
        "eval_enforcement": {
            "mode": resolve_enforcement_mode(),
            "items": [
                _item("Promotion eval enforcement", resolve_enforcement_mode(), editable_via="env:TUNING_EVAL_ENFORCEMENT" if enforcement_explicit else "env:TUNING_EVAL_ENFORCEMENT (derived from APP_ENV)"),
            ],
        },
        "workers": {
            "single_process": True,
            "items": [
                _item("Process model", "single-process (in-memory queue, rate limits, model singletons)", editable_via="env:ALLOW_MULTI_WORKER", requires_restart=True),
                _item("Allow multiple workers", bool(settings.ALLOW_MULTI_WORKER), editable_via="env:ALLOW_MULTI_WORKER", requires_restart=True),
                _item("Configured workers", configured_worker_count(), editable_via="env:WEB_CONCURRENCY", requires_restart=True),
            ],
        },
        "rate_limits": {
            "items": [
                _item("Rate limiting", "on" if settings.RATE_LIMIT_ENABLED else "off", editable_via="env:RATE_LIMIT_ENABLED", requires_restart=True),
                _item("Ask / minute", settings.RATE_LIMIT_ASK_PER_MINUTE, editable_via="env:RATE_LIMIT_ASK_PER_MINUTE", requires_restart=True),
                _item("Search / minute", settings.RATE_LIMIT_SEARCH_PER_MINUTE, editable_via="env:RATE_LIMIT_SEARCH_PER_MINUTE", requires_restart=True),
                _item("Admin-expensive / minute", settings.RATE_LIMIT_ADMIN_EXPENSIVE_PER_MINUTE, editable_via="env:RATE_LIMIT_ADMIN_EXPENSIVE_PER_MINUTE", requires_restart=True),
            ],
        },
        "cost_governance": {
            "items": [
                _item("Cost alert threshold (USD)", settings.LLM_COST_ALERT_USD, editable_via="env:LLM_COST_ALERT_USD"),
                _item("Price table overridden", bool(settings.LLM_PRICE_TABLE_JSON), editable_via="env:LLM_PRICE_TABLE_JSON"),
            ],
        },
    }
