from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings


def _as_utc(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def source_freshness(source: Any, *, now: Optional[datetime] = None) -> dict[str, Any]:
    current = _as_utc(now) or datetime.now(timezone.utc)
    metadata = dict(getattr(source, "source_metadata_json", {}) or {})
    source_type = str(getattr(source, "source_type", "") or "")
    last_synced = _as_utc(getattr(source, "last_synced_at", None))
    last_ingested = _as_utc(getattr(source, "last_ingested_at", None))
    last_enriched = _as_utc(getattr(source, "last_enriched_at", None))
    observed = last_synced if source_type == "db_row" else last_ingested

    threshold_hours = int(metadata.get("freshness_threshold_hours") or settings.SOURCE_STALE_AFTER_HOURS)
    threshold_hours = max(1, threshold_hours)
    if observed is None:
        status = "unknown"
        age_seconds = None
    else:
        age_seconds = max(0, int((current - observed).total_seconds()))
        status = "stale" if age_seconds > threshold_hours * 3600 else "fresh"

    return {
        "status": status,
        "observed_at": observed.isoformat() if observed else None,
        "age_seconds": age_seconds,
        "threshold_hours": threshold_hours,
        "last_synced_at": last_synced.isoformat() if last_synced else None,
        "last_ingested_at": last_ingested.isoformat() if last_ingested else None,
        "last_enriched_at": last_enriched.isoformat() if last_enriched else None,
    }


def freshness_by_source_ids(source_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not source_ids:
        return {}
    from app.db.repo_sources import get_sources_by_ids

    return {source_id: source_freshness(source) for source_id, source in get_sources_by_ids(source_ids).items()}
