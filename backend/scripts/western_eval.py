"""Track B evaluation tooling for the Northline (Western) corpus.

Two offline steps around the existing APP eval runner, which itself is unchanged:

    # 1. CSV + owner-approved key facts -> APP eval set (schema 1.1, no LLM judge)
    python backend/scripts/western_eval.py convert

    # 2. Run the APP eval once against the hosted stack (see docs in corpus/western/README.md),
    #    then turn its JSON report into the published scorecard and three Loom traces.
    python backend/scripts/western_eval.py scorecard --report path/to/eval-results.json

Neither step calls a model, the network or the database.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "eval" / "western"
QUESTIONS_PATH = EVAL_DIR / "EVAL_QUESTIONS.csv"
FACTS_PATH = EVAL_DIR / "facts.review.csv"
MANIFEST_PATH = EVAL_DIR / "MANIFEST.csv"
EVAL_SET_PATH = EVAL_DIR / "generated" / "eval-set-western-northline.json"
SCORECARD_DIR = REPO_ROOT / "docs" / "evaluation" / "western"

EVAL_SET_NAME = "western-northline-demo"
SUITE_VERSION = "western-northline-2026-10"
EXACT_FACT_GATE = 0.70
REFUSAL_STATUSES = {"not_found", "not_grounded"}
REFUSAL_TEXT = re.compile(
    r"not found in provided sources|insufficient evidence|no grounded answer"
    r"|does not (?:contain|include|cover|state|reproduce|specify)"
    r"|(?:is|are) not (?:covered|stated|specified|included)",
    re.IGNORECASE,
)
SCORECARD_COLUMNS = [
    "qid",
    "split",
    "scored_as",
    "expected_route",
    "predicted_route",
    "router_would_pick",
    "used_doc_ids",
    "answer_ok",
    "citation_ok",
    "refused_ok",
    "status",
    "runner_status",
    "latency_ms",
    "notes",
]


class WesternEvalError(ValueError):
    """The eval inputs are inconsistent; nothing was written."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def _split_list(value: str, separator: str) -> list[str]:
    return [item.strip() for item in (value or "").split(separator) if item.strip()]


def _scored_as(facts: list[dict[str, str]]) -> str:
    outcomes = {row["expected_outcome"] for row in facts}
    if len(outcomes) != 1 or not outcomes <= {"answer", "refuse", "denied"}:
        raise WesternEvalError(f"inconsistent expected_outcome {sorted(outcomes)}")
    return outcomes.pop()


def build_eval_set(questions: list[dict[str, str]], facts: list[dict[str, str]]) -> dict[str, Any]:
    facts_by_qid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in facts:
        facts_by_qid[row["qid"]].append(row)
    qids = [row["qid"] for row in questions]
    missing = sorted(set(qids) - set(facts_by_qid))
    unknown = sorted(set(facts_by_qid) - set(qids))
    if missing or unknown:
        raise WesternEvalError(f"facts file mismatch: missing={missing} unknown={unknown}")

    items = []
    for question in questions:
        qid = question["qid"]
        rows = facts_by_qid[qid]
        try:
            scored_as = _scored_as(rows)
        except WesternEvalError as exc:
            raise WesternEvalError(f"{qid}: {exc}") from exc
        item: dict[str, Any] = {
            "case_id": qid,
            "question": question["question"],
            "question_type": question["split"],
            "difficulty": question.get("difficulty") or "easy",
            "rationale": question["gold_answer"],
        }
        if scored_as == "answer":
            documents = _split_list(question["gold_doc_ids"], ";")
            if not documents:
                raise WesternEvalError(f"{qid}: answer item without gold_doc_ids")
            item.update(
                expectation="answer",
                expected_documents=documents,
                required_facts=[
                    {
                        "id": row["fact_id"],
                        "any_of": _split_list(row["any_of"], "|"),
                        "evidence_required": row["evidence_required"].lower() != "false",
                    }
                    for row in rows
                ],
                source_sections=[],
            )
            if any(not fact["any_of"] for fact in item["required_facts"]):
                raise WesternEvalError(f"{qid}: a required fact has no aliases")
        else:
            item.update(expectation="refuse", expected_documents=[], required_facts=[])
        items.append(item)

    return {
        "schema_version": "1.1",
        "eval_set": EVAL_SET_NAME,
        "suite_version": SUITE_VERSION,
        "note": "Synthetic Northline Analytics corpus. Generated from eval/western; do not edit.",
        "questions": items,
    }


