import argparse
import json
from contextlib import contextmanager
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.api.ask import ask_endpoint
from app.core.config import settings
from app.core.logging import logger
from app.core_rag.answering import AskRequest
from app.core_rag.retrieval import DeepLookupRequest, SearchFilters, SearchRequest, perform_deep_lookup, perform_search
from app.eval.retrieval_eval import PROJECT_ROOT, write_eval_report
from app.profiles.models import RerankerProfileConfig, RetrievalProfileConfig
from app.profiles.resolver import get_active_profile_snapshot, get_effective_reranker, get_effective_retrieval


EVAL_FIXTURE_DIR = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "eval"
BENCHMARK_CASES_FILE = EVAL_FIXTURE_DIR / "benchmark_cases.json"
DEFAULT_REPORT_FILE = PROJECT_ROOT / "data" / "reports" / "eval_report_mode_benchmark.json"
SUPPORTED_BENCHMARK_MODES = ("vector", "keyword", "hybrid", "graph_hybrid", "full", "deep_lookup")
SUPPORTED_FUSION_METHODS = ("linear", "rrf")


def load_benchmark_cases(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    case_path = path or BENCHMARK_CASES_FILE
    if not case_path.exists():
        logger.error("Benchmark case file not found at %s", case_path)
        return []

    with open(case_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    return data if isinstance(data, list) else []


def _resolve_runtime_bindings(value: Any, bindings: Dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _resolve_runtime_bindings(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_runtime_bindings(item, bindings) for item in value]
    if isinstance(value, str) and value in bindings:
        return bindings[value]
    return value


@contextmanager
def _temporary_value(target: Any, attr_name: str, value: Any) -> Iterator[None]:
    original = getattr(target, attr_name)
    setattr(target, attr_name, value)
    try:
        yield
    finally:
        setattr(target, attr_name, original)


@contextmanager
def _temporary_settings(overrides: Optional[Dict[str, Any]]) -> Iterator[None]:
    overrides = overrides or {}
    originals = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in originals.items():
            setattr(settings, key, value)


def _build_filters(filters_payload: Optional[Dict[str, Any]]) -> Optional[SearchFilters]:
    if not filters_payload:
        return None
    return SearchFilters(**filters_payload)


@contextmanager
def _temporary_retrieval_profile(overrides: Optional[Dict[str, Any]]) -> Iterator[None]:
    if not overrides:
        yield
        return

    import app.core_rag.retrieval as retrieval_module

    base_config = get_effective_retrieval().model_dump()
    base_config.update(overrides)
    patched_config = RetrievalProfileConfig(**base_config)
    current_module = sys.modules[__name__]
    with _temporary_value(retrieval_module, "get_effective_retrieval", lambda: patched_config):
        with _temporary_value(current_module, "get_effective_retrieval", lambda: patched_config):
            yield


@contextmanager
def _temporary_reranker_profile(overrides: Optional[Dict[str, Any]]) -> Iterator[None]:
    if not overrides:
        yield
        return

    import app.core_rag.retrieval as retrieval_module
    import app.profiles.resolver as resolver_module

    base_config = get_effective_reranker().model_dump()
    base_config.update(overrides)
    patched_config = RerankerProfileConfig(**base_config)
    current_module = sys.modules[__name__]
    with _temporary_value(resolver_module, "get_effective_reranker", lambda: patched_config):
        with _temporary_value(retrieval_module, "get_effective_reranker", lambda: patched_config):
            with _temporary_value(current_module, "get_effective_reranker", lambda: patched_config):
                yield


def _mock_llm_content(case: Dict[str, Any], mode: str) -> Optional[str]:
    per_mode = case.get("mock_llm_content_by_mode") or {}
    if mode in per_mode:
        return per_mode[mode]
    return case.get("mock_llm_content")


def _evaluate_retrieval_summary(*, results: List[Dict[str, Any]], expected: Dict[str, Any]) -> Dict[str, Any]:
    expected = expected or {}
    headings_any = [item.lower() for item in expected.get("headings_any", [])]
    snippet_keywords_any = [item.lower() for item in expected.get("snippet_keywords_any", [])]
    snippet_keywords_all = [item.lower() for item in expected.get("snippet_keywords_all", [])]
    source_types_any = [item.lower() for item in expected.get("source_types_any", [])]

    matched = False
    best_match_rank = None
    matched_heading = None
    matched_keywords: list[str] = []
    matched_source_type = None

    for index, result in enumerate(results):
        heading = str(result.get("heading", "")).lower()
        snippet = str(result.get("snippet", "")).lower()
        source_type = str(result.get("source_type", "")).lower()
        combined_text = f"{heading} {snippet}"

        heading_ok = not headings_any or any(token in heading for token in headings_any)
        keyword_any_ok = not snippet_keywords_any or any(token in combined_text for token in snippet_keywords_any)
        keyword_all_ok = not snippet_keywords_all or all(token in combined_text for token in snippet_keywords_all)
        source_type_ok = not source_types_any or source_type in source_types_any

        if heading_ok and keyword_any_ok and keyword_all_ok and source_type_ok:
            matched = True
            best_match_rank = index + 1
            matched_heading = result.get("heading")
            matched_source_type = result.get("source_type")
            matched_keywords = sorted(
                {token for token in snippet_keywords_any + snippet_keywords_all if token in combined_text}
            )
            break

    note = "retrieval_expectations_met" if matched else "retrieval_expectations_not_met"
    if not results:
        note = "no_search_results"

    return {
        "passed": matched,
        "note": note,
        "best_match_rank": best_match_rank,
        "matched_heading": matched_heading,
        "matched_source_type": matched_source_type,
        "matched_keywords": matched_keywords,
        "result_count": len(results),
        "top_headings": [item.get("heading") for item in results[:3]],
        "top_source_types": [item.get("source_type") for item in results[:3]],
    }


def _evaluate_citation_quality(*, payload: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    expected = expected or {}
    citations = payload.get("citations", []) or []
    citation_count = len(citations)
    observed_source_ids = sorted({item["source_id"] for item in citations})
    min_citations = expected.get("min_citations", 0)
    expected_source_ids = sorted(expected.get("source_ids", []))

    passed = citation_count >= min_citations
    if expected_source_ids and observed_source_ids != expected_source_ids:
        passed = False

    note = "citation_expectations_met" if passed else "citation_expectations_not_met"
    if citation_count == 0:
        note = "no_citations_returned"

    return {
        "passed": passed,
        "note": note,
        "citation_count": citation_count,
        "citation_source_ids": observed_source_ids,
    }


def _evaluate_answer_clarity(*, payload: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    expected = expected or {}
    answer_text = payload.get("answer") or ""
    answer_lower = answer_text.lower()
    contains_any = expected.get("contains_any", [])
    not_found_allowed = bool(expected.get("not_found_allowed", True))
    not_found_observed = "not found in provided sources" in answer_lower
    matched_tokens = [token for token in contains_any if token in answer_text]

    passed = True
    if contains_any and not matched_tokens:
        passed = False
    if not_found_observed and not not_found_allowed:
        passed = False

    if not_found_observed:
        note = "not_found_answer_observed"
    elif passed:
        note = "answer_clarity_expectations_met"
    else:
        note = "answer_clarity_expectations_not_met"

    return {
        "passed": passed,
        "note": note,
        "matched_tokens": matched_tokens,
        "not_found_observed": not_found_observed,
    }


def _mode_failure_note(*, search_error: Optional[str], ask_error: Optional[str], answer_payload: Optional[Dict[str, Any]]) -> str:
    if search_error:
        return f"search_error:{search_error}"
    if ask_error:
        return f"ask_error:{ask_error}"
    if not answer_payload:
        return "no_answer_payload"
    if (answer_payload.get("answer") or "").lower().startswith("not found in provided sources"):
        return "not_found_answer"
    if not answer_payload.get("citations"):
        return "no_citations"
    return "none"


def _run_mode(
    case: Dict[str, Any],
    *,
    mode: str,
    retrieval_profile_overrides: Optional[Dict[str, Any]] = None,
    reranker_profile_overrides: Optional[Dict[str, Any]] = None,
    rerank_variant: str = "profile_default",
) -> Dict[str, Any]:
    import app.api.ask as ask_api_module
    import app.core_rag.answering as answering_module

    request_payload = dict(case.get("request", {}))
    filters = _build_filters(request_payload.get("filters"))
    question = request_payload["question"]
    k = int(request_payload.get("k", 5))
    k_chunks = int(request_payload.get("k_chunks", 6))

    search_error = None
    ask_error = None
    raw_results: list[dict[str, Any]] = []
    search_latency_ms = None
    search_mode = mode
    search_trace: dict[str, Any] = {}
    ask_trace: dict[str, Any] = {}

    try:
        with _temporary_retrieval_profile(retrieval_profile_overrides):
            with _temporary_reranker_profile(reranker_profile_overrides):
                if mode == "deep_lookup":
                    source_ids = list(
                        request_payload.get("source_ids")
                        or ([] if not filters or filters.source_id is None else [filters.source_id])
                    )
                    search_response = perform_deep_lookup(DeepLookupRequest(question=question, k=k, source_ids=source_ids))
                else:
                    search_response = perform_search(SearchRequest(question=question, k=k, filters=filters, mode=mode))
                raw_results = [item.model_dump() for item in search_response.results]
                search_latency_ms = search_response.latency_ms
                search_mode = search_response.mode
                search_trace = getattr(search_response, "debug_info", None) or {}
    except Exception as exc:
        search_error = str(exc)

    answer_payload = None
    ask_latency_ms = None
    ask_debug_info: dict[str, Any] = {}
    llm_content = _mock_llm_content(case, mode)
    ask_request = None
    if mode != "deep_lookup":
        ask_request = AskRequest(question=question, k_chunks=k_chunks, filters=filters, mode=mode, dry_run=False)
    if search_error is None and mode != "deep_lookup":
        try:
            with _temporary_retrieval_profile(retrieval_profile_overrides):
                with _temporary_reranker_profile(reranker_profile_overrides):
                    with _temporary_value(ask_api_module, "verify_llm_ready", lambda: True):
                        if llm_content is None:
                            ask_response = ask_endpoint(ask_request)
                        else:
                            with _temporary_value(
                                answering_module,
                                "generate_answer",
                                lambda system_prompt, user_prompt: {"success": True, "content": llm_content},
                            ):
                                ask_response = ask_endpoint(ask_request)
            answer_payload = ask_response.model_dump()
            ask_latency_ms = ask_response.latency_ms
            ask_debug_info = ask_response.debug_info or {}
            ask_trace = (ask_response.debug_info or {}).get("retrieval_trace", {})
        except Exception as exc:
            ask_error = str(exc)

    expected = dict(case.get("expected", {}))
    retrieval_summary = _evaluate_retrieval_summary(results=raw_results, expected=expected.get("retrieval", {}))
    if mode == "deep_lookup":
        citation_quality = {
            "passed": retrieval_summary["passed"],
            "note": "not_applicable_retrieval_only",
            "citation_count": 0,
            "citation_source_ids": [],
        }
        answer_clarity = {
            "passed": retrieval_summary["passed"],
            "note": "not_applicable_retrieval_only",
            "matched_tokens": [],
            "not_found_observed": False,
        }
        failure_mode = "retrieval_only_mode"
        passed = not search_error and retrieval_summary["passed"]
    else:
        citation_quality = _evaluate_citation_quality(payload=answer_payload or {}, expected=expected.get("citations", {}))
        answer_clarity = _evaluate_answer_clarity(payload=answer_payload or {}, expected=expected.get("answer", {}))
        failure_mode = _mode_failure_note(search_error=search_error, ask_error=ask_error, answer_payload=answer_payload)
        passed = not search_error and not ask_error and retrieval_summary["passed"] and citation_quality["passed"] and answer_clarity["passed"]

    return {
        "mode": mode,
        "rerank_variant": rerank_variant,
        "rerank_enabled": bool(((ask_trace or search_trace).get("rerank_policy") or {}).get("enabled")),
        "fusion_method": ((ask_trace or search_trace).get("fusion") or {}).get("method") or (retrieval_profile_overrides or {}).get("fusion_method") or "linear",
        "status": "PASS" if passed else "FAIL",
        "resolved_search_mode": search_mode,
        "latency_ms": {
            "search": search_latency_ms,
            "ask": ask_latency_ms,
            "total": (search_latency_ms or 0) + (ask_latency_ms or 0),
        },
        "retrieval_relevance": retrieval_summary,
        "citation_quality": citation_quality,
        "answer_clarity": answer_clarity,
        "failure_mode": failure_mode,
        "observed": {
            "result_count": len(raw_results),
            "answer": (answer_payload or {}).get("answer"),
            "citation_count": len((answer_payload or {}).get("citations", [])),
            "used_chunks_count": (answer_payload or {}).get("used_chunks_count", 0),
            "top_headings": retrieval_summary["top_headings"],
            "top_source_types": retrieval_summary["top_source_types"],
        },
        "errors": {
            "search": search_error,
            "ask": ask_error,
        },
        "trace": {
            "search_request_id": search_trace.get("request_id"),
            "ask_request_id": ask_trace.get("request_id"),
            "retrieval_path_used": (ask_trace or search_trace).get("retrieval_path_used"),
            "candidate_counts": (ask_trace or search_trace).get("candidate_counts", {}),
            "latency_ms": (ask_trace or search_trace).get("latency_ms", {}),
            "fallback_reason": (ask_trace or search_trace).get("fallback_reason"),
            "fusion": (ask_trace or search_trace).get("fusion"),
            "rerank_policy": (ask_trace or search_trace).get("rerank_policy"),
            "corpus_policy": (ask_trace or search_trace).get("corpus_policy"),
            "structured_filters": (ask_trace or search_trace).get("structured_filters", {}),
            "answer_generation_path": ask_debug_info.get("answer_generation_path"),
            "score_diagnostics": (ask_trace or search_trace).get("score_diagnostics", []),
        },
    }


def _build_rerank_latency_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for case in results:
        for mode_result in case.get("modes", []):
            variant = mode_result.get("rerank_variant", "profile_default")
            entry = grouped.setdefault(
                variant,
                {
                    "rerank_variant": variant,
                    "runs": 0,
                    "passed": 0,
                    "rerank_enabled": False,
                    "rerank_applied_runs": 0,
                    "search_total_ms": 0,
                    "ask_total_ms": 0,
                    "total_ms": 0,
                    "rerank_total_ms": 0,
                },
            )
            entry["runs"] += 1
            entry["passed"] += 1 if mode_result.get("status") == "PASS" else 0
            entry["rerank_enabled"] = entry["rerank_enabled"] or bool(mode_result.get("rerank_enabled"))
            rerank_policy = (mode_result.get("trace") or {}).get("rerank_policy") or {}
            entry["rerank_applied_runs"] += 1 if rerank_policy.get("applied") else 0
            latency_ms = mode_result.get("latency_ms") or {}
            trace_latency_ms = (mode_result.get("trace") or {}).get("latency_ms") or {}
            entry["search_total_ms"] += int(latency_ms.get("search") or 0)
            entry["ask_total_ms"] += int(latency_ms.get("ask") or 0)
            entry["total_ms"] += int(latency_ms.get("total") or 0)
            entry["rerank_total_ms"] += int(trace_latency_ms.get("rerank") or 0)

    variants = []
    for entry in sorted(grouped.values(), key=lambda item: item["rerank_variant"]):
        runs = entry["runs"] or 1
        variants.append(
            {
                "rerank_variant": entry["rerank_variant"],
                "rerank_enabled": entry["rerank_enabled"],
                "runs": entry["runs"],
                "pass_rate_percent": round((entry["passed"] / runs) * 100.0, 2),
                "avg_search_latency_ms": round(entry["search_total_ms"] / runs, 2),
                "avg_ask_latency_ms": round(entry["ask_total_ms"] / runs, 2),
                "avg_total_latency_ms": round(entry["total_ms"] / runs, 2),
                "avg_rerank_latency_ms": round(entry["rerank_total_ms"] / runs, 2),
                "rerank_applied_runs": entry["rerank_applied_runs"],
            }
        )

    baseline = next((item for item in variants if not item["rerank_enabled"]), None)
    deltas = []
    if baseline is not None:
        for item in variants:
            if item["rerank_variant"] == baseline["rerank_variant"]:
                continue
            deltas.append(
                {
                    "baseline_variant": baseline["rerank_variant"],
                    "target_variant": item["rerank_variant"],
                    "delta_avg_total_latency_ms": round(item["avg_total_latency_ms"] - baseline["avg_total_latency_ms"], 2),
                    "delta_avg_rerank_latency_ms": round(item["avg_rerank_latency_ms"] - baseline["avg_rerank_latency_ms"], 2),
                    "delta_pass_rate_percent": round(item["pass_rate_percent"] - baseline["pass_rate_percent"], 2),
                }
            )

    return {"variants": variants, "deltas": deltas}


def evaluate_benchmark_case(case: Dict[str, Any], *, bindings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    bindings = bindings or {}
    resolved_case = _resolve_runtime_bindings(case, bindings)
    request_payload = dict(resolved_case.get("request", {}))
    if "question" not in request_payload and "question" in resolved_case:
        request_payload["question"] = resolved_case["question"]
    if "question" not in request_payload:
        return {"id": resolved_case.get("id", "unknown"), "status": "FAIL", "error": "missing_question"}

    resolved_case["request"] = request_payload
    modes = [mode for mode in resolved_case.get("modes", list(SUPPORTED_BENCHMARK_MODES)) if mode in SUPPORTED_BENCHMARK_MODES]
    fusion_methods = [
        fusion_method
        for fusion_method in resolved_case.get("fusion_methods", ["linear"])
        if fusion_method in SUPPORTED_FUSION_METHODS
    ] or ["linear"]
    rerank_variants = resolved_case.get("rerank_variants") or [{"label": "profile_default", "overrides": {}}]

    with _temporary_settings(resolved_case.get("settings_overrides")):
        mode_results = []
        for fusion_method in fusion_methods:
            for rerank_variant in rerank_variants:
                retrieval_profile_overrides = dict(resolved_case.get("retrieval_profile_overrides") or {})
                retrieval_profile_overrides["fusion_method"] = fusion_method
                reranker_profile_overrides = dict((rerank_variant or {}).get("overrides") or {})
                rerank_label = (rerank_variant or {}).get("label") or "profile_default"
                for mode in modes:
                    mode_results.append(
                        _run_mode(
                            resolved_case,
                            mode=mode,
                            retrieval_profile_overrides=retrieval_profile_overrides,
                            reranker_profile_overrides=reranker_profile_overrides,
                            rerank_variant=rerank_label,
                        )
                    )

    failures = [item["mode"] for item in mode_results if item["status"] == "FAIL"]
    return {
        "id": resolved_case.get("id", "unknown"),
        "category": resolved_case.get("category"),
        "question": request_payload["question"],
        "notes": resolved_case.get("notes"),
        "status": "PASS" if not failures else "FAIL",
        "modes": mode_results,
        "failed_modes": failures,
    }


def run_mode_benchmark(
    *,
    cases: List[Dict[str, Any]],
    bindings: Optional[Dict[str, Any]] = None,
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    results = [evaluate_benchmark_case(case, bindings=bindings) for case in cases]
    failures = [item for item in results if item["status"] == "FAIL"]
    total = len(results)
    passed = total - len(failures)
    evaluated_modes = sorted({mode_result["mode"] for case in results for mode_result in case.get("modes", [])})
    evaluated_fusion_methods = sorted({mode_result.get("fusion_method", "linear") for case in results for mode_result in case.get("modes", [])})
    evaluated_rerank_variants = sorted({mode_result.get("rerank_variant", "profile_default") for case in results for mode_result in case.get("modes", [])})
    report = {
        "summary": {
            "kind": "mode_benchmark",
            "total": total,
            "passed": passed,
            "failed": len(failures),
            "pass_rate_percent": round((passed / total) * 100.0, 2) if total else 0.0,
            "evaluated_modes": evaluated_modes,
            "evaluated_fusion_methods": evaluated_fusion_methods,
            "evaluated_rerank_variants": evaluated_rerank_variants,
            "rerank_latency_report": _build_rerank_latency_report(results),
        },
        "report_metadata": {
            "active_profiles": get_active_profile_snapshot(),
            "retrieval_settings": get_effective_retrieval().model_dump(),
            "reranker_settings": get_effective_reranker().model_dump(),
        },
        "results": results,
        "failures": failures,
    }
    report_file = write_eval_report(report, report_path or DEFAULT_REPORT_FILE)
    report["report_path"] = str(report_file)
    return report


def _parse_bindings(raw_bindings: Optional[List[str]]) -> Dict[str, Any]:
    bindings: Dict[str, Any] = {}
    for item in raw_bindings or []:
        if "=" not in item:
            continue
        key, raw_value = item.split("=", 1)
        try:
            bindings[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            bindings[key] = raw_value
    return bindings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M20 mode comparison benchmarks.")
    parser.add_argument("--cases", type=Path, default=BENCHMARK_CASES_FILE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_FILE)
    parser.add_argument(
        "--bind",
        action="append",
        default=[],
        help="Runtime binding in key=json_or_string form, for example benchmark_source_id=123",
    )
    args = parser.parse_args()

    cases = load_benchmark_cases(args.cases)
    report = run_mode_benchmark(cases=cases, bindings=_parse_bindings(args.bind), report_path=args.report)
    print(json.dumps(report["summary"], indent=2))
    print(f"report_path={report['report_path']}")


if __name__ == "__main__":
    main()
