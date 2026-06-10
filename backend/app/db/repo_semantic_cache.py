import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.auth.access_strategy import active_corpus_grant_fingerprint, active_access_strategy
from app.db.db import engine
from app.db.repo_acl import active_direct_grant_fingerprint, can_current_user_access_source, current_acl_context
from app.db.repo_semantic_cache_policies import (
    get_active_policy_version,
    normalize_question,
    record_policy_event,
)
from app.db.repo_sources import get_source_by_id
from app.profiles.resolver import get_active_profile_snapshot


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_scope(*, question: str, retrieval_mode: Optional[str], corpus_scope: Optional[dict[str, Any]] = None) -> dict[str, str]:
    acl = current_acl_context()
    profiles = get_active_profile_snapshot()
    return {
        "normalized_question": normalize_question(question),
        "acl_scope_hash": _stable_hash(
            {
                "external_user_id": acl.get("external_user_id"),
                "email": acl.get("email"),
                "strategy": active_access_strategy(),
                "groups": sorted(acl.get("groups") or []),
                "local_dev_full_access": bool(acl.get("local_dev_full_access")),
                "direct_grants": active_direct_grant_fingerprint(),
                "corpus_grants": active_corpus_grant_fingerprint(),
            }
        ),
        "profile_snapshot_hash": _stable_hash(profiles),
        "corpus_scope_hash": _stable_hash(corpus_scope or {}),
        "retrieval_mode": retrieval_mode or "",
    }


def bump_cache_revision(*, scope_type: str, scope_key: str = "global", reason: str) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO semantic_cache_revisions (scope_type, scope_key, revision, reason)
                    VALUES (:scope_type, :scope_key, 1, :reason)
                    ON CONFLICT (scope_type, scope_key)
                    DO UPDATE SET revision = semantic_cache_revisions.revision + 1,
                                  reason = EXCLUDED.reason,
                                  updated_at = now()
                    RETURNING revision
                    """
                ),
                {"scope_type": scope_type, "scope_key": scope_key, "reason": reason},
            ).scalar_one()
        )


def current_cache_revisions(*, corpus_names: Optional[list[str]] = None, source_ids: Optional[list[int]] = None) -> dict[str, int]:
    keys = [("access", "global"), ("profile", "global"), ("content", "global")]
    keys.extend(("corpus", str(item).strip().lower()) for item in (corpus_names or []) if str(item).strip())
    keys.extend(("source", str(int(item))) for item in (source_ids or []))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT scope_type, scope_key, revision
                FROM semantic_cache_revisions
                WHERE (scope_type, scope_key) IN (
                    SELECT item->>0, item->>1
                    FROM jsonb_array_elements(CAST(:keys AS jsonb)) AS item
                )
                """
            ),
            {"keys": json.dumps(keys)},
        ).mappings().all()
    found = {f"{row['scope_type']}:{row['scope_key']}": int(row["revision"]) for row in rows}
    return {f"{scope_type}:{scope_key}": found.get(f"{scope_type}:{scope_key}", 0) for scope_type, scope_key in keys}


def _source_scope(citations_json: list[dict[str, Any]]) -> tuple[list[int], list[str], dict[str, Any]]:
    source_ids = sorted(
        {
            int(item["source_id"])
            for item in citations_json
            if isinstance(item, dict) and item.get("source_id") is not None
        }
    )
    corpora: set[str] = set()
    source_revisions: dict[str, Any] = {}
    for source_id in source_ids:
        source = get_source_by_id(source_id)
        if not source:
            continue
        corpus_name = str((source.source_metadata_json or {}).get("corpus") or "").strip().lower()
        if corpus_name:
            corpora.add(corpus_name)
        source_revisions[str(source_id)] = {
            "hash_sha256": source.hash_sha256,
            "ingestion_status": source.ingestion_status,
            "enrichment_status": source.enrichment_status,
        }
    return source_ids, sorted(corpora), source_revisions


def cache_citation_scope(citations_json: list[dict[str, Any]]) -> tuple[list[int], list[str]]:
    source_ids, corpus_names, _ = _source_scope(citations_json)
    return source_ids, corpus_names


