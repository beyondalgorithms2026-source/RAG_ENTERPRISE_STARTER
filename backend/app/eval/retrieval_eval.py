import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.core_rag.retrieval import DeepLookupRequest, SearchRequest, perform_deep_lookup, perform_search
from app.profiles.resolver import get_active_profile_snapshot, get_effective_retrieval


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEMO_FILE = PROJECT_ROOT / "demo_questions.md"
EVAL_FIXTURE_DIR = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "eval"
RETRIEVAL_CASES_FILE = EVAL_FIXTURE_DIR / "retrieval_cases.json"
DEFAULT_REPORT_FILE = PROJECT_ROOT / "eval_report_retrieval.json"


def parse_demo_questions() -> List[Dict[str, Any]]:
    if not DEMO_FILE.exists():
        logger.error("Demo file not found at %s", DEMO_FILE)
        return []

    with open(DEMO_FILE, "r", encoding="utf-8") as handle:
        content = handle.read()

    match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
    if not match:
        logger.error("Could not find JSON block in demo_questions.md")
        return []

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON demo questions: %s", exc)
        return []


def load_eval_cases(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    case_path = path or RETRIEVAL_CASES_FILE
    if not case_path.exists():
        logger.error("Eval case file not found at %s", case_path)
        return []

    with open(case_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data if isinstance(data, list) else []


def write_eval_report(report: Dict[str, Any], path: Optional[Path] = None) -> Path:
    report_path = path or DEFAULT_REPORT_FILE
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return report_path


def print_debug_table(results: List[Dict[str, Any]]):
    print(
        f"\n{'Rank':<5} | {'Score':<6} | {'Type':<10} | {'File Name':<20} | "
        f"{'Heading':<20} | {'Locator':<16} | {'Snippet (First 80 chars)'}"
    )
    print("-" * 140)
    for index, result in enumerate(results):
        snippet = result["snippet"].replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:80] + "..."
        print(
            f"{index + 1:<5} | {result.get('score', 0.0):<6.3f} | {result.get('source_type', '')[:10]:<10} | "
            f"{result.get('file_name', '')[:20]:<20} | {result.get('heading', '')[:20]:<20} | "
            f"{str(result.get('locator', ''))[:16]:<16} | {snippet}"
        )
    print()


def _resolve_legacy_eval_mode(mode: str) -> str:
    if mode not in {"vector", "keyword", "hybrid", "graph_hybrid", "full"}:
        return "hybrid"
    return mode


def _evaluate_expected_matches(*, results: List[Dict[str, Any]], expected: Dict[str, Any]) -> Dict[str, Any]:
    headings_any = [item.lower() for item in expected.get("headings_any", [])]
    headings_all = [item.lower() for item in expected.get("headings_all", [])]
    snippet_keywords_any = [item.lower() for item in expected.get("snippet_keywords_any", [])]
    snippet_keywords_all = [item.lower() for item in expected.get("snippet_keywords_all", [])]
    source_types_any = [item.lower() for item in expected.get("source_types_any", [])]

    best_match_rank = None
    matched_heading = None
    matched_source_type = None
    matched_keywords: list[str] = []
    passed = False

    for index, result in enumerate(results):
        heading = str(result.get("heading", "")).lower()
        snippet = str(result.get("snippet", "")).lower()
        source_type = str(result.get("source_type", "")).lower()
        combined_text = f"{heading} {snippet}"

        heading_ok = True
        if headings_any:
            heading_ok = any(item in heading for item in headings_any)
        if heading_ok and headings_all:
            heading_ok = all(item in heading for item in headings_all)

        snippet_ok = True
        local_keyword_matches: list[str] = []
        if snippet_keywords_any:
            snippet_ok = False
            for keyword in snippet_keywords_any:
                if keyword in combined_text:
                    snippet_ok = True
                    local_keyword_matches.append(keyword)
        if snippet_ok and snippet_keywords_all:
            snippet_ok = all(keyword in combined_text for keyword in snippet_keywords_all)
            if snippet_ok:
                local_keyword_matches.extend(snippet_keywords_all)

        source_type_ok = True
        if source_types_any:
            source_type_ok = source_type in source_types_any

        if heading_ok and snippet_ok and source_type_ok:
            passed = True
            best_match_rank = index + 1
            matched_heading = result.get("heading")
            matched_source_type = result.get("source_type")
            matched_keywords = sorted(set(local_keyword_matches))
            break

    return {
        "passed": passed,
        "best_match_rank": best_match_rank,
        "matched_heading": matched_heading,
        "matched_source_type": matched_source_type,
        "matched_keywords": matched_keywords,
    }


def evaluate_search_case(case: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    request_payload = dict(case.get("request", {}))
    if "question" not in request_payload:
        return {"id": case.get("id", "unknown"), "status": "FAIL", "error": "missing_question"}

    surface = case.get("surface", "search")
    try:
        if surface == "deep_lookup":
            request = DeepLookupRequest(**request_payload)
            response = perform_deep_lookup(request)
            requested_mode = "deep_lookup"
        else:
            request = SearchRequest(**request_payload)
            response = perform_search(request)
            requested_mode = request.mode
    except Exception as exc:
        logger.error("Eval search failed for case '%s': %s", case.get("id", "unknown"), exc)
        return {"id": case.get("id", "unknown"), "status": "FAIL", "error": str(exc)}

    raw_results = [item.model_dump() for item in response.results]
    if debug:
        print(f"DEBUG CASE {case.get('id', 'unknown')} ({response.mode})")
        print_debug_table(raw_results)

    expected = dict(case.get("expected", {}))
    match_info = _evaluate_expected_matches(results=raw_results, expected=expected)

    expected_mode = expected.get("mode")
    expected_fallback = expected.get("fallback_to")
    mode_ok = True if not expected_mode else response.mode == expected_mode
    fallback_ok = True if not expected_fallback else response.mode == expected_fallback
    passed = bool(match_info["passed"] and mode_ok and fallback_ok)
    response_trace = getattr(response, "debug_info", None) or {}

    return {
        "id": case.get("id", "unknown"),
        "question": request.question,
        "status": "PASS" if passed else "FAIL",
        "requested_mode": requested_mode,
        "resolved_mode": response.mode,
        "best_match_rank": match_info["best_match_rank"],
        "matched_heading": match_info["matched_heading"],
        "matched_source_type": match_info["matched_source_type"],
        "matched_keywords": match_info["matched_keywords"],
        "result_count": len(raw_results),
        "expected": expected,
        "observed": {
            "top_headings": [item.get("heading") for item in raw_results[:3]],
            "top_source_types": [item.get("source_type") for item in raw_results[:3]],
        },
        "trace": {
            "request_id": response_trace.get("request_id"),
            "retrieval_path_used": response_trace.get("retrieval_path_used"),
            "candidate_counts": response_trace.get("candidate_counts", {}),
            "latency_ms": response_trace.get("latency_ms", {}),
            "fallback_reason": response_trace.get("fallback_reason"),
            "score_diagnostics": response_trace.get("score_diagnostics", []),
        },
    }


def evaluate_question(
    question_data: Dict[str, Any],
    default_k: int,
    global_source_type: Optional[str] = None,
    debug: bool = False,
    mode: str = "vector",
) -> Dict[str, Any]:
    question = question_data["question"]
    k = question_data.get("k", default_k)
    filters = dict(question_data.get("filters", {}))
    source_type = filters.get("source_type")
    if not source_type and global_source_type and global_source_type.lower() != "all":
        filters["source_type"] = global_source_type

    case = {
        "id": question_data.get("id", "Unknown"),
        "request": {
            "question": question,
            "k": k,
            "mode": _resolve_legacy_eval_mode(mode),
            "filters": filters or None,
        },
        "expected": {
            "headings_any": [question_data.get("heading_hint")] if question_data.get("heading_hint") else [],
            "snippet_keywords_any": question_data.get("keywords_any", []),
            "snippet_keywords_all": question_data.get("keywords_all", []),
        },
    }
    return evaluate_search_case(case, debug=debug)


def run_retrieval_eval(
    *,
    cases: List[Dict[str, Any]],
    report_path: Optional[Path] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    results = [evaluate_search_case(case, debug=debug) for case in cases]
    passed = sum(1 for item in results if item["status"] == "PASS")
    total = len(results)
    failures = [item for item in results if item["status"] == "FAIL"]
    evaluated_modes = sorted({item.get("requested_mode") or item.get("resolved_mode") for item in results if item})
    report = {
        "summary": {
            "kind": "retrieval",
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate_percent": round((passed / total) * 100.0, 2) if total else 0.0,
            "evaluated_modes": evaluated_modes,
        },
        "report_metadata": {
            "active_profiles": get_active_profile_snapshot(),
            "retrieval_settings": get_effective_retrieval().model_dump(),
        },
        "active_profiles": get_active_profile_snapshot(),
        "results": results,
        "failures": failures,
    }
    report_file = write_eval_report(report, report_path)
    report["report_path"] = str(report_file)
    return report


def run_eval(args):
    if args.debug_question:
        question_data = {
            "id": "DEBUG_1",
            "question": args.debug_question,
            "keywords_any": [],
            "keywords_all": [],
            "heading_hint": "",
            "k": args.k,
        }
        result = evaluate_question(
            question_data,
            args.k,
            global_source_type=args.source_type,
            debug=True,
            mode=args.mode or "hybrid",
        )
        print("DEBUG QUESTION RESULT:")
        print(json.dumps(result, indent=2))
        return

    cases = load_eval_cases()
    if not cases:
        return

    if args.mode:
        rewritten_cases = []
        for case in cases:
            if case.get("surface") == "deep_lookup":
                rewritten_cases.append(case)
            else:
                rewritten_cases.append(dict(case, request={**case.get("request", {}), "mode": args.mode}))
        cases = rewritten_cases
    if args.limit:
        cases = cases[: args.limit]

    report = run_retrieval_eval(cases=cases, debug=args.debug)
    print(json.dumps(report["summary"], indent=2))
    print(f"Report saved to: {report['report_path']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="M19 Retrieval Evaluation Harness")
    parser.add_argument("--k", type=int, default=6, help="Default k retrieved chunks")
    parser.add_argument("--limit", type=int, help="Limit to N cases")
    parser.add_argument("--debug", action="store_true", help="Print debug top-k tables")
    parser.add_argument("--debug-question", type=str, help="Debug single ad-hoc question")
    parser.add_argument("--source-type", type=str, help="Filter by source type (pdf, docx, pptx, xlsx, eml)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["vector", "keyword", "hybrid", "graph_hybrid", "full"],
        help="Search mode override",
    )
    run_eval(parser.parse_args())
