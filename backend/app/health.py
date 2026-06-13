"""Operator health and trust dashboard (AR10).

The audit found the admin console shows what is *configured* but never whether
the configuration is *self-consistent* — the blind spot that let the dev
environment carry wrong registry dimensions, a draft profile active as live, and
a migration-ledger mismatch without anyone noticing. This module composes one
"is the system coherent right now?" answer from the AR2 coherence invariants
plus reranker warm-up freshness, semantic-cache state, and the AR3/AR4 eval gate.

Each tile is {tile, status: pass|warn|fail, reason, details}. P0 invariants
(the coherence checks) drive the console banner; the operational tiles
(warm-up, cache, eval) can only warn.
"""
from datetime import datetime, timezone
from typing import Any, Optional

P0_TILES = {"embedding_dimension", "embedding_registry_metadata", "active_profiles_promoted", "migration_ledger", "vector_serving"}


def _tile(name: str, status: str, reason: str, **details: Any) -> dict[str, Any]:
    payload = {"tile": name, "status": status, "reason": reason}
    if details:
        payload["details"] = {k: v for k, v in details.items() if v is not None}
    return payload


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def reranker_warmup_tile(*, max_age_s: int = 86400) -> dict[str, Any]:
    from app.db.repo_tuning_configs import list_model_warmups

    warmups = [w for w in list_model_warmups(limit=50) if w.get("model_type") == "reranker"]
    if not warmups:
        return _tile("reranker_warmup", "warn", "No reranker warm-up recorded; first rerank will pay cold-start latency.")
    latest = warmups[0]
    if str(latest.get("status")) != "success":
        return _tile("reranker_warmup", "fail", f"Last reranker warm-up failed: {latest.get('error_message') or 'unknown'}.", model=latest.get("model_name"))
    created = _parse_ts(latest.get("created_at"))
    age_s = int((datetime.now(timezone.utc) - created).total_seconds()) if created else None
    if age_s is not None and age_s > max_age_s:
        return _tile("reranker_warmup", "warn", f"Reranker warm-up is stale ({age_s // 3600}h old).", model=latest.get("model_name"), age_s=age_s)
    return _tile("reranker_warmup", "pass", "Reranker warmed and loadable.", model=latest.get("model_name"), age_s=age_s)


def semantic_cache_tile() -> dict[str, Any]:
    from app.db.repo_semantic_cache import cache_health

    health = cache_health()
    policy = health.get("active_policy")
    if not policy:
        return _tile("semantic_cache", "pass", "Cache globally off (no active policy).", state="off")
    return _tile(
        "semantic_cache",
        "pass",
        f"Active cache policy in {health.get('match_mode', 'exact')} mode.",
        match_mode=health.get("match_mode"),
        active_entries=health.get("active_entries"),
        exact_hits=health.get("exact_hit_count"),
        similarity_hits=health.get("similarity_hit_count"),
        namespace=str((policy or {}).get("cache_namespace") or ""),
    )


def eval_gate_tile() -> dict[str, Any]:
    from app.db.repo_eval_runs import latest_live_baseline_run
    from app.db.repo_tuning_configs import list_tuning_history

    baseline = latest_live_baseline_run()
    history = list_tuning_history(limit=20)
    last_promote = next((e for e in history.get("promotion_events", []) if e.get("action") == "promote"), None)
    promotion_evidence = (last_promote or {}).get("eval_evidence_json") or {}
    if not baseline:
        return _tile(
            "eval_gate",
            "warn",
            "No live baseline eval recorded (run POST /admin/tuning/eval-runs).",
            last_promotion_gate=promotion_evidence.get("gate_status"),
        )
    status = "pass" if baseline.get("gate_status") == "pass" else "fail"
    reason = "Live baseline passes the eval gate." if status == "pass" else "Live baseline FAILS the eval gate."
    return _tile(
        "eval_gate",
        status,
        reason,
        baseline_run_id=baseline.get("id"),
        gate_status=baseline.get("gate_status"),
        gate_aggregates=baseline.get("gate_aggregates"),
        last_promotion_gate=promotion_evidence.get("gate_status"),
        last_promotion_warnings=promotion_evidence.get("warnings") or None,
    )


def health_dashboard(*, deep: bool = False) -> dict[str, Any]:
    from app.coherence import run_coherence_checks

    coherence = run_coherence_checks(deep=deep)
    tiles: list[dict[str, Any]] = []
    for inv in coherence["invariants"]:
        tiles.append(_tile(inv["invariant"], inv["status"], inv["reason"], **(inv.get("details") or {})))
    tiles.append(reranker_warmup_tile())
    tiles.append(semantic_cache_tile())
    tiles.append(eval_gate_tile())

    p0_failed = [t for t in tiles if t["tile"] in P0_TILES and t["status"] == "fail"]
    any_fail = [t for t in tiles if t["status"] == "fail"]
    any_warn = [t for t in tiles if t["status"] == "warn"]
    if any_fail:
        banner = "fail"
    elif any_warn:
        banner = "warn"
    else:
        banner = "pass"
    return {
        "banner": banner,
        "p0_breached": bool(p0_failed),
        "p0_failures": [t["tile"] for t in p0_failed],
        "tiles": tiles,
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
    }