def get_cache_entry_by_id(cache_entry_id: int) -> Optional[dict[str, Any]]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, policy_version_id, cache_namespace, answer_json, citations_json,
                       corpus_names_json, answer_path, original_latency_ms, metadata_json,
                       created_at, expires_at, invalidated_at
                FROM semantic_cache_entries
                WHERE id = :cache_entry_id
                """
            ),
            {"cache_entry_id": cache_entry_id},
        ).mappings().first()
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in dict(row).items()} if row else None


def invalidate_cache_entry(cache_entry_id: int, *, reason: str) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE semantic_cache_entries
                SET invalidated_at = now(),
                    metadata_json = metadata_json || CAST(:metadata AS jsonb)
                WHERE id = :cache_entry_id AND invalidated_at IS NULL
                """
            ),
            {"cache_entry_id": cache_entry_id, "metadata": json.dumps({"invalidation_reason": reason})},
        )
    return bool(result.rowcount)


def policy_allows(
    policy: dict[str, Any],
    *,
    question: str,
    corpus_names: list[str],
    groups: list[str],
) -> tuple[bool, str]:
    normalized = normalize_question(question)
    corpus_set = {str(item).strip().lower() for item in corpus_names if str(item).strip()}
    group_set = {str(item).strip().lower() for item in groups if str(item).strip()}
    if normalized in set(policy.get("deny_questions") or []):
        return False, "question_denied"
    if corpus_set & set(policy.get("deny_corpora") or []):
        return False, "corpus_denied"
    if group_set & set(policy.get("deny_groups") or []):
        return False, "group_denied"

    positive = normalized in set(policy.get("allow_questions") or [])
    allowed_corpora = set(policy.get("allow_corpora") or [])
    if corpus_set and allowed_corpora:
        if not corpus_set.issubset(allowed_corpora):
            return False, "corpus_not_fully_eligible"
        positive = True
    if group_set & set(policy.get("allow_groups") or []):
        positive = True
    return (positive, "eligible" if positive else "no_positive_scope_match")


def active_policy_decision(*, question: str, corpus_names: list[str]) -> tuple[Optional[dict[str, Any]], str]:
    policy = get_active_policy_version()
    if not policy:
        return None, "global_default_off"
    acl = current_acl_context()
    allowed, reason = policy_allows(
        policy,
        question=question,
        corpus_names=corpus_names,
        groups=list(acl.get("groups") or []),
    )
    return (policy if allowed else None), reason


