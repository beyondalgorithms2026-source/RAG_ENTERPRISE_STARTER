import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin_user
from app.core.config import REPO_ROOT
from app.core.logging import logger
from app.core_rag.retrieval import SearchFilters, SearchRequest, perform_search
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
from app.profiles.resolver import get_active_profile_snapshot, get_effective_retrieval, invalidate_cache


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

    set_active_profile(body.profile_type, body.profile_name)
    invalidate_cache(body.profile_type)
    logger.info("Activated profile %s/%s", body.profile_type, body.profile_name)
    return {"status": "ok", "profile_type": body.profile_type, "profile_name": body.profile_name}


@router.get("/profiles/metadata")
def get_profile_metadata():
    retrieval_settings = get_effective_retrieval().model_dump()
    return {
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": retrieval_settings,
        "strategy_defaults": {
            "default_mode": retrieval_settings.get("default_mode"),
            "fusion_method": retrieval_settings.get("fusion_method"),
            "vector_candidates": retrieval_settings.get("vector_candidates"),
            "keyword_candidates": retrieval_settings.get("keyword_candidates"),
            "hybrid_alpha": retrieval_settings.get("hybrid_alpha"),
            "deep_research_vector_candidates": retrieval_settings.get("deep_research_vector_candidates"),
            "deep_research_keyword_candidates": retrieval_settings.get("deep_research_keyword_candidates"),
        },
        "profile_types": sorted(PROFILE_TYPE_MODELS.keys()),
        "supported_search_modes": ["vector", "keyword", "hybrid", "graph_hybrid", "full"],
    }


@router.get("/corpora")
def get_corpora():
    rows = list_corpora()
    sources = list_sources()
    source_payload = [_source_to_payload(row) for row in sources]
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


@router.post("/corpora")
def create_corpus(body: CorpusCreateRequest):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Corpus name is required")
    row = upsert_corpus(name=body.name.strip(), description=body.description.strip(), metadata_json=body.metadata_json)
    return {"status": "ok", "corpus": row}


@router.patch("/corpora/{corpus_name}")
def update_corpus(corpus_name: str, body: CorpusCreateRequest):
    existing = get_corpus(corpus_name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Corpus '{corpus_name}' not found")
    target_name = body.name.strip() or corpus_name
    row = upsert_corpus(name=target_name, description=body.description.strip(), metadata_json=body.metadata_json)
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
    return {"status": "ok", "corpus": corpus_name, "updated_source_ids": updated_source_ids}


@router.post("/sources/{source_id}/reindex")
def trigger_reindex(source_id: int, body: ReindexRequest):
    try:
        result = admin_reindex_source(source_id=source_id, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/sources/{source_id}/enrich")
def trigger_enrichment(source_id: int, body: ReindexRequest):
    try:
        result = admin_rerun_enrichment(source_id=source_id, force=body.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@router.get("/jobs")
def get_jobs(source_id: Optional[int] = None):
    return {
        "ingestion_jobs": [row.__dict__ for row in list_ingestion_jobs(source_id=source_id)],
        "enrichment_jobs": [row.__dict__ for row in list_enrichment_jobs(source_id=source_id)],
    }


@router.get("/jobs/ingestion/{job_id}")
def get_ingestion_job_status(job_id: int):
    row = get_ingestion_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    return row.__dict__


@router.get("/jobs/enrichment/{job_id}")
def get_enrichment_job_status(job_id: int):
    row = get_enrichment_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    return row.__dict__


@router.post("/eval/run")
def run_eval(body: EvalRunRequest):
    report_kind = body.report_kind.strip().lower()
    if report_kind == "retrieval":
        report = run_retrieval_eval(cases=load_eval_cases(), report_path=RETRIEVAL_REPORT_FILE, debug=body.debug)
    elif report_kind == "benchmark":
        report = run_mode_benchmark(cases=load_benchmark_cases(), report_path=BENCHMARK_REPORT_FILE)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported report kind: {body.report_kind}")
    return {
        "status": "completed",
        "report_kind": report_kind,
        "summary": report.get("summary"),
        "report_metadata": report.get("report_metadata"),
        "path": str(_EVAL_REPORT_FILES[report_kind].relative_to(REPO_ROOT)),
    }


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
        "traces": list_traces(limit=limit, offset=offset),
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/traces/by-request/{request_id}")
def get_retrieval_trace_by_request(request_id: str):
    trace = get_trace(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace for request_id '{request_id}' not found")
    return {
        "trace": trace,
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }


@router.get("/traces/{trace_id}")
def get_retrieval_trace(trace_id: int):
    trace = get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return {
        "trace": trace,
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": get_effective_retrieval().model_dump(),
    }