def _doc_ids_by_name(manifest: list[dict[str, str]]) -> dict[str, str]:
    return {Path(row["filename"]).stem.lower(): row["id"] for row in manifest}


def _predicted_route(row: dict[str, Any]) -> str:
    tools = [str(a.get("tool") or "") for a in row.get("attempt_diagnostics") or []]
    tools = tools or list(row.get("tools_used") or [])
    route = "hybrid"
    if len(tools) > 1:
        route += "→keyword"
    if "get_document_excerpt" in tools:
        route += "→excerpt"
    return route


def _router_would_pick(question: str) -> str:
    try:
        sys.path.insert(0, str(REPO_ROOT / "backend"))
        from app.core_rag.query_router import route_query

        return route_query(
            question=question, explicit_mode=None, default_mode="hybrid"
        ).selected_mode
    except Exception:  # The scorecard must not depend on backend import health.
        return "unavailable"


def score_rows(
    report: dict[str, Any],
    questions: list[dict[str, str]],
    facts: list[dict[str, str]],
    manifest: list[dict[str, str]],
    *,
    router=_router_would_pick,
) -> list[dict[str, Any]]:
    rows_by_qid = {row.get("case_id"): row for row in report.get("rows") or []}
    facts_by_qid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fact in facts:
        facts_by_qid[fact["qid"]].append(fact)
    doc_ids = _doc_ids_by_name(manifest)
    known_ids = set(doc_ids.values())

    scored = []
    for question in questions:
        qid = question["qid"]
        row = rows_by_qid.get(qid)
        scored_as = _scored_as(facts_by_qid[qid])
        split = "refuse" if scored_as in {"refuse", "denied"} else question["split"]
        notes: list[str] = []
        if row is None:
            scored.append(
                {
                    **dict.fromkeys(SCORECARD_COLUMNS, ""),
                    "qid": qid,
                    "split": split,
                    "scored_as": scored_as,
                    "notes": "not run",
                }
            )
            continue

        cited = [doc_ids.get(name.lower(), name) for name in row.get("cited_documents") or []]
        status = str(row.get("grounding_status") or "")
        answer = str(row.get("generated_answer") or "")
        refused = status in REFUSAL_STATUSES or bool(REFUSAL_TEXT.search(answer))
        if scored_as == "answer":
            fact_results = (row.get("expected_eval") or {}).get("required_facts") or []
            answer_ok = bool(fact_results) and all(
                item.get("answer_matched")
                and (item.get("evidence_matched") if item.get("evidence_required", True) else True)
                for item in fact_results
            )
            gold = set(_split_list(question["gold_doc_ids"], ";"))
            forbidden = set(_split_list(question.get("must_not_cite", ""), ";"))
            citation_ok = bool(gold & set(cited)) and not (forbidden & set(cited))
            refused_ok: Any = "n/a"
            if forbidden & set(cited):
                notes.append(f"cited must_not_cite: {', '.join(sorted(forbidden & set(cited)))}")
            if row.get("failure_reason") == "unsafe_instruction_request":
                notes.append("blocked by input screening (did not obey the instruction)")
            elif refused:
                notes.append("declined (miss, not a wrong answer)")
            missing = [
                item.get("fact_id")
                for item in fact_results
                if not item.get("answer_matched")
                or (item.get("evidence_required", True) and not item.get("evidence_matched"))
            ]
            if missing:
                notes.append(f"facts missing: {', '.join(map(str, missing))}")
        else:
            refused_ok = refused
            answer_ok = refused
            citation_ok = all(doc in known_ids for doc in cited)
            if scored_as == "denied":
                notes.append("restricted document: expected ACL denial for anonymous visitor")
            if not refused:
                notes.append("answered where refusal expected")
        if status == "needs_review":
            notes.append("held for human review")

        scored.append(
            {
                "qid": qid,
                "split": split,
                "scored_as": scored_as,
                "expected_route": question.get("expected_route", ""),
                "predicted_route": _predicted_route(row),
                "router_would_pick": router(question["question"]),
                "used_doc_ids": ";".join(cited),
                "answer_ok": answer_ok,
                "citation_ok": citation_ok,
                "refused_ok": refused_ok,
                "status": status,
                "runner_status": row.get("eval_status", ""),
                "latency_ms": row.get("end_to_end_latency_ms") or row.get("latency_ms") or "",
                "notes": "; ".join(notes),
            }
        )
    return scored


