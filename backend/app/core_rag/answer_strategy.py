import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional

from app.db.repo_source_parts import list_source_parts


AGGREGATION_TERMS = ("total", "sum", "average", "avg", "count", "by ", "per ")
TABLE_TERMS = ("sales", "revenue", "amount", "region", "spreadsheet", "excel", "xlsx", "sheet", "table", "rows")
EMAIL_TERMS = ("email", "emails", "mail", "message", "messages")


@dataclass(frozen=True)
class AnswerStrategyDecision:
    strategy: str
    answer_safety: str
    reason: str
    aggregation: bool = False
    multi_source: bool = False


@dataclass(frozen=True)
class StructuredAggregationResult:
    answer: str
    citations: list[Any]
    debug: dict[str, Any]


def select_answer_strategy(question: str) -> AnswerStrategyDecision:
    normalized = _normalize(question)
    has_aggregation = any(term in normalized for term in AGGREGATION_TERMS) and any(term in normalized for term in TABLE_TERMS)
    has_email = any(term in normalized for term in EMAIL_TERMS)
    if has_aggregation and has_email:
        return AnswerStrategyDecision(
            strategy="multi_source_synthesis",
            answer_safety="requires_complete_table",
            reason="aggregation_plus_email_signal",
            aggregation=True,
            multi_source=True,
        )
    if has_aggregation:
        return AnswerStrategyDecision(
            strategy="structured_aggregation",
            answer_safety="requires_complete_table",
            reason="aggregation_table_signal",
            aggregation=True,
        )
    return AnswerStrategyDecision(strategy="retrieval_answer", answer_safety="grounded", reason="default_retrieval")


def try_structured_aggregation(
    *,
    question: str,
    raw_chunks: list[Any],
    make_citation,
) -> Optional[StructuredAggregationResult]:
    parsed_request = _parse_sum_by_request(question)
    source_ids = _xlsx_source_ids(raw_chunks)
    if not parsed_request or not source_ids:
        return _unsafe_aggregation_result(reason="structured_table_unavailable")

    measure_hint, group_hint = parsed_request
    for source_id in source_ids:
        parts = [part for part in list_source_parts(source_id) if part.part_type == "sheet" and (part.content_text or "").strip()]
        for part in parts:
            parsed_sheet = _parse_sheet(part.content_text or "")
            if not parsed_sheet:
                continue
            headers, rows = parsed_sheet
            measure_col = _match_header(headers, measure_hint)
            group_col = _match_header(headers, group_hint)
            if measure_col is None or group_col is None:
                continue
            totals: dict[str, float] = defaultdict(float)
            row_count = 0
            for row in rows:
                group = row.get(group_col, "").strip()
                amount = _parse_number(row.get(measure_col, ""))
                if group and amount is not None:
                    totals[group] += amount
                    row_count += 1
            if not totals:
                continue
            sorted_totals = sorted(totals.items(), key=lambda item: item[0].lower())
            lines = [f"- {group}: {_format_number(total)}" for group, total in sorted_totals]
            citation = make_citation(part, f"{part.title or 'Sheet'} complete sheet")
            return StructuredAggregationResult(
                answer="Computed from the complete spreadsheet sheet:\n\n" + "\n".join(lines),
                citations=[citation],
                debug={
                    "answer_safety": "computed_from_complete_table",
                    "structured_aggregation": {
                        "status": "computed",
                        "source_id": source_id,
                        "source_part_id": part.id,
                        "sheet": part.title,
                        "measure": measure_col,
                        "group_by": group_col,
                        "row_count": row_count,
                    },
                },
            )
    return _unsafe_aggregation_result(reason="matching_headers_unavailable")


def _unsafe_aggregation_result(*, reason: str) -> StructuredAggregationResult:
    return StructuredAggregationResult(
        answer="I cannot safely calculate this from partial retrieved snippets. I need a complete structured spreadsheet/table with identifiable columns before answering.",
        citations=[],
        debug={"answer_safety": "insufficient_evidence", "structured_aggregation": {"status": "refused", "reason": reason}},
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _parse_sum_by_request(question: str) -> Optional[tuple[str, str]]:
    normalized = _normalize(question)
    match = re.search(r"(?:total|sum) ([a-z0-9 _-]+?) by ([a-z0-9 _-]+?)(?:\?|$)", normalized)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    if "sales" in normalized and "region" in normalized:
        return "sales", "region"
    if "revenue" in normalized and "region" in normalized:
        return "revenue", "region"
    return None


def _xlsx_source_ids(raw_chunks: list[Any]) -> list[int]:
    source_ids: list[int] = []
    seen: set[int] = set()
    for chunk in raw_chunks:
        source_type = str(getattr(chunk, "source_type", "") or "").lower()
        source_id = getattr(chunk, "source_id", None)
        if "xlsx" in source_type and source_id is not None and int(source_id) not in seen:
            seen.add(int(source_id))
            source_ids.append(int(source_id))
    return source_ids


def _parse_sheet(content_text: str) -> Optional[tuple[dict[str, str], list[dict[str, str]]]]:
    rows: list[dict[str, str]] = []
    for line in content_text.splitlines():
        row: dict[str, str] = {}
        for coordinate, value in re.findall(r"([A-Z]+)\d+=([^|]+)", line):
            row[coordinate.strip()] = value.strip()
        if row:
            rows.append(row)
    if len(rows) < 2:
        return None
    headers = {column: value for column, value in rows[0].items() if value}
    if not headers:
        return None
    return headers, rows[1:]


def _match_header(headers: dict[str, str], hint: str) -> Optional[str]:
    normalized_hint = _normalize(hint).replace("_", " ")
    for column, header in headers.items():
        normalized_header = _normalize(header).replace("_", " ")
        if normalized_header == normalized_hint or normalized_hint in normalized_header or normalized_header in normalized_hint:
            return column
    return None


def _parse_number(value: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"
