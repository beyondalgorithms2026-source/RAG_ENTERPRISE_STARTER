import json
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine


MANDATORY_SAFETY = {
    "require_grounded_answer": True,
    "require_citations": True,
    "excluded_answer_paths": [
        "not_found",
        "approval_required",
        "pending_approval",
        "tool_action",
        "failed",
        "incomplete",
        "dry_run",
    ],
}


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _normalized_tokens(values: list[str], *, questions: bool = False) -> list[str]:
    cleaned = {
        normalize_question(value) if questions else str(value or "").strip().lower()
        for value in values
        if str(value or "").strip()
    }
    return sorted(cleaned)


def validate_policy_config(config: dict[str, Any]) -> dict[str, Any]:
    allow_corpora = _normalized_tokens(list(config.get("allow_corpora") or []))
    allow_groups = _normalized_tokens(list(config.get("allow_groups") or []))
    allow_questions = _normalized_tokens(list(config.get("allow_questions") or []), questions=True)
    if not (allow_corpora or allow_groups or allow_questions):
        raise ValueError("At least one allowed corpus, ACL group, or exact question is required")
    ttl_seconds = int(config.get("ttl_seconds") or 900)
    max_active_entries = int(config.get("max_active_entries") or 1000)
    if not 30 <= ttl_seconds <= 86400:
        raise ValueError("TTL must be between 30 and 86400 seconds")
    if not 1 <= max_active_entries <= 100000:
        raise ValueError("Maximum active entries must be between 1 and 100000")
    match_mode = str(config.get("match_mode") or "exact").strip().lower()
    if match_mode not in {"exact", "semantic"}:
        raise ValueError("match_mode must be 'exact' or 'semantic'")
    similarity_threshold = float(config.get("similarity_threshold") or 0.92)
    if not 0.5 <= similarity_threshold <= 0.999:
        raise ValueError("similarity_threshold must be between 0.5 and 0.999")
    return {
        "enabled": bool(config.get("enabled", False)),
        "match_mode": match_mode,
        "similarity_threshold": similarity_threshold,
        "ttl_seconds": ttl_seconds,
        "max_active_entries": max_active_entries,
        "allow_corpora": allow_corpora,
        "deny_corpora": _normalized_tokens(list(config.get("deny_corpora") or [])),
        "allow_groups": allow_groups,
        "deny_groups": _normalized_tokens(list(config.get("deny_groups") or [])),
        "allow_questions": allow_questions,
        "deny_questions": _normalized_tokens(list(config.get("deny_questions") or []), questions=True),
        "safety": dict(MANDATORY_SAFETY),
    }


def _version_payload(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key in (
        "allow_corpora_json",
        "deny_corpora_json",
        "allow_groups_json",
        "deny_groups_json",
        "allow_questions_json",
        "deny_questions_json",
        "safety_json",
    ):
        payload[key.removesuffix("_json")] = payload.pop(key, None) or ([] if key != "safety_json" else {})
    return _jsonable(payload)


def _policy_payload(row: Any) -> dict[str, Any]:
    source = dict(row)
    payload = {
        key: _jsonable(source.get(key))
        for key in (
            "id",
            "name",
            "justification",
            "owner",
            "review_at",
            "status",
            "active_version_id",
            "created_by_external_user_id",
            "created_by_email",
            "created_at",
            "updated_at",
        )
    }
    if source.get("version_id"):
        payload["active_version"] = {
            "id": source.get("version_id"),
            "policy_id": source.get("version_policy_id"),
            "version_number": source.get("version_version_number"),
            "cache_namespace": source.get("version_cache_namespace"),
            "status": source.get("version_status"),
            "enabled": source.get("enabled"),
            "match_mode": source.get("match_mode"),
            "similarity_threshold": source.get("similarity_threshold"),
            "ttl_seconds": source.get("ttl_seconds"),
            "max_active_entries": source.get("max_active_entries"),
            "allow_corpora": source.get("allow_corpora_json") or [],
            "deny_corpora": source.get("deny_corpora_json") or [],
            "allow_groups": source.get("allow_groups_json") or [],
            "deny_groups": source.get("deny_groups_json") or [],
            "allow_questions": source.get("allow_questions_json") or [],
            "deny_questions": source.get("deny_questions_json") or [],
            "safety": source.get("safety_json") or {},
            "created_by_external_user_id": source.get("version_created_by_external_user_id"),
            "created_by_email": source.get("version_created_by_email"),
            "approved_by_external_user_id": source.get("approved_by_external_user_id"),
            "approved_by_email": source.get("approved_by_email"),
            "created_at": source.get("version_created_at"),
            "activated_at": source.get("activated_at"),
        }
        payload["active_version"] = _jsonable(payload["active_version"])
    else:
        payload["active_version"] = None
    return payload


_POLICY_SELECT = """
SELECT p.id, p.name, p.justification, p.owner, p.review_at, p.status,
       p.active_version_id, p.created_by_external_user_id, p.created_by_email,
       p.created_at, p.updated_at,
       v.id AS version_id, v.policy_id AS version_policy_id,
       v.version_number AS version_version_number,
       v.cache_namespace AS version_cache_namespace,
       v.status AS version_status, v.enabled, v.match_mode, v.similarity_threshold, v.ttl_seconds,
       v.max_active_entries, v.allow_corpora_json, v.deny_corpora_json,
       v.allow_groups_json, v.deny_groups_json, v.allow_questions_json,
       v.deny_questions_json, v.safety_json,
       v.created_by_external_user_id AS version_created_by_external_user_id,
       v.created_by_email AS version_created_by_email,
       v.approved_by_external_user_id, v.approved_by_email,
       v.created_at AS version_created_at, v.activated_at
FROM semantic_cache_policies p
LEFT JOIN semantic_cache_policy_versions v ON v.id = p.active_version_id
"""


def list_policies() -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"{_POLICY_SELECT} ORDER BY p.updated_at DESC, p.id DESC")).mappings().all()
    return [get_policy(int(row["id"])) or _policy_payload(row) for row in rows]


