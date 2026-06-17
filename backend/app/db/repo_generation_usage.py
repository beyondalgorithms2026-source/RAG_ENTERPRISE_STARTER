"""Generation token/cost usage events and rollups (AR11)."""
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine

_ALLOWED_GROUP_BY = {"model", "retrieval_mode", "provider", "answer_path"}


def record_generation_usage_event(
    *,
    request_id: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    retrieval_mode: Optional[str],
    answer_path: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated: bool,
    cost_usd: float,
    latency_ms: Optional[int],
    call_count: int,
    over_budget: bool,
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
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
        ).mappings().one()
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in dict(row).items()}


def cost_summary(*, group_by: str = "retrieval_mode", limit: int = 100) -> dict[str, Any]:
    """Per-dimension rollup so an operator can answer 'deep research vs fast mode
    cost' (group_by=retrieval_mode) or per-model spend (group_by=model)."""
    column = group_by if group_by in _ALLOWED_GROUP_BY else "retrieval_mode"
    with engine.connect() as conn:
        rows = conn.execute(
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
        ).mappings().all()
        totals = conn.execute(
            text(
                "SELECT COUNT(*)::bigint AS request_count, "
                "SUM(total_tokens)::bigint AS total_tokens, "
                "ROUND(SUM(cost_usd)::numeric, 6) AS total_cost_usd FROM generation_usage_events"
            )
        ).mappings().one()
    return {
        "group_by": column,
        "buckets": [{k: (float(v) if hasattr(v, "as_integer_ratio") else v) for k, v in dict(row).items()} for row in rows],
        "totals": {k: (float(v) if hasattr(v, "as_integer_ratio") else v) for k, v in dict(totals).items()},
    }
