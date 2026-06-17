import json
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.db import engine


_REDACTED = "[redacted by retention policy]"


def _days(value: int) -> int:
    return max(int(value or 0), 1)


def run_retention_policy() -> dict[str, Any]:
    results: dict[str, Any] = {}
    with engine.begin() as conn:
        if settings.RETENTION_REDACT_TEXT_FIELDS:
            results["query_events_redacted"] = int(
                conn.execute(
                    text(
                        """
                        UPDATE query_events
                        SET question = :redacted,
                            metadata_json = metadata_json || CAST(:metadata AS jsonb)
                        WHERE created_at < now() - (:days * interval '1 day')
                          AND question <> :redacted
                        """
                    ),
                    {"redacted": _REDACTED, "metadata": json.dumps({"retention_redacted": True}), "days": _days(settings.RETENTION_QUERY_EVENTS_DAYS)},
                ).rowcount
                or 0
            )
            results["feedback_redacted"] = int(
                conn.execute(
                    text(
                        """
                        UPDATE query_feedback
                        SET question = :redacted,
                            reason = CASE WHEN reason = '' THEN reason ELSE :redacted END,
                            suggested_source = NULL,
                            metadata_json = metadata_json || CAST(:metadata AS jsonb)
                        WHERE created_at < now() - (:days * interval '1 day')
                          AND question <> :redacted
                        """
                    ),
                    {"redacted": _REDACTED, "metadata": json.dumps({"retention_redacted": True}), "days": _days(settings.RETENTION_FEEDBACK_DAYS)},
                ).rowcount
                or 0
            )
            results["negative_feedback_redacted"] = int(
                conn.execute(
                    text(
                        """
                        UPDATE negative_feedback_events
                        SET question = :redacted,
                            answer_text = :redacted,
                            note = CASE WHEN note = '' THEN note ELSE :redacted END,
                            metadata_json = metadata_json || CAST(:metadata AS jsonb)
                        WHERE created_at < now() - (:days * interval '1 day')
                          AND question <> :redacted
                        """
                    ),
                    {"redacted": _REDACTED, "metadata": json.dumps({"retention_redacted": True}), "days": _days(settings.RETENTION_FEEDBACK_DAYS)},
                ).rowcount
                or 0
            )
            results["traces_redacted"] = int(
                conn.execute(
                    text(
                        """
                        UPDATE retrieval_traces
                        SET question = :redacted,
                            trace_json = trace_json || CAST(:metadata AS jsonb)
                        WHERE created_at < now() - (:days * interval '1 day')
                          AND question <> :redacted
                        """
                    ),
                    {"redacted": _REDACTED, "metadata": json.dumps({"retention_redacted": True}), "days": _days(settings.RETENTION_TRACES_DAYS)},
                ).rowcount
                or 0
            )
        results["semantic_cache_invalidated"] = int(
            conn.execute(
                text(
                    """
                    UPDATE semantic_cache_entries
                    SET invalidated_at = COALESCE(invalidated_at, now()),
                        metadata_json = metadata_json || CAST(:metadata AS jsonb)
                    WHERE created_at < now() - (:days * interval '1 day')
                      AND invalidated_at IS NULL
                    """
                ),
                {"metadata": json.dumps({"retention_invalidated": True}), "days": _days(settings.RETENTION_SEMANTIC_CACHE_DAYS)},
            ).rowcount
            or 0
        )
        results["audit_events_marked"] = int(
            conn.execute(
                text(
                    """
                    UPDATE admin_audit_events
                    SET integrity_metadata_json = integrity_metadata_json || CAST(:metadata AS jsonb)
                    WHERE created_at < now() - (:days * interval '1 day')
                      AND NOT (integrity_metadata_json ? 'retention_reviewed')
                    """
                ),
                {"metadata": json.dumps({"retention_reviewed": True}), "days": _days(settings.RETENTION_AUDIT_EXPORT_DAYS)},
            ).rowcount
            or 0
        )
    return results
