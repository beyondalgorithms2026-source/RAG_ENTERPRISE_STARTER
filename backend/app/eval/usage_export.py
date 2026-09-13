"""Export sanitized generation cost aggregates for an isolated eval database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.db import engine
from sqlalchemy import text


class UsageExportError(ValueError):
    """The eval report cannot be joined safely to usage telemetry."""


def _request_ids(report: dict[str, Any]) -> tuple[list[str], int]:
    rows = report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise UsageExportError("evaluation report rows are required")
    request_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise UsageExportError("every evaluation row must be an object")
        values = row.get("backend_request_ids")
        if not isinstance(values, list):
            raise UsageExportError("every evaluation row requires backend_request_ids")
        for value in values:
            request_id = str(value).strip()
            if request_id and request_id not in seen:
                seen.add(request_id)
                request_ids.append(request_id)
    if not request_ids:
        raise UsageExportError("evaluation report contains no backend request ids")
    if len(request_ids) > 1000:
        raise UsageExportError("evaluation report exceeds the 1000-request export limit")
    return request_ids, len(rows)


def _usage_rows(request_ids: list[str]) -> dict[str, dict[str, Any]]:
    statement = text(
        """
        SELECT request_id,
               ROUND(SUM(cost_usd)::numeric, 8) AS cost_usd,
               SUM(call_count)::bigint AS generation_call_count,
               SUM(total_tokens)::bigint AS total_tokens,
               BOOL_OR(estimated) AS any_estimated
        FROM generation_usage_events
        WHERE request_id = ANY(CAST(:request_ids AS text[]))
        GROUP BY request_id
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(statement, {"request_ids": request_ids}).mappings().all()
    return {str(row["request_id"]): dict(row) for row in rows}


def build_usage_export(
    report: dict[str, Any], *, usage_rows: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    request_ids, query_count = _request_ids(report)
    by_id = _usage_rows(request_ids) if usage_rows is None else usage_rows
    requests: list[dict[str, Any]] = []
    total_cost = 0.0
    generation_request_count = 0
    generation_call_count = 0
    any_estimated = False
    for request_id in request_ids:
        row = by_id.get(request_id) or {}
        cost = float(row.get("cost_usd") or 0.0)
        calls = int(row.get("generation_call_count") or 0)
        total_cost += cost
        generation_call_count += calls
        if calls:
            generation_request_count += 1
        any_estimated = any_estimated or bool(row.get("any_estimated"))
        requests.append(
            {
                "request_id": request_id,
                "cost_usd": round(cost, 8),
                "generation_call_count": calls,
                "total_tokens": int(row.get("total_tokens") or 0),
                "estimated": bool(row.get("any_estimated")),
            }
        )
    return {
        "schema_version": "1.0",
        "query_count": query_count,
        "backend_request_count": len(request_ids),
        "generation_request_count": generation_request_count,
        "generation_call_count": generation_call_count,
        "total_cost_usd": round(total_cost, 8),
        "any_estimated": any_estimated,
        "requests": requests,
        "exclusions": ["corpus_embedding_costs"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.eval_report.read_text(encoding="utf-8"))
        payload = build_usage_export(report)
    except (OSError, json.JSONDecodeError, UsageExportError) as exc:
        print(f"error: cannot export evaluation usage: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"Exported {payload['backend_request_count']} request aggregates for "
        f"{payload['query_count']} evaluation cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