def summarize(scored: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, dict[str, Any]] = {}
    for split in ("exact_fact", "open", "refuse", "adversarial"):
        rows = [row for row in scored if row["split"] == split and row["status"]]
        if split == "refuse":
            passed = sum(1 for row in rows if row["refused_ok"] is True)
        else:
            passed = sum(
                1 for row in rows if row["answer_ok"] is True and row["citation_ok"] is True
            )
        by_split[split] = {"total": len(rows), "passed": passed}
    exact = by_split["exact_fact"]
    hit_rate = exact["passed"] / exact["total"] if exact["total"] else 0.0
    return {
        "by_split": by_split,
        "exact_fact_hit_rate": round(hit_rate, 3),
        "gate": EXACT_FACT_GATE,
        "gate_passed": hit_rate >= EXACT_FACT_GATE,
        "not_run": [row["qid"] for row in scored if not row["status"]],
    }


def render_markdown(
    scored: list[dict[str, Any]], summary: dict[str, Any], meta: dict[str, Any]
) -> str:
    lines = [
        "# Northline (Western) demo scorecard",
        "",
        "Synthetic corpus and questions (Northline Analytics Ltd). Demo evidence on a 20-question set, "
        "not a benchmark or a production accuracy claim.",
        "",
        f"- Run: {meta.get('run_label', 'n/a')}",
        f"- Model: {meta.get('model', 'n/a')}; recovery steps: {meta.get('max_recovery_steps', 'n/a')}",
        "- Scoring: exact_fact/open/adversarial pass when all key facts are present (approved in "
        "`eval/western/facts.review.csv`) and a gold document is cited without citing a `must_not_cite` "
        "document. Refuse items pass on a refusal; a refusal is never counted as an accuracy failure.",
        "",
        "| Split | Passed | Total |",
        "|---|---:|---:|",
    ]
    for split, counts in summary["by_split"].items():
        lines.append(f"| {split} | {counts['passed']} | {counts['total']} |")
    verdict = "met" if summary["gate_passed"] else "NOT met (stop and report; no tuning run)"
    lines += [
        "",
        f"exact_fact hit-rate: **{summary['exact_fact_hit_rate']:.2f}** (gate {summary['gate']:.2f}: {verdict})",
        "",
        "| " + " | ".join(SCORECARD_COLUMNS) + " |",
        "|" + "---|" * len(SCORECARD_COLUMNS),
    ]
    for row in scored:
        cells = [str(row[column]).replace("|", "/") for column in SCORECARD_COLUMNS]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def render_trace(row: dict[str, Any], scored: dict[str, Any]) -> str:
    attempts = row.get("attempt_diagnostics") or []
    lines = [
        f"# {scored['qid']} ({scored['split']})",
        "",
        f"**Question:** {row.get('question')}",
        "",
        f"**Answer:** {row.get('generated_answer')}",
        "",
        f"- Status: `{scored['status']}`; route: {scored['predicted_route']}",
        f"- Cited documents: {scored['used_doc_ids'] or 'none'}",
        f"- answer_ok={scored['answer_ok']} citation_ok={scored['citation_ok']} refused_ok={scored['refused_ok']}",
        "",
        "| Attempt | Tool | Status | Reason |",
        "|---:|---|---|---|",
    ]
    for attempt in attempts:
        lines.append(
            f"| {attempt.get('attempt')} | {attempt.get('tool')} | {attempt.get('status')} | "
            f"{str(attempt.get('reason') or '').replace('|', '/')} |"
        )
    return "\n".join(lines) + "\n"


