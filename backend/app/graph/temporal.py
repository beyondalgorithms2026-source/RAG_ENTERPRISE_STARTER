import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Optional

from app.core.config import settings


TEMPORAL_ARTIFACT_VERSION = "m13-rule-based-temporal-v1"

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_FULL_DATE_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\s+(?P<day>\d{{1,2}}),\s+(?P<year>\d{{4}})\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\b")
_MONTH_YEAR_RE = re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\s+(?P<year>\d{{4}})\b", re.IGNORECASE)
_RANGE_RE = re.compile(
    rf"\b(?:from\s+)?(?P<start>{_MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"
    rf"\s+(?:through|to|until|-)\s+"
    rf"(?P<end>{_MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    rf"\b(?:effective(?:\s+as\s+of)?|in\s+effect\s+on)\s+"
    rf"(?P<date>{_MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_VALID_UNTIL_RE = re.compile(
    rf"\b(?:valid\s+(?:through|until)|expires?\s+on)\s+"
    rf"(?P<date>{_MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(
    r"\b(?:version|ver\.|revision|rev\.|amendment)\s*(?:no\.\s*)?(?P<value>[A-Za-z0-9][A-Za-z0-9._-]*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TemporalResult:
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    reason: str = "temporal_disabled"
    artifact_version: str = TEMPORAL_ARTIFACT_VERSION


def _normalize_date_text(value: str) -> Optional[str]:
    raw = value.strip()
    iso_match = _ISO_DATE_RE.fullmatch(raw)
    if iso_match:
        year = int(iso_match.group("year"))
        month = int(iso_match.group("month"))
        day = int(iso_match.group("day"))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    full_match = _FULL_DATE_RE.fullmatch(raw)
    if full_match:
        month_name = full_match.group("month").lower()
        month = _MONTHS.get(month_name)
        if month is None:
            return None
        try:
            return date(int(full_match.group("year")), month, int(full_match.group("day"))).isoformat()
        except ValueError:
            return None

    month_year_match = _MONTH_YEAR_RE.fullmatch(raw)
    if month_year_match:
        month_name = month_year_match.group("month").lower()
        month = _MONTHS.get(month_name)
        if month is None:
            return None
        try:
            return date(int(month_year_match.group("year")), month, 1).isoformat()
        except ValueError:
            return None

    return None


def _dedupe_dicts(items: Iterable[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def analyze_temporal_metadata(*, text: str) -> TemporalResult:
    if not (settings.ENABLE_TEMPORAL or settings.EXTRACT_TEMPORAL_METADATA):
        return TemporalResult()

    expressions: list[dict[str, Any]] = []
    effective_start = None
    effective_end = None
    version_refs: list[dict[str, Any]] = []

    for match in _EFFECTIVE_RE.finditer(text):
        evidence = match.group(0)
        normalized = _normalize_date_text(match.group("date"))
        if normalized is None:
            continue
        effective_start = normalized
        expressions.append(
            {
                "type": "effective_date",
                "text": evidence,
                "normalized": normalized,
                "confidence": "high",
                "evidence": evidence,
            }
        )

    for match in _VALID_UNTIL_RE.finditer(text):
        evidence = match.group(0)
        normalized = _normalize_date_text(match.group("date"))
        if normalized is None:
            continue
        effective_end = normalized
        expressions.append(
            {
                "type": "valid_until",
                "text": evidence,
                "normalized": normalized,
                "confidence": "high",
                "evidence": evidence,
            }
        )

    for match in _RANGE_RE.finditer(text):
        evidence = match.group(0)
        start_normalized = _normalize_date_text(match.group("start"))
        end_normalized = _normalize_date_text(match.group("end"))
        if start_normalized is None or end_normalized is None:
            continue
        effective_start = effective_start or start_normalized
        effective_end = effective_end or end_normalized
        expressions.append(
            {
                "type": "date_range",
                "text": evidence,
                "normalized": {"start": start_normalized, "end": end_normalized},
                "confidence": "high",
                "evidence": evidence,
            }
        )

    for matcher, expression_type, confidence in (
        (_FULL_DATE_RE, "explicit_date", "high"),
        (_ISO_DATE_RE, "explicit_date", "high"),
        (_MONTH_YEAR_RE, "month_year", "low"),
    ):
        for match in matcher.finditer(text):
            evidence = match.group(0)
            normalized = _normalize_date_text(evidence)
            if normalized is None:
                continue
            context_before = text[max(0, match.start() - 32) : match.start()].lower()
            expressions.append(
                {
                    "type": expression_type,
                    "text": evidence,
                    "normalized": normalized,
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )
            if expression_type == "explicit_date":
                if "effective" in context_before or "in effect on" in context_before:
                    effective_start = effective_start or normalized
                    expressions.append(
                        {
                            "type": "effective_date",
                            "text": evidence,
                            "normalized": normalized,
                            "confidence": "high",
                            "evidence": evidence,
                        }
                    )
                if "valid until" in context_before or "valid through" in context_before or "expires on" in context_before:
                    effective_end = effective_end or normalized
                    expressions.append(
                        {
                            "type": "valid_until",
                            "text": evidence,
                            "normalized": normalized,
                            "confidence": "high",
                            "evidence": evidence,
                        }
                    )

    for match in _VERSION_RE.finditer(text):
        evidence = match.group(0)
        version_refs.append(
            {
                "type": "document_version_reference",
                "text": evidence,
                "value": match.group("value"),
                "confidence": "medium",
                "evidence": evidence,
            }
        )

    expressions = _dedupe_dicts(expressions, ("type", "text"))
    version_refs = _dedupe_dicts(version_refs, ("type", "text", "value"))

    metadata: dict[str, Any] = {
        "expressions": expressions,
        "normalized_dates": [item["normalized"] for item in expressions if isinstance(item.get("normalized"), str)],
        "document_version_refs": version_refs,
        "artifact_version": TEMPORAL_ARTIFACT_VERSION,
        "fallback_reason": None,
    }

    if effective_start or effective_end:
        metadata["effective_window"] = {
            "start": effective_start,
            "end": effective_end,
            "confidence": "high" if effective_start and effective_end else "medium",
        }
    else:
        metadata["effective_window"] = None

    if not expressions and not version_refs:
        metadata["confidence"] = "none"
        metadata["fallback_reason"] = "no_reliable_temporal_metadata"
        return TemporalResult(
            metadata=metadata,
            enabled=True,
            reason="no_reliable_temporal_metadata",
        )

    metadata["confidence"] = "high" if any(item["confidence"] == "high" for item in expressions) else "low"
    return TemporalResult(
        metadata=metadata,
        enabled=True,
        reason="m13_rule_based_temporal_complete",
    )


def summarize_temporal_metadata(*, chunk_temporal_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    reliable_chunks = [
        item for item in chunk_temporal_metadata if item and item.get("confidence") in {"high", "medium", "low"}
    ]
    normalized_dates: list[str] = []
    version_refs: list[dict[str, Any]] = []
    fallback_count = 0
    for item in chunk_temporal_metadata:
        if not item:
            continue
        if item.get("fallback_reason"):
            fallback_count += 1
        normalized_dates.extend(value for value in item.get("normalized_dates", []) if isinstance(value, str))
        version_refs.extend(item.get("document_version_refs", []))

    normalized_dates = sorted(set(normalized_dates))
    version_refs = _dedupe_dicts(version_refs, ("type", "text", "value"))

    if not reliable_chunks:
        return {
            "artifact_version": TEMPORAL_ARTIFACT_VERSION,
            "confidence": "none",
            "fallback_reason": "no_reliable_temporal_metadata",
            "reliable_chunk_count": 0,
            "fallback_chunk_count": fallback_count,
            "document_version_refs": version_refs,
        }

    effective_starts = [
        item.get("effective_window", {}).get("start")
        for item in reliable_chunks
        if isinstance(item.get("effective_window"), dict) and item.get("effective_window", {}).get("start")
    ]
    effective_ends = [
        item.get("effective_window", {}).get("end")
        for item in reliable_chunks
        if isinstance(item.get("effective_window"), dict) and item.get("effective_window", {}).get("end")
    ]
    return {
        "artifact_version": TEMPORAL_ARTIFACT_VERSION,
        "confidence": "high" if any(item.get("confidence") == "high" for item in reliable_chunks) else "low",
        "fallback_reason": None,
        "reliable_chunk_count": len(reliable_chunks),
        "fallback_chunk_count": fallback_count,
        "date_bounds": {
            "earliest": normalized_dates[0] if normalized_dates else None,
            "latest": normalized_dates[-1] if normalized_dates else None,
        },
        "effective_window": {
            "start": min(effective_starts) if effective_starts else None,
            "end": max(effective_ends) if effective_ends else None,
        },
        "document_version_refs": version_refs,
    }
