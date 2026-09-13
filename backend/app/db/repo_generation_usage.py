"""Generation token/cost usage events and rollups (AR11)."""

from typing import Any

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from sqlalchemy import text

_ALLOWED_GROUP_BY = {"model", "retrieval_mode", "provider", "answer_path"}


def record_generation_usage_event(
    *,
    request_id: str | None,
    provider: str | None,
    model: str | None,
    retrieval_mode: str | None,
    answer_path: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated: bool,
    cost_usd: float,
    latency_ms: int | None,
    call_count: int,
    over_budget: bool,
    actor: AuthenticatedUser | None = None,
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = (
            conn.execute(
                text(
                    """
                INSERT INTO generation_usage_events (
                    request_id, provider, model, retrieval_mode, answer_path,
                    prompt_tokens, completion_tokens, total_tokens, estimated,
                    cost_usd, latency_ms, call_count, over_budget,
                    actor_external_user_id, actor_email
                )
                VALUES (
                    :request_id, :provider, :model, :retrieval_mode, :answer_path,
                    :prompt_tokens, :completion_tokens, :total_tokens, :estimated,
                    :cost_usd, :latency_ms, :call_count, :over_budget, :actor_id, :actor_email
                )
                RETURNING id, model, retrieval_mode, total_tokens, cost_usd, over_budget, created_at
                """
                ),
                {
                    "request_id": request_id,
                    "provider": provider,
                    "model": model,
                    "retrieval_mode": retrieval_mode,
                    "answer_path": answer_path,
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(total_tokens),
                    "estimated": bool(estimated),
                    "cost_usd": float(cost_usd),
                    "latency_ms": latency_ms,
                    "call_count": int(call_count),
                    "over_budget": bool(over_budget),
                    "actor_id": actor.user_id if actor else None,
                    "actor_email": actor.email if actor else None,
                },
            )
            .mappings()
            .one()
        )
    return {
        key: (value.isoformat() if hasattr(value, "isoformat") else value)
        for key, value in dict(row).items()
    }


def cost_summary(*, group_by: str = "retrieval_mode", limit: int = 100) -> dict[str, Any]:
    """Per-dimension rollup so an operator can answer 'deep research vs fast mode
    cost' (group_by=retrieval_mode) or per-model spend (group_by=model)."""
    column = group_by if group_by in _ALLOWED_GROUP_BY else "retrieval_mode"
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    f"""
                SELECT COALESCE({column}, 'unknown') AS bucket,
                       COUNT(*)::bigint AS request_count,
                       SUM(total_tokens)::bigint AS total_tokens,
                       ROUND(SUM(cost_usd)::numeric, 6) AS total_cost_usd,
                       ROUND(AVG(cost_usd)::numeric, 6) AS avg_cost_usd,
                       ROUND(AVG(latency_ms)::numeric, 1) AS avg_latency_ms,
                       SUM(CASE WHEN over_budget THEN 1 ELSE 0 END)::bigint AS over_budget_count,
                       BOOL_OR(estimated) AS any_estimated
                FROM generation_usage_events
                GROUP BY bucket
                ORDER BY total_cost_usd DESC NULLS LAST
                LIMIT :limit
                """
                ),
                {"limit": limit},
            )
            .mappings()
            .all()
        )
        totals = (
            conn.execute(
                text(
                    "SELECT COUNT(*)::bigint AS request_count, "
                    "SUM(total_tokens)::bigint AS total_tokens, "
                    "ROUND(SUM(cost_usd)::numeric, 6) AS total_cost_usd FROM generation_usage_events"
                )
            )
            .mappings()
            .one()
        )
    return {
        "group_by": column,
        "buckets": [
            {k: (float(v) if hasattr(v, "as_integer_ratio") else v) for k, v in dict(row).items()}
            for row in rows
        ],
        "totals": {
            k: (float(v) if hasattr(v, "as_integer_ratio") else v) for k, v in dict(totals).items()
        },
    }


def live_usage_summary(*, hours: int = 24) -> dict[str, Any]:
    """Sanitized rolling generation metrics grouped by backend request ID.

    The generation-usage table contains LLM answer calls only, so one-time
    ingestion/embedding cost is excluded by construction.
    """
    bounded_hours = min(max(int(hours), 1), 168)
    sql = text(
        """
        WITH per_request AS (
            SELECT request_id,
                   SUM(cost_usd) AS cost_usd,
                   MAX(latency_ms) AS latency_ms,
                   BOOL_OR(answer_path = 'repair') AS recovery_attempted
            FROM generation_usage_events
            WHERE created_at >= now() - (:hours * interval '1 hour')
              AND request_id IS NOT NULL
            GROUP BY request_id
        )
        SELECT COUNT(*)::bigint AS sample_size,
               ROUND(AVG(latency_ms)::numeric, 1) AS mean_latency_ms,
               percentile_disc(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
               percentile_disc(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
               MAX(latency_ms) AS max_latency_ms,
               ROUND(AVG(cost_usd)::numeric, 8) AS average_cost_usd_per_query,
               ROUND(AVG(CASE WHEN recovery_attempted THEN 1.0 ELSE 0.0 END)::numeric, 6)
                   AS recovery_rate
        FROM per_request
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"hours": bounded_hours}).mappings().one()
    return {
        key: (float(value) if hasattr(value, "as_integer_ratio") else value)
        for key, value in dict(row).items()
    }