def pick_traces(questions: list[dict[str, str]], scored: list[dict[str, Any]]) -> dict[str, str]:
    """One Loom trace per kind: passing items first, then the owner's demo_use=loom items."""
    by_qid = {row["qid"]: row for row in scored if row["status"]}
    loom = {q["qid"] for q in questions if q.get("demo_use") == "loom"}

    def passed(qid: str) -> bool:
        row = by_qid.get(qid) or {}
        if row.get("split") == "refuse":
            return row.get("refused_ok") is True
        return row.get("answer_ok") is True and row.get("citation_ok") is True

    ordered = sorted(
        (q["qid"] for q in questions), key=lambda qid: (not passed(qid), qid not in loom)
    )
    wanted = {"exact": "exact_fact", "open": "open", "refuse": "refuse"}
    picks: dict[str, str] = {}
    for kind, split in wanted.items():
        for qid in ordered:
            row = by_qid.get(qid)
            if row and row["split"] == split:
                picks[kind] = qid
                break
    return picks


def write_scorecard(report_path: Path, out_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    questions = _read_csv(QUESTIONS_PATH)
    facts = _read_csv(FACTS_PATH)
    scored = score_rows(report, questions, facts, _read_csv(MANIFEST_PATH))
    summary = summarize(scored)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "scorecard.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORECARD_COLUMNS)
        writer.writeheader()
        writer.writerows(scored)
    (out_dir / "scorecard.md").write_text(render_markdown(scored, summary, meta), encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps({**summary, "meta": meta}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows_by_qid = {row.get("case_id"): row for row in report.get("rows") or []}
    scored_by_qid = {row["qid"]: row for row in scored}
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(exist_ok=True)
    for kind, qid in pick_traces(questions, scored).items():
        (traces_dir / f"{kind}.md").write_text(
            render_trace(rows_by_qid[qid], scored_by_qid[qid]), encoding="utf-8"
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("convert", help="Write the APP eval set from the CSV and approved facts.")
    score = commands.add_parser(
        "scorecard", help="Write the scorecard from an APP eval JSON report."
    )
    score.add_argument("--report", type=Path, required=True)
    score.add_argument("--out", type=Path, default=SCORECARD_DIR)
    score.add_argument("--run-label", default="")
    score.add_argument("--model", default="gpt-4o-mini-2024-07-18")
    score.add_argument("--max-recovery-steps", default="1")
    args = parser.parse_args(argv)

    try:
        if args.command == "convert":
            eval_set = build_eval_set(_read_csv(QUESTIONS_PATH), _read_csv(FACTS_PATH))
            EVAL_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
            EVAL_SET_PATH.write_text(
                json.dumps(eval_set, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(
                f"Wrote {len(eval_set['questions'])} questions to {EVAL_SET_PATH.relative_to(REPO_ROOT)}"
            )
        else:
            meta = {
                "run_label": args.run_label,
                "model": args.model,
                "max_recovery_steps": args.max_recovery_steps,
            }
            print(json.dumps(write_scorecard(args.report, args.out, meta), indent=2))
    except WesternEvalError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
