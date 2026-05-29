import json
import re
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", (question or "").strip().lower())


def record_query_event(
    *,
    question: str,
    event_type: str,
    answer_path: Optional[str] = None,
    request_id: Optional[str] = None,
    retrieval_mode: Optional[str] = None,
    latency_ms: Optional[int] = None,
    feedback_type: Optional[str] = None,
    actor: Optional[AuthenticatedUser] = None,
    metadata_json: Optional[dict[str, Any]] = None,
) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    """
                    INSERT INTO query_events (
                        question, normalized_question, event_type, answer_path, request_id,
                        retrieval_mode, latency_ms, feedback_type, actor_external_user_id,
                        actor_email, metadata_json
                    )
                    VALUES (
                        :question, :normalized_question, :event_type, :answer_path, :request_id,
                        :retrieval_mode, :latency_ms, :feedback_type, :actor_id,
                        :actor_email, CAST(:metadata_json AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "question": question,
                    "normalized_question": normalize_question(question),
                    "event_type": event_type,
                    "answer_path": answer_path,
                    "request_id": request_id,
                    "retrieval_mode": retrieval_mode,
                    "latency_ms": latency_ms,
                    "feedback_type": feedback_type,
                    "actor_id": actor.user_id if actor else None,
                    "actor_email": actor.email if actor else None,
                    "metadata_json": json.dumps(metadata_json or {}),
                },
            ).scalar_one()
        )


def list_query_events(limit: int = 200) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, question, normalized_question, event_type, answer_path, request_id,
                       retrieval_mode, latency_ms, feedback_type, actor_external_user_id,
                       actor_email, metadata_json, created_at
                FROM query_events
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def build_failure_clusters(limit: int = 200) -> list[dict[str, Any]]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT normalized_question, MIN(question) AS sample_question, COUNT(*)::int AS query_count,
                       jsonb_agg(DISTINCT question) AS sample_questions
                FROM query_events
                WHERE event_type IN ('no_evidence', 'not_helpful', 'retry', 'failed')
                   OR answer_path = 'not_found'
                   OR feedback_type IN ('missing_evidence', 'not_helpful')
                GROUP BY normalized_question
                ORDER BY query_count DESC, normalized_question
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        clusters = []
        for row in rows:
            cluster_key = f"q:{row['normalized_question'][:160]}"
            cluster = conn.execute(
                text(
                    """
                    INSERT INTO query_failure_clusters (
                        cluster_key, label, query_count, sample_questions_json, updated_at
                    )
                    VALUES (
                        :cluster_key, :label, :query_count, CAST(:sample_questions AS jsonb), now()
                    )
                    ON CONFLICT (cluster_key)
                    DO UPDATE SET
                        query_count = EXCLUDED.query_count,
                        sample_questions_json = EXCLUDED.sample_questions_json,
                        updated_at = now()
                    RETURNING id, cluster_key, label, status, query_count, sample_questions_json,
                              annotation_json, created_at, updated_at
                    """
                ),
                {
                    "cluster_key": cluster_key,
                    "label": str(row["sample_question"] or row["normalized_question"])[:180],
                    "query_count": row["query_count"],
                    "sample_questions": json.dumps(row["sample_questions"] or []),
                },
            ).mappings().one()
            clusters.append(_jsonable(dict(cluster)))
    return clusters


def annotate_cluster(cluster_id: int, annotation_json: dict[str, Any]) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                UPDATE query_failure_clusters
                SET annotation_json = CAST(:annotation_json AS jsonb), updated_at = now()
                WHERE id = :cluster_id
                RETURNING id, cluster_key, label, status, query_count, sample_questions_json,
                          annotation_json, created_at, updated_at
                """
            ),
            {"cluster_id": cluster_id, "annotation_json": json.dumps(annotation_json)},
        ).mappings().first()
    if not row:
        raise ValueError(f"Cluster {cluster_id} not found")
    return _jsonable(dict(row))


def create_eval_pack_from_clusters(*, name: str, cluster_ids: list[int], actor: Optional[AuthenticatedUser] = None) -> dict[str, Any]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, label, sample_questions_json
                FROM query_failure_clusters
                ORDER BY id
                """
            )
        ).mappings().all()
    wanted = {int(item) for item in cluster_ids}
    rows = [row for row in rows if int(row["id"]) in wanted]
    cases = []
    for row in rows:
        questions = row["sample_questions_json"] or [row["label"]]
        for question in questions[:3]:
            cases.append({"id": f"cluster_{row['id']}_{len(cases) + 1}", "question": question, "expected_cues": []})
    with engine.begin() as conn:
        payload = conn.execute(
            text(
                """
                INSERT INTO derived_eval_packs (
                    name, cluster_ids_json, cases_json, status,
                    created_by_external_user_id, created_by_email
                )
                VALUES (
                    :name, CAST(:cluster_ids AS jsonb), CAST(:cases AS jsonb),
                    'ready', :actor_id, :actor_email
                )
                ON CONFLICT (name)
                DO UPDATE SET
                    cluster_ids_json = EXCLUDED.cluster_ids_json,
                    cases_json = EXCLUDED.cases_json,
                    status = 'ready'
                RETURNING id, name, cluster_ids_json, cases_json, status,
                          created_by_external_user_id, created_by_email, created_at
                """
            ),
            {
                "name": name,
                "cluster_ids": json.dumps(cluster_ids),
                "cases": json.dumps(cases),
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).mappings().one()
    return _jsonable(dict(payload))


def list_failure_clusters(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, cluster_key, label, status, query_count, sample_questions_json,
                       annotation_json, created_at, updated_at
                FROM query_failure_clusters
                ORDER BY query_count DESC, updated_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def list_derived_eval_packs(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, name, cluster_ids_json, cases_json, status,
                       created_by_external_user_id, created_by_email, created_at
                FROM derived_eval_packs
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