def get_policy(policy_id: int) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(text(f"{_POLICY_SELECT} WHERE p.id = :policy_id"), {"policy_id": policy_id}).mappings().first()
    if not row:
        return None
    payload = _policy_payload(row)
    with engine.connect() as conn:
        versions = conn.execute(
            text(
                """
                SELECT id, policy_id, version_number, cache_namespace, status, enabled, match_mode,
                       similarity_threshold,
                       ttl_seconds, max_active_entries, allow_corpora_json, deny_corpora_json,
                       allow_groups_json, deny_groups_json, allow_questions_json,
                       deny_questions_json, safety_json, created_by_external_user_id,
                       created_by_email, approved_by_external_user_id, approved_by_email,
                       created_at, activated_at
                FROM semantic_cache_policy_versions
                WHERE policy_id = :policy_id
                ORDER BY version_number DESC
                """
            ),
            {"policy_id": policy_id},
        ).mappings().all()
    payload["versions"] = [_version_payload(item) for item in versions]
    payload["draft_version"] = next((item for item in payload["versions"] if item["status"] == "draft"), None)
    return payload


def get_active_policy_version() -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT v.*, p.name AS policy_name, p.justification, p.owner, p.review_at
                FROM semantic_cache_policy_versions v
                JOIN semantic_cache_policies p ON p.id = v.policy_id
                WHERE v.status = 'active' AND v.enabled = TRUE
                  AND p.status = 'active' AND p.active_version_id = v.id
                ORDER BY v.activated_at DESC, v.id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
    return _version_payload(row) if row else None


