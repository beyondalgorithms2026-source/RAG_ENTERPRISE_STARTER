import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.api.ask import ask_endpoint
from app.api.compare import compare_endpoint
from app.core.config import settings
from app.core_rag.answering import AskRequest, CompareRequest
from app.eval.retrieval_eval import PROJECT_ROOT, write_eval_report


EVAL_FIXTURE_DIR = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "eval"
ANSWER_CASES_FILE = EVAL_FIXTURE_DIR / "answer_cases.json"
COMPARE_CASES_FILE = EVAL_FIXTURE_DIR / "compare_cases.json"
DEFAULT_REPORT_FILE = PROJECT_ROOT / "data" / "reports" / "eval_report_enriched.json"


def load_answer_cases(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    case_path = path or ANSWER_CASES_FILE
    with open(case_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def load_compare_cases(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    case_path = path or COMPARE_CASES_FILE
    with open(case_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


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


def _check_common_expectations(*, payload: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, Any]:
    observed = {
        "used_chunks_count": payload.get("used_chunks_count", 0),
        "citation_count": len(payload.get("citations", [])),
        "source_count": len(payload.get("sources", [])),
        "debug_info_keys": sorted((payload.get("debug_info") or {}).keys()),
    }

    passed = True
    failures: list[str] = []

    min_used_chunks = expected.get("min_used_chunks")
    if min_used_chunks is not None and observed["used_chunks_count"] < min_used_chunks:
        passed = False
        failures.append("used_chunks_below_min")

    citation_count = expected.get("citation_count")
    if citation_count is not None and observed["citation_count"] != citation_count:
        passed = False
        failures.append("citation_count_mismatch")

    source_count = expected.get("source_count")
    if source_count is not None and observed["source_count"] != source_count:
        passed = False
        failures.append("source_count_mismatch")

    required_debug_keys = expected.get("required_debug_keys", [])
    if any(key not in observed["debug_info_keys"] for key in required_debug_keys):
        passed = False
        failures.append("required_debug_keys_missing")

    expected_answer = expected.get("answer_equals")
    if expected_answer is not None and payload.get("answer") != expected_answer:
        passed = False
        failures.append("answer_mismatch")

    answer_contains = expected.get("answer_contains", [])
    answer_text = payload.get("answer") or ""
    if any(token not in answer_text for token in answer_contains):
        passed = False
        failures.append("answer_missing_expected_token")

    answer_excludes = expected.get("answer_excludes", [])
    if any(token in answer_text for token in answer_excludes):
        passed = False
        failures.append("answer_contains_excluded_token")

    citation_source_ids = expected.get("citation_source_ids")
    if citation_source_ids is not None:
        observed_ids = sorted({item["source_id"] for item in payload.get("citations", [])})
        if sorted(citation_source_ids) != observed_ids:
            passed = False
            failures.append("citation_source_ids_mismatch")
        observed["citation_source_ids"] = observed_ids

    grouped_source_ids = expected.get("grouped_source_ids")
    if grouped_source_ids is not None:
        observed_grouped = sorted(item["source_id"] for item in payload.get("sources", []))
        if sorted(grouped_source_ids) != observed_grouped:
            passed = False
            failures.append("grouped_source_ids_mismatch")
        observed["grouped_source_ids"] = observed_grouped

    resolved_modes = expected.get("resolved_modes")
    if resolved_modes is not None:
        observed_modes = (payload.get("debug_info") or {}).get("resolved_modes", [])
        if list(resolved_modes) != list(observed_modes):
            passed = False
            failures.append("resolved_modes_mismatch")
        observed["resolved_modes"] = observed_modes

    debug_mode = expected.get("debug_mode")
    if debug_mode is not None:
        observed_mode = (payload.get("debug_info") or {}).get("mode")
        if observed_mode != debug_mode:
            passed = False
            failures.append("debug_mode_mismatch")
        observed["debug_mode"] = observed_mode

    return {"passed": passed, "failures": failures, "observed": observed}


def evaluate_answer_case(case: Dict[str, Any]) -> Dict[str, Any]:
    import app.api.ask as ask_api_module
    import app.core_rag.answering as answering_module

    request = AskRequest(**case["request"])
    expected = dict(case.get("expected", {}))
    mock_llm_content = case.get("mock_llm_content")
    settings_overrides = case.get("settings_overrides")

    with _temporary_settings(settings_overrides):
        with _temporary_value(ask_api_module, "verify_llm_ready", lambda: True):
            if mock_llm_content is None:
                response = ask_endpoint(request)
            else:
                with _temporary_value(
                    answering_module,
                    "generate_answer",
                    lambda system_prompt, user_prompt: {"success": True, "content": mock_llm_content},
                ):
                    response = ask_endpoint(request)

    payload = response.model_dump()
    check = _check_common_expectations(payload=payload, expected=expected)
    return {
        "id": case.get("id", "unknown"),
        "kind": "answer",
        "status": "PASS" if check["passed"] else "FAIL",
        "expected": expected,
        "observed": check["observed"],
        "failures": check["failures"],
    }


def evaluate_compare_case(case: Dict[str, Any]) -> Dict[str, Any]:
    import app.api.compare as compare_api_module
    import app.core_rag.answering as answering_module

    request = CompareRequest(**case["request"])
    expected = dict(case.get("expected", {}))
    mock_llm_content = case.get("mock_llm_content")
    settings_overrides = case.get("settings_overrides")

    with _temporary_settings(settings_overrides):
        with _temporary_value(compare_api_module, "verify_llm_ready", lambda: True):
            if mock_llm_content is None:
                response = compare_endpoint(request)
            else:
                with _temporary_value(
                    answering_module,
                    "generate_answer",
                    lambda system_prompt, user_prompt: {"success": True, "content": mock_llm_content},
                ):
                    response = compare_endpoint(request)

    payload = response.model_dump()
    check = _check_common_expectations(payload=payload, expected=expected)
    return {
        "id": case.get("id", "unknown"),
        "kind": "compare",
        "status": "PASS" if check["passed"] else "FAIL",
        "expected": expected,
        "observed": check["observed"],
        "failures": check["failures"],
    }


def run_enriched_eval(
    *,
    answer_cases: List[Dict[str, Any]],
    compare_cases: List[Dict[str, Any]],
    report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    results = [evaluate_answer_case(case) for case in answer_cases]
    results.extend(evaluate_compare_case(case) for case in compare_cases)
    failures = [item for item in results if item["status"] == "FAIL"]
    passed = sum(1 for item in results if item["status"] == "PASS")
    total = len(results)
    report = {
        "summary": {
            "kind": "enriched",
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate_percent": round((passed / total) * 100.0, 2) if total else 0.0,
        },
        "results": results,
        "failures": failures,
    }
    report_file = write_eval_report(report, report_path or DEFAULT_REPORT_FILE)
    report["report_path"] = str(report_file)
    return report