def get_cache_entry(
    *,
    question: str,
    retrieval_mode: Optional[str],
    corpus_scope: Optional[dict[str, Any]] = None,
    actor: Optional[AuthenticatedUser] = None,
    policy: Optional[dict[str, Any]] = None,
    cache_namespace: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    scope = cache_scope(question=question, retrieval_mode=retrieval_mode, corpus_scope=corpus_scope)
    governed = policy or get_active_policy_version()
    namespace = cache_namespace or str((governed or {}).get("cache_namespace") or "")
    sql = text(
        """
        SELECT id, policy_version_id, cache_namespace, normalized_question, answer_json,
               citations_json, retrieved_chunk_ids_json, corpus_names_json,
               source_revisions_json, revision_snapshot_json, answer_path,
               original_latency_ms, metadata_json, created_at, expires_at
        FROM semantic_cache_entries
        WHERE cache_namespace = :cache_namespace
          AND normalized_question = :normalized_question
          AND acl_scope_hash = :acl_scope_hash
          AND profile_snapshot_hash = :profile_snapshot_hash
          AND corpus_scope_hash = :corpus_scope_hash
          AND retrieval_mode = :retrieval_mode
          AND invalidated_at IS NULL
          AND expires_at > now()
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(sql, {**scope, "cache_namespace": namespace}).mappings().first()
        if not row:
            if governed:
                record_policy_event(
                    event_type="miss",
                    reason="not_found",
                    policy_version_id=governed.get("id"),
                    actor=actor,
                    metadata_json={"question": normalize_question(question), "namespace": namespace},
                )
            return None
        if governed:
            allowed, reason = policy_allows(
                governed,
                question=question,
                corpus_names=list(row["corpus_names_json"] or []),
                groups=list(current_acl_context().get("groups") or []),
            )
            if not allowed:
                record_policy_event(
                    event_type="miss",
                    reason=reason,
                    policy_version_id=governed.get("id"),
                    cache_entry_id=row["id"],
                    actor=actor,
                )
                return None
        source_ids = {
            int(item.get("source_id"))
            for item in (row["citations_json"] or [])
            if isinstance(item, dict) and item.get("source_id") is not None
        }
        if any(not can_current_user_access_source(source_id) for source_id in source_ids):
            conn.execute(
                text(
                    """
                    INSERT INTO semantic_cache_hits (
                        cache_entry_id, hit_type, actor_external_user_id, actor_email
                    )
                    VALUES (:cache_entry_id, 'reauthorization_miss', :actor_id, :actor_email)
                    """
                ),
                {"cache_entry_id": row["id"], "actor_id": actor.user_id if actor else None, "actor_email": actor.email if actor else None},
            )
            if governed:
                record_policy_event(
                    event_type="reauthorization_miss",
                    reason="cited_source_not_accessible",
                    policy_version_id=governed.get("id"),
                    cache_entry_id=row["id"],
                    actor=actor,
                )
            return None
        current_revisions = current_cache_revisions(
            corpus_names=list(row["corpus_names_json"] or []),
            source_ids=sorted(source_ids),
        )
        if dict(row["revision_snapshot_json"] or {}) != current_revisions:
            conn.execute(
                text(
                    """
                    UPDATE semantic_cache_entries
                    SET invalidated_at = now(),
                        metadata_json = metadata_json || CAST(:metadata AS jsonb)
                    WHERE id = :id
                    """
                ),
                {"id": row["id"], "metadata": json.dumps({"invalidation_reason": "revision_changed"})},
            )
            if governed:
                record_policy_event(
                    event_type="miss",
                    reason="revision_changed",
                    policy_version_id=governed.get("id"),
                    cache_entry_id=row["id"],
                    actor=actor,
                )
            return None
        conn.execute(text("UPDATE semantic_cache_entries SET last_hit_at = now() WHERE id = :id"), {"id": row["id"]})
        conn.execute(
            text(
                """
                INSERT INTO semantic_cache_hits (
                    cache_entry_id, hit_type, actor_external_user_id, actor_email
                )
                VALUES (:cache_entry_id, 'hit', :actor_id, :actor_email)
                """
            ),
            {"cache_entry_id": row["id"], "actor_id": actor.user_id if actor else None, "actor_email": actor.email if actor else None},
        )
        if governed:
            record_policy_event(
                event_type="hit",
                reason="exact_query",
                policy_version_id=governed.get("id"),
                cache_entry_id=row["id"],
                latency_saved_ms=int(row["original_latency_ms"] or 0),
                actor=actor,
            )
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in dict(row).items()}


def store_cache_entry(
    *,
    question: str,
    retrieval_mode: Optional[str],
    answer_json: dict[str, Any],
    citations_json: list[dict[str, Any]],
    retrieved_chunk_ids: list[int],
    ttl_seconds: int,
    corpus_scope: Optional[dict[str, Any]] = None,
    query_embedding: Optional[list[float]] = None,
    metadata_json: Optional[dict[str, Any]] = None,
    policy: Optional[dict[str, Any]] = None,
    cache_namespace: Optional[str] = None,
    answer_path: Optional[str] = None,
    original_latency_ms: Optional[int] = None,
) -> dict[str, Any]:
    scope = cache_scope(question=question, retrieval_mode=retrieval_mode, corpus_scope=corpus_scope)
    governed = policy or get_active_policy_version()
    namespace = cache_namespace or str((governed or {}).get("cache_namespace") or "")
    source_ids, corpus_names, source_revisions = _source_scope(citations_json)
    revision_snapshot = current_cache_revisions(corpus_names=corpus_names, source_ids=source_ids)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl_seconds, 1))
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO semantic_cache_entries (
                    policy_version_id, cache_namespace, normalized_question,
                    query_embedding_json, acl_scope_hash, profile_snapshot_hash,
                    corpus_scope_hash, corpus_names_json, source_revisions_json,
                    revision_snapshot_json, retrieval_mode, answer_path, original_latency_ms,
                    answer_json, citations_json, retrieved_chunk_ids_json,
                    metadata_json, expires_at
                )
                VALUES (
                    :policy_version_id, :cache_namespace, :normalized_question,
                    CAST(:query_embedding AS jsonb), :acl_scope_hash,
                    :profile_snapshot_hash, :corpus_scope_hash, CAST(:corpus_names AS jsonb),
                    CAST(:source_revisions AS jsonb), CAST(:revision_snapshot AS jsonb),
                    :retrieval_mode, :answer_path, :original_latency_ms,
                    CAST(:answer_json AS jsonb), CAST(:citations_json AS jsonb),
                    CAST(:retrieved_chunk_ids AS jsonb), CAST(:metadata_json AS jsonb),
                    :expires_at
                )
                RETURNING id, normalized_question, created_at, expires_at
                """
            ),
            {
                **scope,
                "policy_version_id": governed.get("id") if governed else None,
                "cache_namespace": namespace,
                "query_embedding": json.dumps(query_embedding or []),
                "corpus_names": json.dumps(corpus_names),
                "source_revisions": json.dumps(source_revisions),
                "revision_snapshot": json.dumps(revision_snapshot),
                "answer_path": answer_path,
                "original_latency_ms": original_latency_ms,
                "answer_json": json.dumps(answer_json),
                "citations_json": json.dumps(citations_json),
                "retrieved_chunk_ids": json.dumps(retrieved_chunk_ids),
                "metadata_json": json.dumps(metadata_json or {}),
                "expires_at": expires_at,
            },
        ).mappings().one()
        if governed:
            max_entries = int(governed.get("max_active_entries") or 1000)
            evicted = conn.execute(
                text(
                    """
                    WITH overflow AS (
                        SELECT id
                        FROM semantic_cache_entries
                        WHERE cache_namespace = :namespace
                          AND invalidated_at IS NULL AND expires_at > now()
                        ORDER BY COALESCE(last_hit_at, created_at) DESC, id DESC
                        OFFSET :max_entries
                    )
                    UPDATE semantic_cache_entries
                    SET invalidated_at = now(),
                        metadata_json = metadata_json || '{"invalidation_reason":"capacity"}'::jsonb
                    WHERE id IN (SELECT id FROM overflow)
                    """
                ),
                {"namespace": namespace, "max_entries": max_entries},
            ).rowcount
            if evicted:
                record_policy_event(
                    event_type="invalidation",
                    reason="capacity",
                    policy_version_id=governed.get("id"),
                    actor=None,
                    metadata_json={"count": int(evicted)},
                )
    if governed:
        record_policy_event(
            event_type="store",
            reason="eligible_grounded_answer",
            policy_version_id=governed.get("id"),
            cache_entry_id=row["id"],
            actor=None,
            metadata_json={"corpora": corpus_names, "source_ids": source_ids},
        )
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in dict(row).items()}