def create_policy(
    *,
    name: str,
    justification: str,
    owner: str,
    review_at: Optional[datetime],
    config: dict[str, Any],
    actor: Optional[AuthenticatedUser],
) -> dict[str, Any]:
    policy_name = str(name or "").strip()
    if not policy_name:
        raise ValueError("Policy name is required")
    validated = validate_policy_config(config)
    with engine.begin() as conn:
        policy = conn.execute(
            text(
                """
                INSERT INTO semantic_cache_policies (
                    name, justification, owner, review_at, status,
                    created_by_external_user_id, created_by_email
                )
                VALUES (:name, :justification, :owner, :review_at, 'draft', :actor_id, :actor_email)
                RETURNING id
                """
            ),
            {
                "name": policy_name,
                "justification": str(justification or "").strip(),
                "owner": str(owner or "").strip(),
                "review_at": review_at,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).scalar_one()
        _insert_version(conn, int(policy), 1, validated, actor)
    return get_policy(int(policy)) or {}


def _insert_version(conn, policy_id: int, version_number: int, config: dict[str, Any], actor: Optional[AuthenticatedUser]) -> int:
    namespace = f"policy:{policy_id}:v{version_number}"
    return int(
        conn.execute(
            text(
                """
                INSERT INTO semantic_cache_policy_versions (
                    policy_id, version_number, cache_namespace, status, enabled, match_mode,
                    similarity_threshold, ttl_seconds, max_active_entries, allow_corpora_json, deny_corpora_json,
                    allow_groups_json, deny_groups_json, allow_questions_json,
                    deny_questions_json, safety_json, created_by_external_user_id, created_by_email
                )
                VALUES (
                    :policy_id, :version_number, :namespace, 'draft', :enabled, :match_mode,
                    :similarity_threshold, :ttl_seconds, :max_active_entries, CAST(:allow_corpora AS jsonb),
                    CAST(:deny_corpora AS jsonb), CAST(:allow_groups AS jsonb),
                    CAST(:deny_groups AS jsonb), CAST(:allow_questions AS jsonb),
                    CAST(:deny_questions AS jsonb), CAST(:safety AS jsonb), :actor_id, :actor_email
                )
                RETURNING id
                """
            ),
            {
                "policy_id": policy_id,
                "version_number": version_number,
                "namespace": namespace,
                "enabled": config["enabled"],
                "match_mode": config["match_mode"],
                "similarity_threshold": config["similarity_threshold"],
                "ttl_seconds": config["ttl_seconds"],
                "max_active_entries": config["max_active_entries"],
                "allow_corpora": json.dumps(config["allow_corpora"]),
                "deny_corpora": json.dumps(config["deny_corpora"]),
                "allow_groups": json.dumps(config["allow_groups"]),
                "deny_groups": json.dumps(config["deny_groups"]),
                "allow_questions": json.dumps(config["allow_questions"]),
                "deny_questions": json.dumps(config["deny_questions"]),
                "safety": json.dumps(MANDATORY_SAFETY),
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).scalar_one()
    )


def update_policy(
    policy_id: int,
    *,
    name: str,
    justification: str,
    owner: str,
    review_at: Optional[datetime],
    config: dict[str, Any],
    actor: Optional[AuthenticatedUser],
) -> dict[str, Any]:
    existing = get_policy(policy_id)
    if not existing:
        raise ValueError(f"Cache policy {policy_id} not found")
    policy_name = str(name or "").strip()
    if not policy_name:
        raise ValueError("Policy name is required")
    validated = validate_policy_config(config)
    latest_number = max([int(item["version_number"]) for item in existing.get("versions", [])] or [0])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE semantic_cache_policies
                SET name = :name, justification = :justification, owner = :owner,
                    review_at = :review_at, updated_at = now()
                WHERE id = :policy_id
                """
            ),
            {
                "policy_id": policy_id,
                "name": policy_name,
                "justification": str(justification or "").strip(),
                "owner": str(owner or "").strip(),
                "review_at": review_at,
            },
        )
        conn.execute(
            text("UPDATE semantic_cache_policy_versions SET status = 'superseded' WHERE policy_id = :policy_id AND status = 'draft'"),
            {"policy_id": policy_id},
        )
        _insert_version(conn, policy_id, latest_number + 1, validated, actor)
    return get_policy(policy_id) or {}


def activate_policy(policy_id: int, *, confirmation: str, actor: Optional[AuthenticatedUser]) -> dict[str, Any]:
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Cache policy {policy_id} not found")
    if confirmation.strip() != policy["name"]:
        raise ValueError("Typed confirmation must exactly match the cache policy name")
    draft = policy.get("draft_version")
    if not draft:
        raise ValueError("Cache policy has no draft version to activate")
    validate_policy_config({**draft, "enabled": True})
    with engine.begin() as conn:
        conn.execute(text("UPDATE semantic_cache_policy_versions SET status = 'rolled_back', enabled = FALSE WHERE status = 'active'"))
        conn.execute(text("UPDATE semantic_cache_policies SET status = 'disabled', active_version_id = NULL WHERE status = 'active'"))
        conn.execute(
            text(
                """
                UPDATE semantic_cache_policy_versions
                SET status = 'active', enabled = TRUE, activated_at = now(),
                    approved_by_external_user_id = :actor_id, approved_by_email = :actor_email
                WHERE id = :version_id
                """
            ),
            {
                "version_id": draft["id"],
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        )
        conn.execute(
            text("UPDATE semantic_cache_policies SET status = 'active', active_version_id = :version_id, updated_at = now() WHERE id = :policy_id"),
            {"version_id": draft["id"], "policy_id": policy_id},
        )
    return get_policy(policy_id) or {}


def disable_policy(policy_id: int) -> dict[str, Any]:
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Cache policy {policy_id} not found")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE semantic_cache_policy_versions SET status = 'disabled', enabled = FALSE WHERE policy_id = :policy_id AND status = 'active'"),
            {"policy_id": policy_id},
        )
        conn.execute(
            text("UPDATE semantic_cache_policies SET status = 'disabled', active_version_id = NULL, updated_at = now() WHERE id = :policy_id"),
            {"policy_id": policy_id},
        )
    return get_policy(policy_id) or {}


def rollback_policy(policy_id: int, *, version_id: int, actor: Optional[AuthenticatedUser]) -> dict[str, Any]:
    policy = get_policy(policy_id)
    if not policy:
        raise ValueError(f"Cache policy {policy_id} not found")
    target = next((item for item in policy.get("versions", []) if int(item["id"]) == int(version_id)), None)
    if not target:
        raise ValueError(f"Cache policy version {version_id} not found")
    with engine.begin() as conn:
        conn.execute(text("UPDATE semantic_cache_policy_versions SET status = 'rolled_back', enabled = FALSE WHERE status = 'active'"))
        conn.execute(text("UPDATE semantic_cache_policies SET status = 'disabled', active_version_id = NULL WHERE status = 'active'"))
        conn.execute(
            text(
                """
                UPDATE semantic_cache_policy_versions
                SET status = 'active', enabled = TRUE, activated_at = now(),
                    approved_by_external_user_id = :actor_id, approved_by_email = :actor_email
                WHERE id = :version_id
                """
            ),
            {
                "version_id": version_id,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        )
        conn.execute(
            text("UPDATE semantic_cache_policies SET status = 'active', active_version_id = :version_id, updated_at = now() WHERE id = :policy_id"),
            {"version_id": version_id, "policy_id": policy_id},
        )
    return get_policy(policy_id) or {}


def record_policy_event(
    *,
    event_type: str,
    reason: str,
    policy_version_id: Optional[int] = None,
    cache_entry_id: Optional[int] = None,
    latency_saved_ms: Optional[int] = None,
    estimated_cost_saved_usd: float = 0.0,
    actor: Optional[AuthenticatedUser] = None,
    metadata_json: Optional[dict[str, Any]] = None,
) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO semantic_cache_policy_events (
                        policy_version_id, cache_entry_id, event_type, reason,
                        latency_saved_ms, estimated_cost_saved_usd,
                        actor_external_user_id, actor_email, metadata_json
                    )
                    VALUES (
                        :policy_version_id, :cache_entry_id, :event_type, :reason,
                        :latency_saved_ms, :estimated_cost_saved_usd,
                        :actor_id, :actor_email, CAST(:metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "policy_version_id": policy_version_id,
                    "cache_entry_id": cache_entry_id,
                    "event_type": event_type,
                    "reason": reason,
                    "latency_saved_ms": latency_saved_ms,
                    "estimated_cost_saved_usd": estimated_cost_saved_usd,
                    "actor_id": actor.user_id if actor else None,
                    "actor_email": actor.email if actor else None,
                    "metadata_json": json.dumps(metadata_json or {}),
                },
            ).scalar_one()
        )


def policy_metrics() -> dict[str, Any]:
    with engine.connect() as conn:
        counts = conn.execute(
            text(
                """
                SELECT event_type, COUNT(*)::bigint AS count,
                       COALESCE(SUM(latency_saved_ms), 0)::bigint AS latency_saved_ms,
                       COALESCE(SUM(estimated_cost_saved_usd), 0)::numeric AS estimated_cost_saved_usd
                FROM semantic_cache_policy_events
                GROUP BY event_type
                """
            )
        ).mappings().all()
        reasons = conn.execute(
            text(
                """
                SELECT COALESCE(reason, 'unspecified') AS reason, COUNT(*)::bigint AS count
                FROM semantic_cache_policy_events
                GROUP BY COALESCE(reason, 'unspecified')
                ORDER BY count DESC, reason
                LIMIT 30
                """
            )
        ).mappings().all()
    by_type = {str(row["event_type"]): int(row["count"]) for row in counts}
    return {
        "event_counts": by_type,
        "hit_count": by_type.get("hit", 0),
        "miss_count": by_type.get("miss", 0),
        "refresh_count": by_type.get("refresh", 0),
        "reauthorization_miss_count": by_type.get("reauthorization_miss", 0),
        "materially_changed_refresh_count": by_type.get("refresh_changed", 0),
        "latency_saved_ms": sum(int(row["latency_saved_ms"] or 0) for row in counts),
        "estimated_cost_saved_usd": float(sum(row["estimated_cost_saved_usd"] or 0 for row in counts)),
        "reasons": [_jsonable(dict(row)) for row in reasons],
    }
