import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin_user
from app.corpus_policies import get_corpus_policy
from app.core.config import REPO_ROOT
from app.core.logging import logger
from app.core_rag.retrieval import SearchFilters, SearchRequest, perform_search
from app.db.repo_acl import assign_document_acl, list_access_summary, list_source_acl_map
from app.db.repo_admin_audit import insert_admin_audit_event, list_admin_audit_events
from app.db.repo_corpora import get_corpus, list_corpora, upsert_corpus
from app.db.repo_jobs import (
    get_enrichment_job,
    get_ingestion_job,
    list_enrichment_jobs,
    list_ingestion_jobs,
)
from app.db.repo_profiles import get_active_profile_name, get_profile, list_profiles, set_active_profile
from app.db.repo_sources import get_source_by_id, list_sources, update_source_admin_fields
from app.db.repo_traces import get_trace, get_trace_by_id, list_traces
from app.eval.compare_eval import DEFAULT_REPORT_FILE as BENCHMARK_REPORT_FILE
from app.eval.compare_eval import load_benchmark_cases, run_mode_benchmark
from app.eval.retrieval_eval import DEFAULT_REPORT_FILE as RETRIEVAL_REPORT_FILE
from app.eval.retrieval_eval import load_eval_cases, run_retrieval_eval
from app.ingestion.enrichment import admin_rerun_enrichment
from app.ingestion.jobs import admin_reindex_source
from app.profiles.models import PROFILE_TYPE_MODELS
from app.profiles.resolver import get_active_profile_snapshot, get_effective_reranker, get_effective_retrieval, invalidate_cache


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])

_EVAL_REPORT_FILES = {
    "retrieval": RETRIEVAL_REPORT_FILE,
    "benchmark": BENCHMARK_REPORT_FILE,
}


class ActiveProfileRequest(BaseModel):
    profile_type: str
    profile_name: str


class TraceListResponse(BaseModel):
    traces: list[dict]
    active_profiles: dict
    retrieval_settings: dict


class CorpusCreateRequest(BaseModel):
    name: str
    description: str = ""
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CorpusSourceAssignmentRequest(BaseModel):
    source_ids: list[int]
    sensitivity_label: Optional[str] = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    corpus_name: Optional[str] = None
    sensitivity_label: Optional[str] = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)
    acl_group_names: Optional[list[str]] = None


class ReindexRequest(BaseModel):
    force: bool = False


class EvalRunRequest(BaseModel):
    report_kind: str = Field(default="retrieval")
    debug: bool = False


class QueryTraceRequest(BaseModel):
    question: str
    k: int = 10
    filters: Optional[SearchFilters] = None
    mode: Optional[str] = None
    deep_research: bool = False
    custom_query: Optional[str] = None
    anchor_terms: list[str] = Field(default_factory=list)
    exact_phrase_bias: Optional[str] = None
    expand_neighbors: bool = False
    force_rare_keyword_scan: bool = False


def _report_summary(kind: str, path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "kind": kind,
        "path": str(path.relative_to(REPO_ROOT)),
        "exists": path.exists(),
        "summary": payload.get("summary"),
        "report_metadata": payload.get("report_metadata"),
    }


def _source_to_payload(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "file_name": row.file_name,
        "storage_path": row.storage_path,
        "source_type": row.source_type,
        "mime_type": row.mime_type,
        "hash_sha256": row.hash_sha256,
        "sensitivity_label": row.sensitivity_label,
        "file_size_bytes": row.file_size_bytes,
        "ingestion_status": row.ingestion_status,
        "enrichment_status": row.enrichment_status,
        "source_metadata_json": row.source_metadata_json,
    }


def _coerce_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _job_payload(row, *, kind: str, source_lookup: dict[int, dict[str, Any]]) -> dict[str, Any]:
    payload = dict(row.__dict__)
    started_at = _coerce_datetime(payload.get("started_at"))
    completed_at = _coerce_datetime(payload.get("completed_at"))
    duration_seconds = None
    if started_at and completed_at:
        duration_seconds = round((completed_at - started_at).total_seconds(), 3)
    source = source_lookup.get(int(payload["source_id"])) if payload.get("source_id") is not None else None
    payload["job_kind"] = kind
    payload["duration_seconds"] = duration_seconds
    payload["source_file_name"] = source["file_name"] if source else None
    payload["corpus_name"] = source["corpus_name"] if source else None
    return payload


