import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.repo_acl import active_direct_grant_fingerprint, can_current_user_access_source, current_acl_context
from app.profiles.resolver import get_active_profile_snapshot


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())


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
                "groups": sorted(acl.get("groups") or []),
                "local_dev_full_access": bool(acl.get("local_dev_full_access")),
                "direct_grants": active_direct_grant_fingerprint(),
            }
        ),
        "profile_snapshot_hash": _stable_hash(profiles),
        "corpus_scope_hash": _stable_hash(corpus_scope or {}),
        "retrieval_mode": retrieval_mode or "",
    }


def get_cache_entry(*, question: str, retrieval_mode: Optional[str], corpus_scope: Optional[dict[str, Any]] = None, actor: Optional[AuthenticatedUser] = None) -> Optional[dict[str, Any]]:
    scope = cache_scope(question=question, retrieval_mode=retrieval_mode, corpus_scope=corpus_scope)
    sql = text(
        """
        SELECT id, normalized_question, answer_json, citations_json, retrieved_chunk_ids_json,
               metadata_json, created_at, expires_at
        FROM semantic_cache_entries
        WHERE normalized_question = :normalized_question
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
        row = conn.execute(sql, scope).mappings().first()
        if not row:
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
) -> dict[str, Any]:
    scope = cache_scope(question=question, retrieval_mode=retrieval_mode, corpus_scope=corpus_scope)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(ttl_seconds, 1))
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO semantic_cache_entries (
                    normalized_question, query_embedding_json, acl_scope_hash,
                    profile_snapshot_hash, corpus_scope_hash, retrieval_mode,
                    answer_json, citations_json, retrieved_chunk_ids_json,
                    metadata_json, expires_at
                )
                VALUES (
                    :normalized_question, CAST(:query_embedding AS jsonb), :acl_scope_hash,
                    :profile_snapshot_hash, :corpus_scope_hash, :retrieval_mode,
                    CAST(:answer_json AS jsonb), CAST(:citations_json AS jsonb),
                    CAST(:retrieved_chunk_ids AS jsonb), CAST(:metadata_json AS jsonb),
                    :expires_at
                )
                RETURNING id, normalized_question, created_at, expires_at
                """
            ),
            {
                **scope,
                "query_embedding": json.dumps(query_embedding or []),
                "answer_json": json.dumps(answer_json),
                "citations_json": json.dumps(citations_json),
                "retrieved_chunk_ids": json.dumps(retrieved_chunk_ids),
                "metadata_json": json.dumps(metadata_json or {}),
                "expires_at": expires_at,
            },
        ).mappings().one()
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in dict(row).items()}


def invalidate_cache(reason: str = "manual") -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE semantic_cache_entries
                SET invalidated_at = now(),
                    metadata_json = metadata_json || CAST(:metadata AS jsonb)
                WHERE invalidated_at IS NULL
                """
            ),
            {"metadata": json.dumps({"invalidation_reason": reason})},
        )
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
    return {**dict(row), "hit_count": int(hits)}