def invalidate_cache(reason: str = "manual", *, cache_namespace: Optional[str] = None) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE semantic_cache_entries
                SET invalidated_at = now(),
                    metadata_json = metadata_json || CAST(:metadata AS jsonb)
                WHERE invalidated_at IS NULL
                  AND (:cache_namespace IS NULL OR cache_namespace = :cache_namespace)
                """
            ),
            {"metadata": json.dumps({"invalidation_reason": reason}), "cache_namespace": cache_namespace},
        )
    if result.rowcount:
        record_policy_event(event_type="invalidation", reason=reason, metadata_json={"count": int(result.rowcount)})
    return int(result.rowcount or 0)


def cache_health() -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                  COUNT(*)::bigint AS total_entries,
                  COUNT(*) FILTER (WHERE invalidated_at IS NULL AND expires_at > now())::bigint AS active_entries,
                  COUNT(*) FILTER (WHERE invalidated_at IS NOT NULL)::bigint AS invalidated_entries
                FROM semantic_cache_entries
                """
            )
        ).mappings().one()
        hits = conn.execute(text("SELECT COUNT(*)::bigint FROM semantic_cache_hits")).scalar_one()
    active_policy = get_active_policy_version()
    return {
        **dict(row),
        "hit_count": int(hits),
        "global_default": "off",
        "active_policy": active_policy,
    }