def _trace_payload(trace: dict[str, Any]) -> dict[str, Any]:
    payload = dict(trace)
    latency = payload.get("latency_ms") or {}
    payload["total_latency_ms"] = latency.get("total") or latency.get("search_total") or latency.get("search")
    payload["search_latency_ms"] = latency.get("search")
    payload["has_fallback"] = bool(payload.get("fallback_reason"))
    return payload


def _source_payload_with_acl(row, acl_map: dict[int, list[str]]) -> dict[str, Any]:
    payload = _source_to_payload(row)
    payload["corpus_name"] = (row.source_metadata_json or {}).get("corpus")
    payload["acl_groups"] = acl_map.get(int(row.id), [])
    return payload


@router.get("/profiles")
def get_profiles(profile_type: Optional[str] = None):
    rows = list_profiles(profile_type)
    active_map: dict[str, Optional[str]] = {}
    for row in rows:
        pt = row["profile_type"]
        if pt not in active_map:
            active_map[pt] = get_active_profile_name(pt)
    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "profile_type": row["profile_type"],
                "name": row["name"],
                "config": row["config_json"],
                "is_default": row["is_default"],
                "is_active": row["name"] == active_map.get(row["profile_type"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
        )
    return {"profiles": result}


@router.post("/profiles/active")
def set_active(body: ActiveProfileRequest):
    if body.profile_type not in PROFILE_TYPE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown profile type: {body.profile_type}")

    profile = get_profile(body.profile_type, body.profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile_name}' of type '{body.profile_type}' not found")

    model_cls = PROFILE_TYPE_MODELS[body.profile_type]
    try:
        model_cls(**profile["config_json"])
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Profile config validation failed: {exc}") from exc

    previous_profile_name = get_active_profile_name(body.profile_type)
    set_active_profile(body.profile_type, body.profile_name)
    invalidate_cache(body.profile_type)
    logger.info("Activated profile %s/%s", body.profile_type, body.profile_name)
    insert_admin_audit_event(
        event_type="profile",
        action="profile.activate",
        resource_type="profile",
        resource_id=f"{body.profile_type}:{body.profile_name}",
        resource_name=body.profile_name,
        profile_type=body.profile_type,
        profile_name=body.profile_name,
        before_json={"profile_name": previous_profile_name},
        after_json={"profile_name": body.profile_name},
    )
    return {"status": "ok", "profile_type": body.profile_type, "profile_name": body.profile_name}


@router.get("/profiles/metadata")
def get_profile_metadata():
    retrieval_settings = get_effective_retrieval().model_dump()
    reranker_settings = get_effective_reranker().model_dump()
    return {
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": retrieval_settings,
        "reranker_settings": reranker_settings,
        "strategy_defaults": {
            "default_mode": retrieval_settings.get("default_mode"),
            "fusion_method": retrieval_settings.get("fusion_method"),
            "rrf_k": retrieval_settings.get("rrf_k"),
            "vector_candidates": retrieval_settings.get("vector_candidates"),
            "keyword_candidates": retrieval_settings.get("keyword_candidates"),
            "hybrid_alpha": retrieval_settings.get("hybrid_alpha"),
            "deep_research_vector_candidates": retrieval_settings.get("deep_research_vector_candidates"),
            "deep_research_keyword_candidates": retrieval_settings.get("deep_research_keyword_candidates"),
            "rerank_enabled": reranker_settings.get("enabled"),
            "rerank_enabled_modes": reranker_settings.get("enabled_modes"),
            "rerank_enabled_corpora": reranker_settings.get("enabled_corpora"),
            "rerank_min_candidate_count": reranker_settings.get("min_candidate_count"),
            "rerank_max_candidate_count": reranker_settings.get("max_candidate_count"),
            "rerank_latency_budget_ms": reranker_settings.get("latency_budget_ms"),
            "rerank_mmr_enabled": reranker_settings.get("mmr_enabled"),
        },
        "profile_types": sorted(PROFILE_TYPE_MODELS.keys()),
        "supported_search_modes": ["vector", "keyword", "hybrid", "graph_hybrid", "full"],
        "supported_corpus_policies": [
            get_corpus_policy("default").to_dict(),
            get_corpus_policy("legal").to_dict(),
            get_corpus_policy("transcripts").to_dict(),
            get_corpus_policy("db_rows").to_dict(),
            get_corpus_policy("email_casework").to_dict(),
        ],
    }


@router.get("/overview")
def get_admin_overview():
    corpora = list_corpora()
    sources = list_sources()
    source_lookup = {
        int(row.id): {
            "file_name": row.file_name,
            "corpus_name": (row.source_metadata_json or {}).get("corpus"),
        }
        for row in sources
    }
    ingestion_jobs = [_job_payload(row, kind="ingestion", source_lookup=source_lookup) for row in list_ingestion_jobs()]
    enrichment_jobs = [_job_payload(row, kind="enrichment", source_lookup=source_lookup) for row in list_enrichment_jobs()]
    traces = [_trace_payload(row) for row in list_traces(limit=6, offset=0)]
    reports = [_report_summary(kind, path) for kind, path in _EVAL_REPORT_FILES.items()]
    audit_events = list_admin_audit_events(limit=5)
    latest_report = next((report for report in reports if report["exists"]), None)

    alerts: list[dict[str, Any]] = []
    failed_jobs = [job for job in [*ingestion_jobs, *enrichment_jobs] if str(job.get("status", "")).lower() in {"failed", "error"}]
    if failed_jobs:
        alerts.append(
            {
                "tone": "danger",
                "title": "Failed jobs need review",
                "body": f"{len(failed_jobs)} ingestion or enrichment jobs ended in a failed state.",
                "href": "/console/admin/jobs",
            }
        )
    unassigned_sources = [row for row in sources if not (row.source_metadata_json or {}).get("corpus")]
    if unassigned_sources:
        alerts.append(
            {
                "tone": "warning",
                "title": "Sources still need corpus assignment",
                "body": f"{len(unassigned_sources)} sources are not attached to a corpus yet.",
                "href": "/console/admin/corpora",
            }
        )
    if latest_report is None:
        alerts.append(
            {
                "tone": "info",
                "title": "No eval report available yet",
                "body": "Run retrieval or benchmark evals before relying on quality summaries.",
                "href": "/console/admin/evals",
            }
        )
    fallback_traces = [trace for trace in traces if trace.get("has_fallback")]
    if fallback_traces:
        alerts.append(
            {
                "tone": "warning",
                "title": "Recent retrieval fallbacks detected",
                "body": f"{len(fallback_traces)} of the latest traces recorded a fallback reason.",
                "href": "/console/admin/traces",
            }
        )

    active_jobs = [
        job
        for job in [*ingestion_jobs, *enrichment_jobs]
        if str(job.get("status", "")).lower() in {"queued", "processing", "running", "pending"}
    ]
    return {
        "summary": {
            "corpora_count": len(corpora),
            "source_count": len(sources),
            "active_job_count": len(active_jobs),
            "latest_eval_pass_rate": (latest_report or {}).get("summary", {}).get("pass_rate_percent"),
            "latest_eval_kind": latest_report["kind"] if latest_report else None,
        },
        "alerts": alerts,
        "recent_traces": traces[:4],
        "recent_audit_events": audit_events,
        "reports": reports,
    }


@router.get("/corpora")
def get_corpora():
    rows = list_corpora()
    sources = list_sources()
    acl_map = list_source_acl_map()
    source_payload = [_source_payload_with_acl(row, acl_map) for row in sources]
    unassigned_count = sum(1 for row in sources if not (row.source_metadata_json or {}).get("corpus"))
    return {
        "corpora": [
            {
                "name": row["name"],
                "description": row["description"],
                "metadata_json": row["metadata_json"],
                "source_count": int(row["source_count"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
            for row in rows
        ],
        "sources": source_payload,
        "unassigned_source_count": unassigned_count,
    }


@router.get("/sources")
def get_sources():
    acl_map = list_source_acl_map()
    return {"sources": [_source_payload_with_acl(row, acl_map) for row in list_sources()]}


@router.post("/corpora")
def create_corpus(body: CorpusCreateRequest):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Corpus name is required")
    row = upsert_corpus(name=body.name.strip(), description=body.description.strip(), metadata_json=body.metadata_json)
    insert_admin_audit_event(
        event_type="corpus",
        action="corpus.create",
        resource_type="corpus",
        resource_id=str(row["name"]),
        resource_name=str(row["name"]),
        corpus_name=str(row["name"]),
        after_json=row,
    )
    return {"status": "ok", "corpus": row}


@router.patch("/corpora/{corpus_name}")
def update_corpus(corpus_name: str, body: CorpusCreateRequest):
    existing = get_corpus(corpus_name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_name}' not found")
    target_name = body.name.strip() or corpus_name
    row = upsert_corpus(name=target_name, description=body.description.strip(), metadata_json=body.metadata_json)
    insert_admin_audit_event(
        event_type="corpus",
        action="corpus.update",
        resource_type="corpus",
        resource_id=target_name,
        resource_name=target_name,
        corpus_name=target_name,
        before_json=existing,
        after_json=row,
    )
    return {"status": "ok", "corpus": row}


@router.patch("/corpora/{corpus_name}/sources")
def assign_sources_to_corpus(corpus_name: str, body: CorpusSourceAssignmentRequest):
    corpus = get_corpus(corpus_name)
    if corpus is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_name}' not found")
    if not body.source_ids:
        raise HTTPException(status_code=400, detail="At least one source_id is required")

    updated_source_ids: list[int] = []
    for source_id in body.source_ids:
        row = get_source_by_id(source_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
        metadata = dict(row.source_metadata_json or {})
        metadata["corpus"] = corpus_name
        if body.metadata_patch:
            metadata.update(body.metadata_patch)
        update_source_admin_fields(
            source_id,
            sensitivity_label=body.sensitivity_label,
            source_metadata_json=metadata,
        )
        updated_source_ids.append(source_id)
    insert_admin_audit_event(
        event_type="corpus",
        action="corpus.assign_sources",
        resource_type="corpus",
        resource_id=corpus_name,
        resource_name=corpus_name,
        corpus_name=corpus_name,
        after_json={
            "updated_source_ids": updated_source_ids,
            "sensitivity_label": body.sensitivity_label,
            "metadata_patch": body.metadata_patch,
        },
    )
    return {"status": "ok", "corpus": corpus_name, "updated_source_ids": updated_source_ids}


@router.patch("/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdateRequest):
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    before_acl_map = list_source_acl_map()
    current_metadata = dict(row.source_metadata_json or {})
    next_metadata = dict(current_metadata)
    if body.corpus_name is not None:
        if body.corpus_name.strip():
            next_metadata["corpus"] = body.corpus_name.strip()
        else:
            next_metadata.pop("corpus", None)
    if body.metadata_patch:
        next_metadata.update(body.metadata_patch)
    update_source_admin_fields(
        source_id,
        sensitivity_label=body.sensitivity_label,
        source_metadata_json=next_metadata,
    )
    if body.acl_group_names is not None:
        assign_document_acl(source_id=source_id, group_names=body.acl_group_names)
    updated = get_source_by_id(source_id)
    acl_map = list_source_acl_map()
    insert_admin_audit_event(
        event_type="source",
        action="source.update",
        resource_type="source",
        resource_id=str(source_id),
        resource_name=row.file_name,
        source_id=source_id,
        corpus_name=(updated.source_metadata_json or {}).get("corpus") if updated else None,
        before_json={
            "sensitivity_label": row.sensitivity_label,
            "corpus_name": current_metadata.get("corpus"),
            "acl_groups": before_acl_map.get(source_id, []),
        },
        after_json=_source_payload_with_acl(updated or row, acl_map),
    )
    return {"status": "ok", "source": _source_payload_with_acl(updated or row, acl_map)}


@router.post("/sources/{source_id}/reindex")
def trigger_reindex(source_id: int, body: ReindexRequest):
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    try:
        result = admin_reindex_source(source_id=source_id, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="job",
        action="source.reindex",
        resource_type="source",
        resource_id=str(source_id),
        resource_name=row.file_name,
        source_id=source_id,
        corpus_name=(row.source_metadata_json or {}).get("corpus"),
        job_kind="ingestion",
        job_id=result.get("job_id"),
        after_json=result,
    )
    return result


@router.post("/sources/{source_id}/enrich")
def trigger_enrichment(source_id: int, body: ReindexRequest):
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    try:
        result = admin_rerun_enrichment(source_id=source_id, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = result.model_dump()
    insert_admin_audit_event(
        event_type="job",
        action="source.enrich",
        resource_type="source",
        resource_id=str(source_id),
        resource_name=row.file_name,
        source_id=source_id,
        corpus_name=(row.source_metadata_json or {}).get("corpus"),
        job_kind="enrichment",
        job_id=payload.get("job_id"),
        after_json=payload,
    )
    return payload


@router.get("/jobs")
def get_jobs(source_id: Optional[int] = None):
    sources = list_sources()
    source_lookup = {
        int(row.id): {
            "file_name": row.file_name,
            "corpus_name": (row.source_metadata_json or {}).get("corpus"),
        }
        for row in sources
    }
    return {
        "ingestion_jobs": [_job_payload(row, kind="ingestion", source_lookup=source_lookup) for row in list_ingestion_jobs(source_id=source_id)],
        "enrichment_jobs": [_job_payload(row, kind="enrichment", source_lookup=source_lookup) for row in list_enrichment_jobs(source_id=source_id)],
    }


@router.get("/jobs/ingestion/{job_id}")
def get_ingestion_job_status(job_id: int):
    row = get_ingestion_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    source_lookup = {}
    if row.source_id is not None:
        source = get_source_by_id(row.source_id)
        if source is not None:
            source_lookup[int(source.id)] = {
                "file_name": source.file_name,
                "corpus_name": (source.source_metadata_json or {}).get("corpus"),
            }
    return _job_payload(row, kind="ingestion", source_lookup=source_lookup)


@router.get("/jobs/enrichment/{job_id}")
def get_enrichment_job_status(job_id: int):
    row = get_enrichment_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    source_lookup = {}
    if row.source_id is not None:
        source = get_source_by_id(row.source_id)
        if source is not None:
            source_lookup[int(source.id)] = {
                "file_name": source.file_name,
                "corpus_name": (source.source_metadata_json or {}).get("corpus"),
            }
    return _job_payload(row, kind="enrichment", source_lookup=source_lookup)


@router.post("/eval/run")
def run_eval(body: EvalRunRequest):
    report_kind = body.report_kind.strip().lower()
    if report_kind == "retrieval":
        report = run_retrieval_eval(cases=load_eval_cases(), report_path=RETRIEVAL_REPORT_FILE, debug=body.debug)
    elif report_kind == "benchmark":
        report = run_mode_benchmark(cases=load_benchmark_cases(), report_path=BENCHMARK_REPORT_FILE)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported report kind: {body.report_kind}")
    payload = {
        "status": "completed",
        "report_kind": report_kind,
        "summary": report.get("summary"),
        "report_metadata": report.get("report_metadata"),
        "path": str(_EVAL_REPORT_FILES[report_kind].relative_to(REPO_ROOT)),
    }
    insert_admin_audit_event(
        event_type="eval",
        action="eval.run",
        resource_type="eval_report",
        resource_id=report_kind,
        resource_name=report_kind,
        after_json=payload,
    )
    return payload


@router.get("/eval/reports")
def list_eval_reports():
    return {"reports": [_report_summary(kind, path) for kind, path in _EVAL_REPORT_FILES.items()]}


@router.post("/traces/query-debug")
def query_retrieval_trace(body: QueryTraceRequest):
    response = perform_search(
        SearchRequest(
            question=body.question,
            k=body.k,
            filters=body.filters,
            mode=body.mode,
            debug=True,
            deep_research=body.deep_research,
            custom_query=body.custom_query,
            anchor_terms=body.anchor_terms,
            exact_phrase_bias=body.exact_phrase_bias,
            expand_neighbors=body.expand_neighbors,
            force_rare_keyword_scan=body.force_rare_keyword_scan,
        )
    )
    return {
        "results": [item.model_dump() for item in response.results],
        "mode": response.mode,
        "latency_ms": response.latency_ms,
        "trace": response.debug_info or {},
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/traces", response_model=TraceListResponse)
def get_retrieval_traces(limit: int = 20, offset: int = 0):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return {
        "traces": [_trace_payload(row) for row in list_traces(limit=limit, offset=offset)],
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/traces/by-request/{request_id}")
def get_retrieval_trace_by_request(request_id: str):
    trace = get_trace(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace for request_id '{request_id}' not found")
    return {
        "trace": _trace_payload(trace),
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/traces/{trace_id}")
def get_retrieval_trace(trace_id: int):
    trace = get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return {
        "trace": _trace_payload(trace),
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/access")
def get_access():
    return list_access_summary()


@router.get("/audit-log")
def get_admin_audit_log(
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    outcome: Optional[str] = None,
    actor_external_user_id: Optional[str] = None,
):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return {
        "events": list_admin_audit_events(
            limit=limit,
            offset=offset,
            action=action,
            resource_type=resource_type,
            outcome=outcome,
            actor_external_user_id=actor_external_user_id,
        )
    }
