import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin_user
from app.auth.admin_modules import admin_modules_payload
from app.auth.context import get_current_user
from app.auth.high_impact import require_high_impact_approval
from app.corpus_policies import get_corpus_policy
from app.core.config import REPO_ROOT, settings
from app.core.logging import logger
from app.core.rate_limit import rate_limit_admin_expensive
from app.core_rag.retrieval import SearchFilters, SearchRequest, perform_search
from app.db.repo_acl import (
    assign_document_acl,
    explain_source_access,
    explain_user_access,
    list_access_summary,
    list_source_acl_map,
    replace_source_acl,
    replace_user_memberships,
)
from app.db.repo_actions import list_approval_requests, top_failed_queries
from app.db.repo_admin_audit import insert_admin_audit_event, list_admin_audit_events, verify_admin_audit_integrity
from app.db.repo_corpora import get_corpus, list_corpora, upsert_corpus
from app.db.repo_governance import (
    create_restriction,
    lift_restriction,
    list_restrictions,
    list_risk_signals,
)
from app.db.repo_jobs import (
    create_ingestion_job,
    get_enrichment_job,
    get_ingestion_job,
    list_enrichment_jobs,
    list_ingestion_jobs,
    update_ingestion_job,
)
from app.db.repo_priority_requests import (
    expire_stale_priority_requests,
    get_latest_priority_request_for_job,
    get_priority_request,
    list_priority_requests,
    update_priority_request_status,
)
from app.db.repo_profiles import (
    PROFILE_TYPES_FOR_TUNING,
    get_active_profile_name,
    get_profile,
    list_approved_registry_profiles,
    list_profiles,
    set_active_profile,
    upsert_profile,
)
from app.db.repo_sources import get_source_by_id, list_sources, update_source_admin_fields, update_source_status
from app.db.repo_semantic_cache import (
    bump_cache_revision,
    cache_health,
    invalidate_cache as invalidate_semantic_cache,
)
from app.db.repo_semantic_cache_policies import (
    activate_policy as activate_semantic_cache_policy,
    create_policy as create_semantic_cache_policy,
    disable_policy as disable_semantic_cache_policy,
    get_active_policy_version as get_active_semantic_cache_policy_version,
    get_policy as get_semantic_cache_policy,
    list_policies as list_semantic_cache_policies,
    policy_metrics as semantic_cache_policy_metrics,
    rollback_policy as rollback_semantic_cache_policy,
    update_policy as update_semantic_cache_policy,
)
from app.db.repo_traces import get_trace, get_trace_by_id, list_traces
from app.db.repo_tuning_configs import (
    create_embedding_experiment,
    create_candidate_draft,
    get_candidate_draft,
    get_live_configuration,
    list_embedding_experiments,
    list_candidate_drafts,
    list_model_warmups,
    list_tuning_history,
    promote_candidate_to_live,
    record_model_warmup,
    rollback_to_version,
    sync_live_configuration_record,
    update_candidate_draft,
)
from app.db.repo_query_mining import (
    annotate_cluster,
    build_failure_clusters,
    create_eval_pack_from_clusters,
    list_derived_eval_packs,
    list_failure_clusters,
    list_query_events,
)
from app.db.repo_eval_runs import get_eval_run, list_eval_runs
from app.db.repo_retention import run_retention_policy
from app.eval.compare_eval import DEFAULT_REPORT_FILE as BENCHMARK_REPORT_FILE
from app.eval.compare_eval import load_benchmark_cases, run_mode_benchmark
from app.eval.retrieval_eval import DEFAULT_REPORT_FILE as RETRIEVAL_REPORT_FILE
from app.eval.retrieval_eval import load_eval_cases, run_retrieval_eval
from app.ingestion.enrichment import admin_rerun_enrichment
from app.ingestion.jobs import admin_reindex_source, _reset_source_for_reindex
from app.ingestion.queue_metrics import priority_request_payload, summarize_ingestion_queue
from app.ingestion.queue_runtime import poke_ingestion_queue
from app.profiles.models import PROFILE_TYPE_MODELS
from app.profiles.resolver import get_active_profile_snapshot, get_effective_reranker, get_effective_retrieval, invalidate_cache
from app.seed.enterprise_acl import DEFAULT_PACK_DIR, seed_enterprise_acl_pack
from app.db.repo_access_requests import upsert_source_access_contacts
from app.tuning.sandbox_compare import run_sandbox_compare


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])

_EVAL_REPORT_FILES = {
    "retrieval": RETRIEVAL_REPORT_FILE,
    "benchmark": BENCHMARK_REPORT_FILE,
}
SANDBOX_TRANSFORM_TIMEOUT_MIN_MS = 20_000
SANDBOX_TRANSFORM_TIMEOUT_MAX_MS = 90_000


@router.get("/modules")
def get_admin_modules():
    return admin_modules_payload()


class AdminModulesUpdateRequest(BaseModel):
    enabled_modules: Optional[list[str]] = None


@router.patch("/modules")
def patch_admin_modules(body: AdminModulesUpdateRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="admin_modules.update")
    from app.db.repo_runtime_settings import delete_setting, set_setting

    before = admin_modules_payload()
    try:
        if body.enabled_modules is None:
            delete_setting("admin_modules_enabled")
        else:
            set_setting("admin_modules_enabled", body.enabled_modules, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after = admin_modules_payload()
    insert_admin_audit_event(
        event_type="config",
        action="admin_modules.update",
        resource_type="runtime_setting",
        resource_id="admin_modules_enabled",
        resource_name="Admin console modules",
        before_json=before,
        after_json=after,
        event_json=approval,
        actor=actor,
    )
    return after


class ActiveProfileRequest(BaseModel):
    profile_type: str
    profile_name: str


class ProfileCreateRequest(BaseModel):
    profile_type: str
    profile_name: str
    config: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ProfileUpdateRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


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


class QueuePriorityUpdateRequest(BaseModel):
    priority: int = Field(ge=50, le=300)
    reason: str = ""
    preview_only: bool = False


class QueuePriorityDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(under_review|approved|denied)$")
    reason: str = ""


class QueueControlRequest(BaseModel):
    action: str = Field(pattern="^(pause|resume|cancel|requeue|retry)$")
    reason: str = ""


class AccessSeedImportRequest(BaseModel):
    pack_dir: Optional[str] = None


class UserMembershipUpdateRequest(BaseModel):
    group_names: list[str] = Field(default_factory=list)


class SourceAclUpdateRequest(BaseModel):
    group_names: list[str] = Field(default_factory=list)


class SourceContactInput(BaseModel):
    contact_role: str
    contact_external_user_id: Optional[str] = None
    contact_email: Optional[str] = None
    contact_display_name: Optional[str] = None


class SourceContactsUpdateRequest(BaseModel):
    contacts: list[SourceContactInput] = Field(default_factory=list)


class BulkGroupAssignmentRequest(BaseModel):
    group_name: str
    source_ids: list[int] = Field(default_factory=list)


class BulkSourceAssignmentRequest(BaseModel):
    source_id: int
    group_names: list[str] = Field(default_factory=list)


class CandidateDraftRequest(BaseModel):
    name: str
    description: str = ""
    selected_profiles: dict[str, str] = Field(default_factory=dict)
    retrieval_override_config: dict[str, Any] = Field(default_factory=dict)


class CandidateDraftUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    selected_profiles: Optional[dict[str, str]] = None
    retrieval_override_config: Optional[dict[str, Any]] = None


class TuningCompareRequest(BaseModel):
    question: str
    draft_id: Optional[int] = None
    selected_profiles: dict[str, str] = Field(default_factory=dict)
    retrieval_override_config: dict[str, Any] = Field(default_factory=dict)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    chunk_size_cap_chars: int = Field(default=512, ge=128, le=2048)
    k_retrieval_count: int = Field(default=5, ge=1, le=20)


class TuningPromotionRequest(BaseModel):
    draft_id: int
    promotion_note: str = ""
    embedding_experiment_id: Optional[int] = None
    eval_run_id: Optional[int] = None


class TuningRollbackRequest(BaseModel):
    version_label: str
    reason: str = ""
    eval_run_id: Optional[int] = None


class TuningEvalRunRequest(BaseModel):
    draft_id: Optional[int] = None
    pack_names: list[str] = Field(default_factory=list)
    sample_size: Optional[int] = Field(default=150, ge=1, le=2000)
    k: int = Field(default=10, ge=1, le=50)


class EmbeddingExperimentRequest(BaseModel):
    candidate_config_id: Optional[int] = None
    target_embedding_profile: str
    scope_type: str = Field(pattern="^(selected_5_files|all_files)$")
    source_ids: list[int] = Field(default_factory=list)
    warning_acknowledged: bool = False
    confirmation_count: int = Field(default=0, ge=0)


class WarmupRequest(BaseModel):
    embeddings: list[str] = Field(default_factory=list)
    rerankers: list[str] = Field(default_factory=list)


class QueryClusterAnnotationRequest(BaseModel):
    annotation_json: dict[str, Any] = Field(default_factory=dict)


class DerivedEvalPackRequest(BaseModel):
    name: str
    cluster_ids: list[int] = Field(default_factory=list)


class SemanticCachePolicyRequest(BaseModel):
    name: str
    justification: str = ""
    owner: str = ""
    review_at: Optional[datetime] = None
    enabled: bool = False
    match_mode: str = Field(default="exact", pattern="^(exact|semantic)$")
    similarity_threshold: float = Field(default=0.92, ge=0.5, le=0.999)
    ttl_seconds: int = Field(default=900, ge=30, le=86400)
    max_active_entries: int = Field(default=1000, ge=1, le=100000)
    allow_corpora: list[str] = Field(default_factory=list)
    deny_corpora: list[str] = Field(default_factory=list)
    allow_groups: list[str] = Field(default_factory=list)
    deny_groups: list[str] = Field(default_factory=list)
    allow_questions: list[str] = Field(default_factory=list)
    deny_questions: list[str] = Field(default_factory=list)


class SemanticCachePolicyActivationRequest(BaseModel):
    confirmation: str


class SemanticCachePolicyRollbackRequest(BaseModel):
    version_id: int


class SemanticCachePolicyCheckRequest(BaseModel):
    question: str
    mode: Optional[str] = "hybrid"


class GovernanceRestrictionRequest(BaseModel):
    user_external_user_id: Optional[str] = None
    user_email: Optional[str] = None
    restriction_type: str = Field(pattern="^(warn_only|extra_review_required|access_request_block|query_block)$")
    reason: str
    duration_hours: Optional[int] = None


class GovernanceRestrictionLiftRequest(BaseModel):
    reason: str = ""


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
    from app.freshness import source_freshness

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
        "freshness": source_freshness(row),
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


def _validated_profile_config(*, profile_type: str, config: dict[str, Any], base_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if profile_type not in PROFILE_TYPE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown profile type: {profile_type}")
    merged = dict(base_config or {})
    merged.update(config or {})
    model_cls = PROFILE_TYPE_MODELS[profile_type]
    try:
        return model_cls(**merged).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Profile config validation failed: {exc}") from exc


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {key: _redact_secrets(item) for key, item in value.items() if key != "api_key_configured"}
        if "api_key" in value:
            redacted["api_key"] = ""
            redacted["api_key_configured"] = bool(value.get("api_key"))
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _transform_posture(config: dict[str, Any]) -> dict[str, Any]:
    strategy: list[str] = []
    if config.get("rewrite_enabled"):
        strategy.append("rewrite")
    if config.get("expansion_enabled"):
        strategy.append("expansion")
    if config.get("hyde_enabled"):
        strategy.append("hyde")
    return {
        "enabled": bool(config.get("query_transform_enabled")),
        "rewrite_enabled": bool(config.get("rewrite_enabled")),
        "expansion_enabled": bool(config.get("expansion_enabled")),
        "hyde_enabled": bool(config.get("hyde_enabled")),
        "transform_timeout_ms": int(config.get("transform_timeout_ms") or 0),
        "transform_max_variants": int(config.get("transform_max_variants") or 0),
        "multi_query_enabled": bool(config.get("multi_query_enabled")),
        "strategy": strategy,
    }


def _effective_tuning_selected_profiles(selected_profiles: Optional[dict[str, str]]) -> dict[str, str]:
    live_selected = dict((get_live_configuration() or {}).get("selected_profiles") or {})
    effective = dict(live_selected)
    for profile_type in PROFILE_TYPES_FOR_TUNING:
        token = str((selected_profiles or {}).get(profile_type) or "").strip()
        if token:
            effective[profile_type] = token
    return effective


def _enforce_llm_provider(*, profile_type: str, config: dict[str, Any]) -> None:
    """AR17: an LLM profile may only name a provider the registry can serve."""
    if profile_type != "llm":
        return
    from app.llm.providers import supported_providers

    provider = str(config.get("provider") or "").strip().lower()
    if provider not in supported_providers():
        raise HTTPException(
            status_code=422,
            detail={"error": "unknown_llm_provider", "message": f"Provider '{provider}' is not supported. Known: {supported_providers()}"},
        )


def _enforce_embedding_dimension_coherence(*, profile_type: str, config: dict[str, Any]) -> None:
    """AR2: an embedding profile may not declare a dimension its model does not
    produce (the audit found bge-small registered as 768; it produces 384)."""
    if profile_type != "embedding":
        return
    from app.coherence import validate_embedding_profile_dimension

    try:
        validate_embedding_profile_dimension(
            model_name=str(config.get("model") or ""),
            declared_dimension=int(config.get("dimension") or 0),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "embedding_dimension_mismatch", "message": str(exc)})
    except Exception as exc:  # model not loadable locally
        raise HTTPException(
            status_code=422,
            detail={
                "error": "embedding_model_unverifiable",
                "message": f"Could not load model to verify its dimension: {exc}",
            },
        )


def _validated_retrieval_override(*, selected_profiles: dict[str, str], override_config: Optional[dict[str, Any]]) -> dict[str, Any]:
    candidate = dict(override_config or {})
    if not candidate:
        return {}
    retrieval_profile_name = str(selected_profiles.get("retrieval") or "").strip()
    if not retrieval_profile_name:
        raise HTTPException(status_code=422, detail="Retrieval override requires a selected retrieval profile")
    retrieval_profile = get_profile("retrieval", retrieval_profile_name)
    if not retrieval_profile:
        raise HTTPException(status_code=404, detail=f"Profile '{retrieval_profile_name}' of type 'retrieval' not found")
    base_config = retrieval_profile["config_json"] or {}
    if candidate.get("query_transform_enabled") or "transform_timeout_ms" in candidate:
        try:
            timeout_ms = int(candidate.get("transform_timeout_ms") or base_config.get("transform_timeout_ms") or SANDBOX_TRANSFORM_TIMEOUT_MIN_MS)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Transform timeout must be numeric") from exc
        candidate["transform_timeout_ms"] = min(SANDBOX_TRANSFORM_TIMEOUT_MAX_MS, max(SANDBOX_TRANSFORM_TIMEOUT_MIN_MS, timeout_ms))
    validated = _validated_profile_config(profile_type="retrieval", config=candidate, base_config=base_config)
    # Preserve exactly the keys the operator requested so lineage records intent
    # deterministically, regardless of the selected base profile's current values.
    return {key: value for key, value in validated.items() if key in candidate}


def _profile_payload(row: dict[str, Any], *, active_map: dict[str, Optional[str]]) -> dict[str, Any]:
    profile_type = row["profile_type"]
    config = _validated_profile_config(profile_type=profile_type, config=row["config_json"] or {})
    payload = {
        "id": row["id"],
        "profile_type": profile_type,
        "name": row["name"],
        "config": _redact_secrets(config),
        "is_default": row["is_default"],
        "is_active": row["name"] == active_map.get(profile_type),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }
    if profile_type == "retrieval":
        payload["transform_posture"] = _transform_posture(config)
    return payload


def _source_payload_with_acl(row, acl_map: dict[int, list[str]]) -> dict[str, Any]:
    payload = _source_to_payload(row)
    payload["corpus_name"] = (row.source_metadata_json or {}).get("corpus")
    payload["acl_groups"] = acl_map.get(int(row.id), [])
    return payload


def _source_row_lookup() -> dict[int, Any]:
    return {int(row.id): row for row in list_sources()}


def _latest_priority_requests_by_job() -> dict[int, Any]:
    expire_stale_priority_requests()
    latest: dict[int, Any] = {}
    for request in list_priority_requests(limit=300):
        latest.setdefault(int(request.job_id), request)
    return latest


def _ingestion_queue_payloads(*, source_id: Optional[int] = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_lookup = _source_row_lookup()
    jobs = list_ingestion_jobs(source_id=source_id)
    priority_lookup = _latest_priority_requests_by_job()
    return summarize_ingestion_queue(jobs, source_lookup, priority_lookup)


def _preview_priority_change(job_id: int, new_priority: int) -> dict[str, Any]:
    source_lookup = _source_row_lookup()
    jobs = list_ingestion_jobs()
    priority_lookup = _latest_priority_requests_by_job()
    before_payloads, _ = summarize_ingestion_queue(jobs, source_lookup, priority_lookup)
    adjusted_jobs = []
    for job in jobs:
        if int(job.id) == job_id:
            job.priority = new_priority
        adjusted_jobs.append(job)
    after_payloads, _ = summarize_ingestion_queue(adjusted_jobs, source_lookup, priority_lookup)
    before_by_id = {int(item["id"]): item for item in before_payloads}
    impacted = []
    for after in after_payloads:
        before = before_by_id.get(int(after["id"]))
        if before is None:
            continue
        if before.get("queue_position") != after.get("queue_position") or before.get("eta_window") != after.get("eta_window"):
            impacted.append(
                {
                    "job_id": after["id"],
                    "before_queue_position": before.get("queue_position"),
                    "after_queue_position": after.get("queue_position"),
                    "before_eta_seconds": (before.get("eta_window") or {}).get("seconds"),
                    "after_eta_seconds": (after.get("eta_window") or {}).get("seconds"),
                }
            )
    return {"impacted_jobs": impacted[:25], "job_count": len(impacted)}


@router.get("/profiles")
def get_profiles(profile_type: Optional[str] = None):
    rows = list_profiles(profile_type)
    active_map: dict[str, Optional[str]] = {}
    for row in rows:
        pt = row["profile_type"]
        if pt not in active_map:
            active_map[pt] = get_active_profile_name(pt)
    return {"profiles": [_profile_payload(row, active_map=active_map) for row in rows]}


@router.post("/profiles")
def create_profile(body: ProfileCreateRequest):
    profile_type = str(body.profile_type or "").strip()
    profile_name = str(body.profile_name or "").strip()
    if not profile_name:
        raise HTTPException(status_code=422, detail="profile_name is required")
    if get_profile(profile_type, profile_name):
        raise HTTPException(status_code=409, detail=f"Profile '{profile_name}' of type '{profile_type}' already exists")

    validated_config = _validated_profile_config(profile_type=profile_type, config=body.config)
    _enforce_embedding_dimension_coherence(profile_type=profile_type, config=validated_config)
    _enforce_llm_provider(profile_type=profile_type, config=validated_config)
    upsert_profile(profile_type, profile_name, validated_config, is_default=body.is_default)
    actor = get_current_user()
    insert_admin_audit_event(
        event_type="profile",
        action="profile.create",
        resource_type="profile",
        resource_id=f"{profile_type}:{profile_name}",
        resource_name=profile_name,
        profile_type=profile_type,
        profile_name=profile_name,
        before_json={},
        after_json={"config": _redact_secrets(validated_config), "is_default": body.is_default},
        actor=actor,
    )
    return {"status": "ok", "profile": _profile_payload(get_profile(profile_type, profile_name), active_map={profile_type: get_active_profile_name(profile_type)})}


@router.patch("/profiles/{profile_type}/{profile_name}")
def update_profile(profile_type: str, profile_name: str, body: ProfileUpdateRequest):
    existing = get_profile(profile_type, profile_name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' of type '{profile_type}' not found")

    validated_config = _validated_profile_config(profile_type=profile_type, config=body.config, base_config=existing["config_json"] or {})
    _enforce_embedding_dimension_coherence(profile_type=profile_type, config=validated_config)
    _enforce_llm_provider(profile_type=profile_type, config=validated_config)
    upsert_profile(profile_type, profile_name, validated_config, is_default=bool(existing["is_default"]))

    if get_active_profile_name(profile_type) == profile_name:
        invalidate_cache(profile_type)
        invalidate_semantic_cache(reason=f"profile_update:{profile_type}:{profile_name}")
        bump_cache_revision(scope_type="profile", reason=f"profile_update:{profile_type}:{profile_name}")
        sync_live_configuration_record()

    actor = get_current_user()
    insert_admin_audit_event(
        event_type="profile",
        action="profile.update",
        resource_type="profile",
        resource_id=f"{profile_type}:{profile_name}",
        resource_name=profile_name,
        profile_type=profile_type,
        profile_name=profile_name,
        before_json={"config": _redact_secrets(existing["config_json"] or {}), "is_default": bool(existing["is_default"])},
        after_json={"config": _redact_secrets(validated_config), "is_default": bool(existing["is_default"])},
        actor=actor,
    )
    return {"status": "ok", "profile": _profile_payload(get_profile(profile_type, profile_name), active_map={profile_type: get_active_profile_name(profile_type)})}


@router.post("/profiles/active")
def set_active(body: ActiveProfileRequest):
    if body.profile_type not in PROFILE_TYPE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown profile type: {body.profile_type}")

    profile = get_profile(body.profile_type, body.profile_name)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile_name}' of type '{body.profile_type}' not found")

    from app.coherence import is_draft_profile_name

    if is_draft_profile_name(body.profile_name):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "draft_profile_activation_blocked",
                "message": "Draft profiles cannot be activated as live; promote them through the tuning workflow.",
            },
        )

    validated_config = _validated_profile_config(profile_type=body.profile_type, config=profile["config_json"] or {})
    _enforce_llm_provider(profile_type=body.profile_type, config=validated_config)

    # AR7: a dimension-changing embedding activation cannot go live through the
    # plain activate path — it would orphan the index. Route it through the
    # managed swap lifecycle instead.
    if body.profile_type == "embedding":
        from app.coherence import index_vector_dimension

        declared = int((profile["config_json"] or {}).get("dimension") or 0)
        column = index_vector_dimension()
        if column is not None and declared != column and body.profile_name != get_active_profile_name("embedding"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "embedding_reindex_required",
                    "message": (
                        f"Activating '{body.profile_name}' changes the embedding dimension "
                        f"({declared} vs index vector({column})). Use POST /admin/embedding/swap/begin "
                        "to run a managed reindex; direct activation is blocked to protect the index."
                    ),
                    "profile_dimension": declared,
                    "index_dimension": column,
                },
            )

    previous_profile_name = get_active_profile_name(body.profile_type)
    set_active_profile(body.profile_type, body.profile_name)
    invalidate_cache(body.profile_type)
    invalidate_semantic_cache(reason=f"profile_activate:{body.profile_type}")
    bump_cache_revision(scope_type="profile", reason=f"profile_activate:{body.profile_type}")
    # get_live_configuration normalizes *_json row keys to the documented
    # selected_profiles/resolved_config/lineage response contract.
    live_config = get_live_configuration()
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
    return {
        "status": "ok",
        "profile_type": body.profile_type,
        "profile_name": body.profile_name,
        "live_configuration": _redact_secrets(live_config),
    }


@router.get("/health/coherence")
def health_coherence(deep: bool = False):
    """AR2: per-invariant configuration coherence report (consumed by AR10).

    deep=true additionally loads embedding models to verify declared dimensions
    against actual model output (slower; on-demand only).
    """
    from app.coherence import run_coherence_checks

    return run_coherence_checks(deep=deep)


@router.get("/system/posture")
def system_posture_endpoint():
    """AR15: read-only operator posture — serving state, cache on/off, retrieval
    defaults, eval enforcement, worker posture, rate limits, cost governance —
    each with how it is changed (UI / env / policy / profile)."""
    from app.system_posture import system_posture

    return system_posture()


@router.get("/health/dashboard")
def health_dashboard_endpoint(deep: bool = False):
    """AR10: one operator-facing answer to 'is this system coherent right now?'
    — AR2 coherence invariants plus reranker warm-up, cache state, and the
    AR3/AR4 eval gate, with a P0 banner."""
    from app.health import health_dashboard

    return health_dashboard(deep=deep)


class EmbeddingSwapPlanRequest(BaseModel):
    target_profile_name: str


class EmbeddingSwapRunRequest(BaseModel):
    run_id: int
    batch_limit: Optional[int] = Field(default=None, ge=1, le=100000)


class EmbeddingSwapAbortRequest(BaseModel):
    run_id: int
    reason: str = "operator_abort"


@router.get("/embedding/serving")
def embedding_serving_state():
    """AR7: is vector search serviceable right now, and is a swap in flight?"""
    from app.coherence import vector_serving_state
    from app.embedding.lifecycle import list_swap_runs

    runs = list_swap_runs(limit=1)
    return {"vector_serving": vector_serving_state(), "latest_swap": runs[0] if runs else None}


@router.post("/embedding/swap/plan")
def plan_embedding_swap_endpoint(body: EmbeddingSwapPlanRequest):
    from app.embedding.lifecycle import plan_embedding_swap

    try:
        return {"plan": plan_embedding_swap(target_profile_name=body.target_profile_name)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/embedding/swap/begin")
def begin_embedding_swap_endpoint(body: EmbeddingSwapPlanRequest, request: Request):
    actor = get_current_user()
    require_high_impact_approval(request=request, actor=actor, action="embedding.swap.begin")
    from app.embedding.lifecycle import begin_embedding_swap

    try:
        run = begin_embedding_swap(target_profile_name=body.target_profile_name, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="embedding",
        action="embedding.swap.begin",
        resource_type="embedding_swap_run",
        resource_id=str(run["id"]),
        resource_name=body.target_profile_name,
        event_json={"target_dimension": run["target_dimension"], "source_dimension": run["source_dimension"]},
        actor=actor,
    )
    return {"swap_run": run}


@router.post("/embedding/swap/run")
def run_embedding_swap_endpoint(body: EmbeddingSwapRunRequest, request: Request, _rate_limit: None = Depends(rate_limit_admin_expensive)):
    actor = get_current_user()
    from app.embedding.lifecycle import run_embedding_swap

    try:
        return {"swap_run": run_embedding_swap(run_id=body.run_id, batch_limit=body.batch_limit)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/embedding/swap/verify")
def verify_embedding_swap_endpoint(body: EmbeddingSwapRunRequest):
    from app.embedding.lifecycle import verify_embedding_swap

    try:
        return {"swap_run": verify_embedding_swap(run_id=body.run_id)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/embedding/swap/abort")
def abort_embedding_swap_endpoint(body: EmbeddingSwapAbortRequest):
    actor = get_current_user()
    from app.embedding.lifecycle import abort_embedding_swap

    try:
        run = abort_embedding_swap(run_id=body.run_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="embedding",
        action="embedding.swap.abort",
        resource_type="embedding_swap_run",
        resource_id=str(body.run_id),
        resource_name=run.get("target_profile_name"),
        event_json={"reason": body.reason},
        actor=actor,
    )
    return {"swap_run": run}


@router.get("/embedding/swaps")
def list_embedding_swaps_endpoint():
    from app.embedding.lifecycle import list_swap_runs

    return {"swap_runs": list_swap_runs(limit=50)}


class FeedbackProposeRequest(BaseModel):
    cluster_id: int


class FeedbackAppendRequest(BaseModel):
    pack_name: str
    cases: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackReviewRequest(BaseModel):
    pack_name: str
    case_id: str
    relevant: dict[str, int] = Field(default_factory=dict)
    review_status: str = Field(default="reviewed", pattern="^(reviewed|unreviewed)$")


@router.post("/feedback-eval/propose")
def feedback_eval_propose(body: FeedbackProposeRequest):
    """AR12: propose quarantined eval cases from a failure cluster (not persisted)."""
    from app.eval.feedback_flywheel import propose_cases_from_cluster

    try:
        return propose_cases_from_cluster(body.cluster_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feedback-eval/append")
def feedback_eval_append(body: FeedbackAppendRequest):
    actor = get_current_user()
    from app.eval.feedback_flywheel import append_cases_to_pack

    try:
        result = append_cases_to_pack(body.pack_name, body.cases, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="eval",
        action="feedback_eval.append",
        resource_type="eval_pack",
        resource_id=body.pack_name,
        resource_name=body.pack_name,
        event_json={"added": result["added"], "added_count": result["added_count"]},
        actor=actor,
    )
    return result


@router.post("/feedback-eval/review")
def feedback_eval_review(body: FeedbackReviewRequest):
    actor = get_current_user()
    from app.eval.feedback_flywheel import review_pack_case

    try:
        case = review_pack_case(
            body.pack_name, body.case_id, relevant=body.relevant, review_status=body.review_status, reviewer=actor.email if actor else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="eval",
        action="feedback_eval.review",
        resource_type="eval_pack_case",
        resource_id=body.case_id,
        resource_name=body.pack_name,
        event_json={"review_status": body.review_status, "relevant": body.relevant},
        actor=actor,
    )
    return {"case": case}


@router.get("/feedback-eval/quarantine")
def feedback_eval_quarantine(pack_name: str):
    from app.eval.feedback_flywheel import quarantine_summary

    try:
        return quarantine_summary(pack_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/feedback-eval/trend")
def feedback_eval_trend():
    from app.eval.feedback_flywheel import pack_passrate_trend

    return pack_passrate_trend()


@router.get("/cost/summary")
def cost_summary_endpoint(group_by: str = "retrieval_mode"):
    """AR11: token/cost rollup. group_by=retrieval_mode answers 'deep research vs
    fast mode cost'; group_by=model gives per-model spend."""
    from app.db.repo_generation_usage import cost_summary
    from app.llm.pricing import cost_alert_source, cost_alert_usd, effective_price_table, price_table_source

    payload = cost_summary(group_by=group_by)
    payload["governance"] = {
        "llm_cost_alert_usd": {"effective": cost_alert_usd(), "source": cost_alert_source()},
        "llm_price_table": {"effective": effective_price_table(), "source": price_table_source()},
    }
    return payload


@router.get("/llm/providers")
def list_llm_providers():
    """AR9: provider names a profile may select (gated by the approved-model
    registry as before). Switching providers is a profile change, not a code edit."""
    from app.llm.providers import supported_providers

    return {"providers": supported_providers()}


class LLMVerifyRequest(BaseModel):
    profile_name: Optional[str] = None
    config: Optional[dict[str, Any]] = None


@router.post("/llm/verify")
def verify_llm_profile(body: LLMVerifyRequest):
    """AR17: preflight a candidate LLM profile (by name or inline config) WITHOUT
    activating it — applied request-scoped via profile_overrides so live traffic
    is never affected."""
    from app.llm.client import verify_llm_connection
    from app.profiles.models import LLMProfileConfig
    from app.profiles.resolver import profile_overrides

    if body.profile_name:
        profile = get_profile("llm", body.profile_name)
        if not profile:
            raise HTTPException(status_code=404, detail=f"LLM profile '{body.profile_name}' not found")
        config = profile["config_json"] or {}
    else:
        config = body.config or {}
    try:
        candidate = LLMProfileConfig(**config)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid LLM config: {exc}") from exc
    _enforce_llm_provider(profile_type="llm", config=candidate.model_dump())
    with profile_overrides(llm=candidate):
        result = verify_llm_connection(update_global=False)
    return {**result, "provider": candidate.provider, "model": candidate.model}


_RUNTIME_SETTING_KEYS = {"llm_cost_alert_usd", "llm_price_table", "tuning_eval_enforcement"}


class RuntimeSettingRequest(BaseModel):
    key: str
    value: Any


@router.get("/runtime-settings")
def get_runtime_settings():
    """AR17: console-editable governed settings + their effective values."""
    from app.db.repo_runtime_settings import all_settings
    from app.eval.promotion_evidence import enforcement_mode_source, resolve_enforcement_mode
    from app.llm.pricing import cost_alert_source, cost_alert_usd, effective_price_table, price_table_source

    overrides = all_settings()
    return {
        "settings": {
            "llm_cost_alert_usd": {
                "effective": cost_alert_usd(),
                "override": overrides.get("llm_cost_alert_usd"),
                "source": cost_alert_source(),
            },
            "llm_price_table": {
                "effective": effective_price_table(),
                "override": overrides.get("llm_price_table"),
                "source": price_table_source(),
            },
            "tuning_eval_enforcement": {
                "effective": resolve_enforcement_mode(),
                "override": overrides.get("tuning_eval_enforcement"),
                "source": enforcement_mode_source(),
            },
        },
        "editable_keys": sorted(_RUNTIME_SETTING_KEYS),
    }


@router.patch("/runtime-settings")
def patch_runtime_settings(body: RuntimeSettingRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="runtime_settings.update")
    if body.key not in _RUNTIME_SETTING_KEYS:
        raise HTTPException(status_code=422, detail={"error": "not_editable", "message": f"'{body.key}' is not a runtime-editable setting."})
    from app.db.repo_runtime_settings import delete_setting, set_setting

    try:
        before = get_runtime_settings()["settings"][body.key]
        if body.value is None or (body.key == "tuning_eval_enforcement" and str(body.value).strip() == ""):
            delete_setting(body.key)
        else:
            set_setting(body.key, body.value, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = get_runtime_settings()
    insert_admin_audit_event(
        event_type="config",
        action="runtime_settings.update",
        resource_type="runtime_setting",
        resource_id=body.key,
        resource_name=body.key,
        before_json=before,
        after_json=response["settings"][body.key],
        event_json={"key": body.key, **approval},
        actor=actor,
    )
    return response


@router.get("/profiles/metadata")
def get_profile_metadata():
    retrieval_settings = get_effective_retrieval().model_dump()
    reranker_settings = get_effective_reranker().model_dump()
    live_configuration = get_live_configuration()
    current_live_retrieval = ((live_configuration.get("resolved_config") or {}).get("retrieval") or {}) if live_configuration else {}
    live_retrieval_config = (current_live_retrieval.get("config") or retrieval_settings) if isinstance(current_live_retrieval, dict) else retrieval_settings
    return {
        "active_profiles": get_active_profile_snapshot(),
        "retrieval_settings": retrieval_settings,
        "reranker_settings": reranker_settings,
        "current_live_retrieval": {
            "profile_name": ((live_configuration.get("selected_profiles") or {}).get("retrieval")) if live_configuration else get_active_profile_name("retrieval"),
            "config": live_retrieval_config,
            "transform_posture": _transform_posture(live_retrieval_config),
        },
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
            "query_transform_enabled": retrieval_settings.get("query_transform_enabled"),
            "rewrite_enabled": retrieval_settings.get("rewrite_enabled"),
            "expansion_enabled": retrieval_settings.get("expansion_enabled"),
            "hyde_enabled": retrieval_settings.get("hyde_enabled"),
            "transform_timeout_ms": retrieval_settings.get("transform_timeout_ms"),
            "transform_max_variants": retrieval_settings.get("transform_max_variants"),
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


@router.get("/retrieval/evidence")
def get_retrieval_evidence():
    from app.eval.retrieval_ablation import REPORT_PATH

    if not REPORT_PATH.exists():
        raise HTTPException(status_code=503, detail="AR14 retrieval evidence report has not been generated")
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@router.get("/tuning/configurations")
def get_tuning_configurations():
    live_configuration = get_live_configuration()
    approved_options: dict[str, list[dict[str, Any]]] = {}
    for profile_type in ("llm", "embedding", "reranker"):
        approved_options[profile_type] = [
            {
                "name": row["name"],
                "display_name": (row["config"] or {}).get("display_name") or row["name"],
                "model": (row["config"] or {}).get("model"),
                "config": row["config"],
            }
            for row in list_approved_registry_profiles(profile_type)
        ]
    approved_options["retrieval"] = [
        {
            "name": row["name"],
            "display_name": (row["config_json"] or {}).get("display_name") or row["name"],
            "config": row["config_json"],
        }
        for row in list_profiles("retrieval")
    ]
    return {
        "live_configuration": _redact_secrets(live_configuration),
        "candidate_drafts": _redact_secrets(list_candidate_drafts()),
        "approved_options": _redact_secrets(approved_options),
        "profile_types": list(PROFILE_TYPES_FOR_TUNING),
    }


@router.post("/tuning/drafts")
def create_tuning_draft(body: CandidateDraftRequest):
    actor = get_current_user()
    effective_selected_profiles = _effective_tuning_selected_profiles(body.selected_profiles)
    try:
        draft = create_candidate_draft(
            name=body.name,
            description=body.description,
            selected_profiles=effective_selected_profiles,
            retrieval_override_config=_validated_retrieval_override(
                selected_profiles=effective_selected_profiles,
                override_config=body.retrieval_override_config,
            ),
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.draft.create",
        resource_type="tuning_config",
        resource_id=str(draft["id"]),
        resource_name=draft["name"],
        before_json={},
        after_json=_redact_secrets(draft),
        event_json={"version_label": draft["version_label"], "status": draft["status"]},
        actor=actor,
    )
    return {"draft": _redact_secrets(draft)}


@router.patch("/tuning/drafts/{draft_id}")
def patch_tuning_draft(draft_id: int, body: CandidateDraftUpdateRequest):
    actor = get_current_user()
    before = next((item for item in list_candidate_drafts() if int(item["id"]) == int(draft_id)), None)
    if not before:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    effective_selected_profiles = _effective_tuning_selected_profiles(body.selected_profiles or before.get("selected_profiles") or {})
    try:
        draft = update_candidate_draft(
            draft_id,
            name=body.name,
            description=body.description,
            selected_profiles=effective_selected_profiles,
            retrieval_override_config=_validated_retrieval_override(
                selected_profiles=effective_selected_profiles,
                override_config=body.retrieval_override_config,
            ) if body.retrieval_override_config is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.draft.update",
        resource_type="tuning_config",
        resource_id=str(draft["id"]),
        resource_name=draft["name"],
        before_json=_redact_secrets(before),
        after_json=_redact_secrets(draft),
        event_json={"version_label": draft["version_label"], "status": draft["status"]},
        actor=actor,
    )
    return {"draft": _redact_secrets(draft)}


@router.post("/tuning/compare")
def run_tuning_compare(body: TuningCompareRequest):
    actor = get_current_user()
    live_configuration = get_live_configuration()
    live_selected = dict(live_configuration.get("selected_profiles") or {})
    if not live_selected:
        raise HTTPException(status_code=422, detail="Live configuration is not ready for sandbox compare")

    selected_profiles = dict(live_selected)
    if body.draft_id is not None:
        draft = get_candidate_draft(body.draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail=f"Draft {body.draft_id} not found")
        selected_profiles.update({key: str(value) for key, value in (draft.get("selected_profiles") or {}).items() if value})
        retrieval_override_config = dict((draft.get("lineage") or {}).get("retrieval_override_config") or {})
    else:
        retrieval_override_config = {}
    selected_profiles.update({key: str(value) for key, value in body.selected_profiles.items() if value})
    retrieval_override_config = _validated_retrieval_override(
        selected_profiles=selected_profiles,
        override_config=body.retrieval_override_config or retrieval_override_config,
    )

    try:
        compare = run_sandbox_compare(
            question=body.question,
            live_selected_profiles=live_selected,
            selected_profiles=selected_profiles,
            retrieval_override_config=retrieval_override_config,
            temperature=body.temperature,
            top_p=body.top_p,
            chunk_size_cap_chars=body.chunk_size_cap_chars,
            k_retrieval_count=body.k_retrieval_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.compare.run",
        resource_type="tuning_compare",
        resource_id=str(body.draft_id or "ad-hoc"),
        resource_name=(compare.get("candidate_run") or {}).get("label") or "sandbox",
        before_json={"live_selected_profiles": live_selected},
        after_json={
            "candidate_selected_profiles": (compare.get("candidate_run") or {}).get("selected_profiles") or selected_profiles,
            "summary": compare.get("summary"),
            "warnings": compare.get("warnings"),
        },
        event_json={
            "question": body.question,
            "chunk_size_cap_chars": body.chunk_size_cap_chars,
            "k_retrieval_count": body.k_retrieval_count,
            "temperature": body.temperature,
            "top_p": body.top_p,
            "retrieval_override_config": retrieval_override_config,
        },
        actor=actor,
    )
    return compare


@router.get("/tuning/history")
def get_tuning_history():
    return _redact_secrets(list_tuning_history(limit=100))


@router.post("/tuning/embedding-experiments")
def create_tuning_embedding_experiment(body: EmbeddingExperimentRequest):
    actor = get_current_user()
    live_configuration = get_live_configuration()
    basis_embedding = str((live_configuration.get("selected_profiles") or {}).get("embedding") or "")
    if not basis_embedding:
        raise HTTPException(status_code=422, detail="Live embedding profile is not available")
    try:
        experiment = create_embedding_experiment(
            candidate_config_id=body.candidate_config_id,
            basis_embedding_profile=basis_embedding,
            target_embedding_profile=body.target_embedding_profile,
            scope_type=body.scope_type,
            source_ids=body.source_ids,
            warning_acknowledged=body.warning_acknowledged,
            confirmation_count=body.confirmation_count,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.embedding.scope_selected",
        resource_type="embedding_experiment",
        resource_id=str(experiment["id"]),
        resource_name=body.target_embedding_profile,
        after_json=experiment,
        actor=actor,
    )
    return {"embedding_experiment": experiment}


@router.get("/tuning/embedding-experiments")
def get_tuning_embedding_experiments():
    return {"embedding_experiments": list_embedding_experiments(limit=100)}


@router.post("/tuning/eval-runs")
def run_tuning_eval(body: TuningEvalRunRequest, request: Request, _rate_limit: None = Depends(rate_limit_admin_expensive)):
    """AR4: run AR3 eval packs under a candidate draft's bundle (or the live
    configuration) and persist the result as promotion evidence."""
    actor = get_current_user()
    from app.eval.promotion_evidence import run_candidate_eval

    try:
        run = run_candidate_eval(
            draft_id=body.draft_id,
            pack_names=body.pack_names or None,
            sample_size=body.sample_size,
            k=body.k,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.eval_run",
        resource_type="tuning_eval_run",
        resource_id=str(run["id"]),
        resource_name=run["run_label"],
        event_json={
            "draft_id": body.draft_id,
            "gate_status": run["gate_status"],
            "gate_aggregates": run["gate_aggregates"],
            "sample_size": body.sample_size,
        },
        actor=actor,
    )
    return {"eval_run": run}


@router.get("/tuning/eval-runs")
def get_tuning_eval_runs(draft_id: Optional[int] = None):
    return {"eval_runs": list_eval_runs(draft_id=draft_id, limit=100)}


def _parse_event_timestamp(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace(" ", "T"))


def _resolve_promotion_eval_evidence(*, draft: dict[str, Any], eval_run_id: Optional[int]) -> dict[str, Any]:
    """AR4 gate: in 'require' mode a fresh, passing eval run on this draft is
    mandatory; in 'warn' mode missing/failed evidence is recorded loudly."""
    from app.eval.promotion_evidence import build_promotion_evidence, resolve_enforcement_mode

    mode = resolve_enforcement_mode()
    warnings: list[str] = []
    eval_run = None
    if eval_run_id is not None:
        eval_run = get_eval_run(eval_run_id)
        if not eval_run:
            raise HTTPException(status_code=404, detail=f"Eval run {eval_run_id} not found")
        if eval_run.get("draft_id") != int(draft["id"]):
            raise HTTPException(
                status_code=422,
                detail={"error": "eval_run_draft_mismatch", "message": f"Eval run {eval_run_id} was not produced from draft {draft['id']}."},
            )
        if _parse_event_timestamp(eval_run["created_at"]) < _parse_event_timestamp(draft["updated_at"]):
            if mode == "require":
                raise HTTPException(
                    status_code=422,
                    detail={"error": "stale_eval_run", "message": "The draft changed after this eval run; re-run evaluation on the current draft."},
                )
            warnings.append("promoted_with_stale_eval_run")
        if eval_run["gate_status"] != "pass":
            if mode == "require":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "eval_gate_failed",
                        "message": "Candidate failed the eval gate and cannot be promoted in require mode.",
                        "gate_aggregates": eval_run["gate_aggregates"],
                        "thresholds": eval_run["thresholds"],
                    },
                )
            warnings.append("promoted_with_failed_eval_gate")
    else:
        if mode == "require":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "eval_evidence_required",
                    "message": "Promotion requires an eval-pack run on this draft (POST /admin/tuning/eval-runs).",
                },
            )
        warnings.append("promoted_without_eval")
    return build_promotion_evidence(eval_run=eval_run, enforcement_mode=mode, warnings=warnings)


@router.post("/tuning/promote")
def promote_tuning_candidate(body: TuningPromotionRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="tuning.promote")
    draft = get_candidate_draft(body.draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft {body.draft_id} not found")
    eval_evidence = _resolve_promotion_eval_evidence(draft=draft, eval_run_id=body.eval_run_id)
    live = get_live_configuration()
    live_embedding = str((live.get("selected_profiles") or {}).get("embedding") or "")
    candidate_embedding = str((draft.get("selected_profiles") or {}).get("embedding") or "")
    if candidate_embedding and live_embedding and candidate_embedding != live_embedding and body.embedding_experiment_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "embedding_experiment_required",
                "message": "Embedding changes require a locked 5-file experiment or all-file reindex confirmation before promotion.",
            },
        )
    try:
        result = promote_candidate_to_live(
            draft_id=body.draft_id,
            promotion_note=body.promotion_note,
            actor=actor,
            eval_evidence=eval_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    for profile_type in PROFILE_TYPES_FOR_TUNING:
        invalidate_cache(profile_type)
    bump_cache_revision(scope_type="profile", reason=f"tuning_promote:{body.draft_id}")
    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.promote",
        resource_type="tuning_config",
        resource_id=str(body.draft_id),
        resource_name=draft.get("name"),
        before_json=_redact_secrets(result.get("previous_live_configuration")),
        after_json=_redact_secrets(result.get("live_configuration")),
        event_json={
            "promotion_note": body.promotion_note,
            "embedding_experiment_id": body.embedding_experiment_id,
            "eval_evidence": eval_evidence,
            **approval,
        },
        actor=actor,
    )
    result["eval_evidence"] = eval_evidence
    return _redact_secrets(result)


@router.post("/tuning/rollback")
def rollback_tuning_candidate(body: TuningRollbackRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="tuning.rollback")
    # AR4: rollbacks are never blocked on eval (they are the escape hatch), but
    # the eval evidence that justified the rollback is linked when provided.
    eval_evidence: dict[str, Any] = {}
    if body.eval_run_id is not None:
        eval_run = get_eval_run(body.eval_run_id)
        if not eval_run:
            raise HTTPException(status_code=404, detail=f"Eval run {body.eval_run_id} not found")
        from app.eval.promotion_evidence import resolve_enforcement_mode

        eval_evidence = {
            "enforcement_mode": resolve_enforcement_mode(),
            "warnings": [],
            "eval_run_id": eval_run["id"],
            "gate_status": eval_run["gate_status"],
            "gate_aggregates": eval_run["gate_aggregates"],
            "thresholds": eval_run["thresholds"],
        }
    try:
        result = rollback_to_version(
            version_label=body.version_label,
            reason=body.reason,
            actor=actor,
            eval_evidence=eval_evidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for profile_type in PROFILE_TYPES_FOR_TUNING:
        invalidate_cache(profile_type)
    bump_cache_revision(scope_type="profile", reason=f"tuning_rollback:{body.version_label}")
    insert_admin_audit_event(
        event_type="tuning",
        action="tuning.rollback",
        resource_type="tuning_config",
        resource_id=body.version_label,
        resource_name=body.version_label,
        before_json=_redact_secrets(result.get("previous_live_configuration")),
        after_json=_redact_secrets(result.get("live_configuration")),
        event_json={"reason": body.reason, "eval_evidence": eval_evidence, **approval},
        actor=actor,
    )
    result["eval_evidence"] = eval_evidence
    return _redact_secrets(result)


def _warm_model(model_type: str, model_name: str) -> dict[str, Any]:
    start = time.time()
    try:
        if model_type == "embedding":
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name)
            dimension = model.get_sentence_embedding_dimension()
            metadata = {"dimension": dimension}
        else:
            from sentence_transformers import CrossEncoder

            CrossEncoder(model_name)
            metadata = {}
        return record_model_warmup(
            model_type=model_type,
            model_name=model_name,
            status="completed",
            latency_ms=int((time.time() - start) * 1000),
            error_message=None,
            metadata_json=metadata,
        )
    except Exception as exc:
        return record_model_warmup(
            model_type=model_type,
            model_name=model_name,
            status="failed",
            latency_ms=int((time.time() - start) * 1000),
            error_message=str(exc),
            metadata_json={},
        )


def _approved_warmup_models(model_type: str) -> set[str]:
    profile_type = "embedding" if model_type == "embedding" else "reranker"
    models: set[str] = set()
    for row in list_approved_registry_profiles(profile_type):
        config = row.get("config") or {}
        if config.get("model"):
            models.add(str(config["model"]))
        models.add(str(row.get("name") or ""))
    return {item for item in models if item}


@router.post("/tuning/warmup")
def warm_tuning_models(body: WarmupRequest, request: Request, _rate_limit: None = Depends(rate_limit_admin_expensive)):
    actor = get_current_user()
    require_high_impact_approval(request=request, actor=actor, action="tuning.warmup")
    results = []
    for model_name in body.embeddings:
        if settings.APPROVED_MODEL_WARMUP_ONLY and model_name not in _approved_warmup_models("embedding"):
            raise HTTPException(status_code=422, detail={"error": "model_not_approved", "model_name": model_name})
        results.append(_warm_model("embedding", model_name))
    for model_name in body.rerankers:
        if settings.APPROVED_MODEL_WARMUP_ONLY and model_name not in _approved_warmup_models("reranker"):
            raise HTTPException(status_code=422, detail={"error": "model_not_approved", "model_name": model_name})
        results.append(_warm_model("reranker", model_name))
    return {"warmup_results": results}


@router.get("/tuning/warmup")
def get_tuning_model_warmups():
    return {"warmup_results": list_model_warmups(limit=100)}


@router.get("/semantic-cache")
def get_semantic_cache_health():
    return {
        "cache": cache_health(),
        "policies": list_semantic_cache_policies(),
        "metrics": semantic_cache_policy_metrics(),
    }


def _cache_policy_config(body: SemanticCachePolicyRequest) -> dict[str, Any]:
    return {
        "enabled": body.enabled,
        "match_mode": body.match_mode,
        "similarity_threshold": body.similarity_threshold,
        "ttl_seconds": body.ttl_seconds,
        "max_active_entries": body.max_active_entries,
        "allow_corpora": body.allow_corpora,
        "deny_corpora": body.deny_corpora,
        "allow_groups": body.allow_groups,
        "deny_groups": body.deny_groups,
        "allow_questions": body.allow_questions,
        "deny_questions": body.deny_questions,
    }


@router.get("/semantic-cache/policies")
def get_semantic_cache_policies():
    return {
        "global_default": "off",
        "policies": list_semantic_cache_policies(),
        "metrics": semantic_cache_policy_metrics(),
    }


@router.post("/semantic-cache/policies")
def create_semantic_cache_policy_endpoint(body: SemanticCachePolicyRequest):
    actor = get_current_user()
    try:
        policy = create_semantic_cache_policy(
            name=body.name,
            justification=body.justification,
            owner=body.owner,
            review_at=body.review_at,
            config=_cache_policy_config(body),
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.create",
        resource_type="semantic_cache_policy",
        resource_id=str(policy["id"]),
        resource_name=policy["name"],
        after_json=policy,
        actor=actor,
    )
    return {"policy": policy}


@router.patch("/semantic-cache/policies/{policy_id}")
def patch_semantic_cache_policy_endpoint(policy_id: int, body: SemanticCachePolicyRequest):
    actor = get_current_user()
    before = get_semantic_cache_policy(policy_id)
    if not before:
        raise HTTPException(status_code=404, detail=f"Cache policy {policy_id} not found")
    try:
        policy = update_semantic_cache_policy(
            policy_id,
            name=body.name,
            justification=body.justification,
            owner=body.owner,
            review_at=body.review_at,
            config=_cache_policy_config(body),
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.update",
        resource_type="semantic_cache_policy",
        resource_id=str(policy_id),
        resource_name=policy["name"],
        before_json=before,
        after_json=policy,
        actor=actor,
    )
    return {"policy": policy}


@router.post("/semantic-cache/policies/{policy_id}/check")
def check_semantic_cache_policy_endpoint(policy_id: int, body: SemanticCachePolicyCheckRequest):
    actor = get_current_user()
    policy = get_semantic_cache_policy(policy_id)
    if not policy or not policy.get("draft_version"):
        raise HTTPException(status_code=404, detail=f"Cache policy {policy_id} has no draft version")
    draft = dict(policy["draft_version"])
    namespace = f"sandbox:{policy_id}:{draft['id']}:{int(time.time())}"
    from app.core_rag.answering import AskRequest, perform_ask

    request = AskRequest(question=body.question, mode=body.mode, bypass_cache=False)
    cold = perform_ask(request, policy_override=draft, cache_namespace_override=namespace)
    warm = perform_ask(request, policy_override=draft, cache_namespace_override=namespace)
    refresh = perform_ask(
        AskRequest(
            question=body.question,
            mode=body.mode,
            bypass_cache=True,
            refresh_cache_entry_id=(cold.cache_info or {}).get("entry_id"),
        ),
        policy_override=draft,
        cache_namespace_override=namespace,
    )
    invalidated = invalidate_semantic_cache(reason="sandbox_policy_check_complete", cache_namespace=namespace)
    result = {
        "namespace": namespace,
        "cold": cold.model_dump(),
        "warm": warm.model_dump(),
        "refresh": refresh.model_dump(),
        "invalidated_entries": invalidated,
    }
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.check",
        resource_type="semantic_cache_policy",
        resource_id=str(policy_id),
        resource_name=policy["name"],
        after_json={"question": body.question, "result": result},
        actor=actor,
    )
    return result


@router.post("/semantic-cache/policies/{policy_id}/activate")
def activate_semantic_cache_policy_endpoint(policy_id: int, body: SemanticCachePolicyActivationRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="semantic_cache.policy.activate")
    before = get_semantic_cache_policy(policy_id)
    try:
        policy = activate_semantic_cache_policy(policy_id, confirmation=body.confirmation, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.activate",
        resource_type="semantic_cache_policy",
        resource_id=str(policy_id),
        resource_name=policy["name"],
        before_json=before,
        after_json=policy,
        event_json=approval,
        actor=actor,
    )
    return {"policy": policy}


@router.post("/semantic-cache/policies/{policy_id}/disable")
def disable_semantic_cache_policy_endpoint(policy_id: int, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="semantic_cache.policy.disable")
    before = get_semantic_cache_policy(policy_id)
    try:
        policy = disable_semantic_cache_policy(policy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    namespace = str(((before or {}).get("active_version") or {}).get("cache_namespace") or "")
    if namespace:
        invalidate_semantic_cache(reason="policy_disabled", cache_namespace=namespace)
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.disable",
        resource_type="semantic_cache_policy",
        resource_id=str(policy_id),
        resource_name=policy["name"],
        before_json=before,
        after_json=policy,
        event_json=approval,
        actor=actor,
    )
    return {"policy": policy}


@router.post("/semantic-cache/policies/{policy_id}/rollback")
def rollback_semantic_cache_policy_endpoint(policy_id: int, body: SemanticCachePolicyRollbackRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="semantic_cache.policy.rollback")
    before = get_semantic_cache_policy(policy_id)
    try:
        policy = rollback_semantic_cache_policy(policy_id, version_id=body.version_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.policy.rollback",
        resource_type="semantic_cache_policy",
        resource_id=str(policy_id),
        resource_name=policy["name"],
        before_json=before,
        after_json=policy,
        event_json=approval,
        actor=actor,
    )
    return {"policy": policy}


@router.get("/semantic-cache/metrics")
def get_semantic_cache_policy_metrics():
    return {"metrics": semantic_cache_policy_metrics()}


@router.post("/semantic-cache/clear")
def clear_semantic_cache(request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="semantic_cache.clear")
    active_policy = get_active_semantic_cache_policy_version()
    namespace = str((active_policy or {}).get("cache_namespace") or "")
    invalidated = invalidate_semantic_cache(reason="admin_clear", cache_namespace=namespace) if namespace else 0
    insert_admin_audit_event(
        event_type="cache",
        action="semantic_cache.clear",
        resource_type="semantic_cache",
        resource_id=namespace or "none",
        after_json={"invalidated": invalidated, "cache_namespace": namespace or None},
        event_json=approval,
        actor=actor,
    )
    return {"status": "cleared", "invalidated": invalidated}


@router.get("/query-mining")
def get_query_mining():
    return {
        "query_events": list_query_events(limit=200),
        "clusters": list_failure_clusters(limit=100),
        "derived_eval_packs": list_derived_eval_packs(limit=100),
    }


@router.post("/retention/run")
def run_admin_retention(request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="retention.run")
    result = run_retention_policy()
    insert_admin_audit_event(
        event_type="retention",
        action="retention.run",
        resource_type="retention_policy",
        resource_id="default",
        after_json=result,
        event_json=approval,
        actor=actor,
    )
    return {"status": "completed", "result": result}


@router.post("/query-mining/clusters/build")
def build_query_mining_clusters():
    clusters = build_failure_clusters(limit=300)
    return {"clusters": clusters}


@router.patch("/query-mining/clusters/{cluster_id}")
def patch_query_mining_cluster(cluster_id: int, body: QueryClusterAnnotationRequest):
    try:
        cluster = annotate_cluster(cluster_id, body.annotation_json)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"cluster": cluster}


@router.post("/query-mining/eval-packs")
def create_query_mining_eval_pack(body: DerivedEvalPackRequest):
    if not body.cluster_ids:
        raise HTTPException(status_code=400, detail="At least one cluster id is required")
    pack = create_eval_pack_from_clusters(name=body.name, cluster_ids=body.cluster_ids, actor=get_current_user())
    return {"eval_pack": pack}


@router.get("/governance")
def get_governance_controls():
    return {"risk_signals": list_risk_signals(limit=200), "restrictions": list_restrictions(limit=200)}


@router.post("/governance/restrictions")
def create_governance_restriction(body: GovernanceRestrictionRequest):
    actor = get_current_user()
    restriction = create_restriction(
        user_external_user_id=body.user_external_user_id,
        user_email=body.user_email,
        restriction_type=body.restriction_type,
        reason=body.reason,
        duration_hours=body.duration_hours,
        actor=actor,
    )
    insert_admin_audit_event(
        event_type="governance",
        action="governance.restriction.create",
        resource_type="user_governance_restriction",
        resource_id=str(restriction["id"]),
        resource_name=body.user_email or body.user_external_user_id,
        after_json=restriction,
        actor=actor,
    )
    return {"restriction": restriction}


@router.post("/governance/restrictions/{restriction_id}/lift")
def lift_governance_restriction(restriction_id: int, body: GovernanceRestrictionLiftRequest):
    actor = get_current_user()
    try:
        restriction = lift_restriction(restriction_id, reason=body.reason, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    insert_admin_audit_event(
        event_type="governance",
        action="governance.restriction.lift",
        resource_type="user_governance_restriction",
        resource_id=str(restriction_id),
        resource_name=restriction.get("user_email") or restriction.get("user_external_user_id"),
        after_json=restriction,
        actor=actor,
    )
    return {"restriction": restriction}


@router.get("/overview")
def get_admin_overview():
    corpora = list_corpora()
    sources = list_sources()
    ingestion_jobs, queue_summary = _ingestion_queue_payloads()
    source_lookup = {
        int(row.id): {
            "file_name": row.file_name,
            "corpus_name": (row.source_metadata_json or {}).get("corpus"),
        }
        for row in sources
    }
    enrichment_jobs = [_job_payload(row, kind="enrichment", source_lookup=source_lookup) for row in list_enrichment_jobs()]
    traces = [_trace_payload(row) for row in list_traces(limit=6, offset=0)]
    reports = [_report_summary(kind, path) for kind, path in _EVAL_REPORT_FILES.items()]
    audit_events = list_admin_audit_events(limit=5)
    latest_report = next((report for report in reports if report["exists"]), None)
    priority_requests = [request for request in _latest_priority_requests_by_job().values() if request.status in {"submitted", "under_review"}]
    pending_approvals = [request for request in list_approval_requests(limit=200) if request.status == "pending"]
    failed_queries = top_failed_queries(limit=5)

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
    if priority_requests:
        alerts.append(
            {
                "tone": "warning",
                "title": "Priority requests are waiting for review",
                "body": f"{len(priority_requests)} user-submitted indexing priority request(s) need operator attention.",
                "href": "/console/admin/jobs",
            }
        )
    if pending_approvals:
        alerts.append(
            {
                "tone": "warning",
                "title": "Approvals are waiting",
                "body": f"{len(pending_approvals)} sensitive output or tool action approval request(s) need review.",
                "href": "/console/admin/actions",
            }
        )
    if failed_queries:
        alerts.append(
            {
                "tone": "info",
                "title": "Missing-evidence feedback captured",
                "body": f"{len(failed_queries)} query pattern(s) have missing-evidence or not-helpful feedback.",
                "href": "/console/admin/actions",
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
            "pending_priority_request_count": len(priority_requests),
            "pending_approval_count": len(pending_approvals),
            "failed_query_pattern_count": len(failed_queries),
        },
        "alerts": alerts,
        "recent_traces": traces[:4],
        "recent_audit_events": audit_events,
        "reports": reports,
        "queue_summary": queue_summary,
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
    bump_cache_revision(scope_type="corpus", scope_key=body.name.strip().lower(), reason="corpus_created")
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
    bump_cache_revision(scope_type="corpus", scope_key=target_name.lower(), reason="corpus_updated")
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
        bump_cache_revision(scope_type="source", scope_key=str(source_id), reason="corpus_assignment")
        bump_cache_revision(scope_type="corpus", scope_key=corpus_name.lower(), reason="source_assigned")
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
def update_source(source_id: int, body: SourceUpdateRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="source.update")
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
    bump_cache_revision(scope_type="source", scope_key=str(source_id), reason="source_admin_update")
    bump_cache_revision(scope_type="content", reason="source_admin_update")
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
        event_json=approval,
        actor=actor,
    )
    return {"status": "ok", "source": _source_payload_with_acl(updated or row, acl_map)}


DOWNLOAD_WARN_BYTES = 25 * 1024 * 1024  # 25 MB: above this the console warns before downloading


@router.get("/sources/{source_id}/download-info")
def source_download_info(source_id: int):
    """AR20/console: metadata for the download affordance — name, size, and
    whether the console should warn before downloading a large file."""
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": f"Source {source_id} not found"})
    size = int(getattr(row, "file_size_bytes", 0) or 0)
    return {
        "source_id": source_id,
        "file_name": row.file_name,
        "source_type": row.source_type,
        "file_size_bytes": size,
        "warn_threshold_bytes": DOWNLOAD_WARN_BYTES,
        "too_large_warning": size > DOWNLOAD_WARN_BYTES,
    }


@router.get("/sources/{source_id}/download")
def download_source_file(source_id: int):
    """Admin-scoped download of a source's original file so an operator can read
    it on their machine before acting. db_row sources stream their text."""
    from fastapi.responses import FileResponse

    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": f"Source {source_id} not found"})
    if row.source_type == "db_row":
        from app.db.repo_source_parts import list_source_parts

        body = "\n\n".join((part.content_text or "") for part in list_source_parts(source_id)).strip()
        return PlainTextResponse(body or row.file_name, media_type="text/plain")
    from app.ingestion.jobs import _source_file_absolute_path

    absolute_path = _source_file_absolute_path(row.storage_path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail={"error": "source_file_not_found", "source_id": source_id, "storage_path": row.storage_path})
    media_type = getattr(row, "mime_type", None) or ("application/pdf" if row.source_type == "pdf" else "application/octet-stream")
    return FileResponse(path=str(absolute_path), media_type=media_type, filename=row.file_name)


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
    invalidate_semantic_cache(reason=f"source_reindex:{source_id}")
    bump_cache_revision(scope_type="source", scope_key=str(source_id), reason="source_reindex")
    bump_cache_revision(scope_type="content", reason="source_reindex")
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
    bump_cache_revision(scope_type="source", scope_key=str(source_id), reason="source_enrichment")
    bump_cache_revision(scope_type="content", reason="source_enrichment")
    return payload


@router.get("/jobs")
def get_jobs(source_id: Optional[int] = None):
    source_lookup = {
        int(row.id): {
            "file_name": row.file_name,
            "corpus_name": (row.source_metadata_json or {}).get("corpus"),
        }
        for row in list_sources()
    }
    ingestion_jobs, queue_summary = _ingestion_queue_payloads(source_id=source_id)
    return {
        "ingestion_jobs": ingestion_jobs,
        "enrichment_jobs": [_job_payload(row, kind="enrichment", source_lookup=source_lookup) for row in list_enrichment_jobs(source_id=source_id)],
        "queue_summary": queue_summary,
        "priority_requests": [priority_request_payload(request) for request in list_priority_requests(limit=100) if priority_request_payload(request)],
    }


@router.get("/jobs/ingestion/{job_id}")
def get_ingestion_job_status(job_id: int):
    payload = next((job for job in _ingestion_queue_payloads()[0] if int(job["id"]) == job_id), None)
    if payload is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    return payload


@router.post("/jobs/ingestion/{job_id}/priority")
def update_ingestion_job_priority(job_id: int, body: QueuePriorityUpdateRequest):
    row = get_ingestion_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    if str(row.status).lower() not in {"queued", "paused"}:
        raise HTTPException(status_code=400, detail={"error": "priority_change_not_supported", "message": "Only waiting jobs can be reprioritized safely in this environment."})
    impact = _preview_priority_change(job_id, body.priority)
    if body.preview_only:
        return {"status": "preview", "job_id": job_id, "priority": body.priority, "impact": impact}
    update_ingestion_job(job_id, priority=body.priority)
    insert_admin_audit_event(
        event_type="queue",
        action="queue.priority.updated",
        resource_type="ingestion_job",
        resource_id=str(job_id),
        resource_name=str(row.source_id or job_id),
        source_id=row.source_id,
        job_kind="ingestion",
        job_id=job_id,
        before_json={"priority": row.priority},
        after_json={"priority": body.priority},
        event_json={"reason": body.reason, "impact": impact},
    )
    poke_ingestion_queue()
    return {"status": "updated", "job": get_ingestion_job_status(job_id), "impact": impact}


@router.post("/jobs/ingestion/{job_id}/priority-request/{request_id}")
def review_ingestion_priority_request(job_id: int, request_id: int, body: QueuePriorityDecisionRequest):
    row = get_ingestion_job(job_id)
    request = get_priority_request(request_id)
    if row is None or request is None or int(request.job_id) != job_id:
        raise HTTPException(status_code=404, detail={"error": "priority_request_not_found", "job_id": job_id, "request_id": request_id})
    before_status = request.status
    update_priority_request_status(request_id, status=body.decision, review_reason=body.reason)
    impact = None
    if body.decision == "approved" and str(row.status).lower() in {"queued", "paused"}:
        impact = _preview_priority_change(job_id, int(request.requested_priority))
        update_ingestion_job(job_id, priority=int(request.requested_priority))
        poke_ingestion_queue()
    insert_admin_audit_event(
        event_type="queue",
        action="queue.priority_request.reviewed",
        resource_type="priority_request",
        resource_id=str(request_id),
        resource_name=str(row.source_id or job_id),
        source_id=row.source_id,
        job_kind="ingestion",
        job_id=job_id,
        before_json={"status": before_status},
        after_json={"status": body.decision},
        event_json={"reason": body.reason, "impact": impact},
    )
    return {
        "status": "updated",
        "request": priority_request_payload(get_priority_request(request_id)),
        "job": get_ingestion_job_status(job_id),
        "impact": impact,
    }


@router.post("/jobs/ingestion/{job_id}/control")
def control_ingestion_job(job_id: int, body: QueueControlRequest):
    row = get_ingestion_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "job_not_found", "job_id": job_id})
    action = body.action
    normalized_status = str(row.status).lower()
    if normalized_status in {"processing", "running"} and action in {"pause", "cancel", "requeue", "retry"}:
        raise HTTPException(status_code=400, detail={"error": "running_job_not_supported", "message": "Running jobs cannot be safely reordered or interrupted in this environment. Wait for completion, then retry or requeue if needed."})

    result: dict[str, Any]
    if action == "pause":
        if normalized_status != "queued":
            raise HTTPException(status_code=400, detail={"error": "pause_not_allowed", "message": "Only queued jobs can be paused."})
        update_ingestion_job(job_id, status="paused", stage="paused")
        if row.source_id is not None:
            update_source_status(row.source_id, ingestion_status="paused")
        result = {"status": "paused", "job": get_ingestion_job_status(job_id)}
    elif action == "resume":
        if normalized_status != "paused":
            raise HTTPException(status_code=400, detail={"error": "resume_not_allowed", "message": "Only paused jobs can be resumed."})
        update_ingestion_job(job_id, status="queued", stage="queued")
        if row.source_id is not None:
            update_source_status(row.source_id, ingestion_status="queued")
        poke_ingestion_queue()
        result = {"status": "queued", "job": get_ingestion_job_status(job_id)}
    elif action == "cancel":
        if normalized_status not in {"queued", "paused"}:
            raise HTTPException(status_code=400, detail={"error": "cancel_not_allowed", "message": "Only waiting jobs can be cancelled."})
        update_ingestion_job(job_id, status="cancelled", stage="cancelled", completed_at_now=True)
        if row.source_id is not None:
            update_source_status(row.source_id, ingestion_status="cancelled")
        result = {"status": "cancelled", "job": get_ingestion_job_status(job_id)}
    elif action == "requeue":
        if normalized_status not in {"paused", "cancelled"}:
            raise HTTPException(status_code=400, detail={"error": "requeue_not_allowed", "message": "Only paused or cancelled jobs can be requeued."})
        update_ingestion_job(job_id, status="queued", stage="queued", clear_started_at=True, clear_completed_at=True, error_message="")
        if row.source_id is not None:
            update_source_status(row.source_id, ingestion_status="queued")
        poke_ingestion_queue()
        result = {"status": "queued", "job": get_ingestion_job_status(job_id)}
    else:
        if normalized_status not in {"failed", "cancelled"}:
            raise HTTPException(status_code=400, detail={"error": "retry_not_allowed", "message": "Only failed or cancelled jobs can be retried."})
        if row.source_id is None:
            raise HTTPException(status_code=400, detail={"error": "source_missing", "message": "The source record is required before retrying this job."})
        source = get_source_by_id(row.source_id)
        if source is None:
            raise HTTPException(status_code=404, detail={"error": "source_not_found", "source_id": row.source_id})
        _reset_source_for_reindex(row.source_id)
        new_job_id = create_ingestion_job(
            source_id=row.source_id,
            status="queued",
            stage="queued",
            priority=max(int(row.priority), 120),
            triggered_by="admin_retry",
            owner_external_user_id=row.owner_external_user_id,
            owner_email=row.owner_email,
            owner_display_name=row.owner_display_name,
            job_metadata_json={
                **dict(row.job_metadata_json or {}),
                "retry_of_job_id": row.id,
                "queue_stage_label": "queued",
            },
        )
        poke_ingestion_queue()
        result = {"status": "queued", "job": get_ingestion_job_status(new_job_id), "retry_of_job_id": job_id}

    insert_admin_audit_event(
        event_type="queue",
        action=f"queue.job.{action}",
        resource_type="ingestion_job",
        resource_id=str(job_id),
        resource_name=str(row.source_id or job_id),
        source_id=row.source_id,
        job_kind="ingestion",
        job_id=job_id,
        event_json={"reason": body.reason, "result": result},
    )
    return result


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


@router.post("/access/seed-import")
def import_access_seed_pack(body: AccessSeedImportRequest):
    pack_dir = Path(body.pack_dir).expanduser() if body.pack_dir else DEFAULT_PACK_DIR
    if not pack_dir.exists():
        raise HTTPException(status_code=404, detail={"error": "seed_pack_not_found", "message": f"Seed pack not found: {pack_dir}"})
    summary = seed_enterprise_acl_pack(pack_dir)
    actor = get_current_user()
    insert_admin_audit_event(
        event_type="access",
        action="access.seed_import",
        resource_type="seed_pack",
        resource_id=str(pack_dir),
        resource_name=pack_dir.name,
        actor=actor,
        after_json=summary,
    )
    return {"status": "ok", "summary": summary, "access": list_access_summary()}


@router.patch("/access/users/{external_user_id}/memberships")
def update_user_memberships(external_user_id: str, body: UserMembershipUpdateRequest, request: Request):
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="access.user_memberships.update")
    replace_user_memberships(external_user_id=external_user_id, group_names=body.group_names)
    insert_admin_audit_event(
        event_type="access",
        action="access.user_memberships.update",
        resource_type="auth_user",
        resource_id=external_user_id,
        resource_name=external_user_id,
        actor=actor,
        after_json={"group_names": body.group_names},
        event_json=approval,
    )
    return {"status": "ok", "user": explain_user_access(external_user_id)}


@router.patch("/access/sources/{source_id}/acl")
def update_source_acl_assignments(source_id: int, body: SourceAclUpdateRequest, request: Request):
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": f"Source {source_id} not found"})
    actor = get_current_user()
    approval = require_high_impact_approval(request=request, actor=actor, action="access.source_acl.update")
    replace_source_acl(source_id=source_id, group_names=body.group_names)
    insert_admin_audit_event(
        event_type="access",
        action="access.source_acl.update",
        resource_type="source",
        resource_id=str(source_id),
        resource_name=row.file_name,
        source_id=source_id,
        actor=actor,
        after_json={"group_names": body.group_names},
        event_json=approval,
    )
    return {"status": "ok", "source": explain_source_access(source_id)}


@router.patch("/access/sources/{source_id}/contacts")
def update_source_contacts(source_id: int, body: SourceContactsUpdateRequest):
    row = get_source_by_id(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": f"Source {source_id} not found"})
    upsert_source_access_contacts(source_id, [contact.model_dump() for contact in body.contacts])
    actor = get_current_user()
    insert_admin_audit_event(
        event_type="access",
        action="access.source_contacts.update",
        resource_type="source",
        resource_id=str(source_id),
        resource_name=row.file_name,
        source_id=source_id,
        actor=actor,
        after_json={"contacts": [contact.model_dump() for contact in body.contacts]},
    )
    return {"status": "ok", "source": explain_source_access(source_id)}


@router.post("/access/bulk/assign-group-to-sources")
def bulk_assign_group_to_sources(body: BulkGroupAssignmentRequest):
    updated: list[int] = []
    acl_map = list_source_acl_map()
    for source_id in body.source_ids:
        merged = sorted({*(acl_map.get(int(source_id), [])), body.group_name.strip()})
        replace_source_acl(source_id=source_id, group_names=merged)
        updated.append(int(source_id))
    actor = get_current_user()
    insert_admin_audit_event(
        event_type="access",
        action="access.bulk_assign_group_to_sources",
        resource_type="group",
        resource_id=body.group_name,
        resource_name=body.group_name,
        actor=actor,
        after_json={"source_ids": updated},
    )
    return {"status": "ok", "group_name": body.group_name, "source_ids": updated}


@router.post("/access/bulk/assign-sources-to-group")
def bulk_assign_sources_to_group(body: BulkSourceAssignmentRequest):
    row = get_source_by_id(body.source_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": f"Source {body.source_id} not found"})
    replace_source_acl(source_id=body.source_id, group_names=body.group_names)
    actor = get_current_user()
    insert_admin_audit_event(
        event_type="access",
        action="access.bulk_assign_sources_to_group",
        resource_type="source",
        resource_id=str(body.source_id),
        resource_name=row.file_name,
        source_id=body.source_id,
        actor=actor,
        after_json={"group_names": body.group_names},
    )
    return {"status": "ok", "source": explain_source_access(body.source_id)}


@router.get("/access/explain/source/{source_id}")
def get_source_access_explanation(source_id: int):
    try:
        return explain_source_access(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "source_not_found", "message": str(exc)}) from exc


@router.get("/access/explain/user/{external_user_id}")
def get_user_access_explanation(external_user_id: str):
    try:
        return explain_user_access(external_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "user_not_found", "message": str(exc)}) from exc


@router.get("/audit-log")
def get_admin_audit_log(
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    outcome: Optional[str] = None,
    actor_external_user_id: Optional[str] = None,
    actor_query: Optional[str] = None,
    source_id: Optional[int] = None,
    job_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
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
            actor_query=actor_query,
            source_id=source_id,
            job_id=job_id,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    }


@router.get("/audit-log/export")
def export_admin_audit_log(
    request: Request,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    outcome: Optional[str] = None,
    actor_external_user_id: Optional[str] = None,
    actor_query: Optional[str] = None,
    source_id: Optional[int] = None,
    job_id: Optional[int] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
):
    actor = get_current_user()
    require_high_impact_approval(request=request, actor=actor, action="audit.export")
    rows = list_admin_audit_events(
        limit=500,
        offset=0,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        actor_external_user_id=actor_external_user_id,
        actor_query=actor_query,
        source_id=source_id,
        job_id=job_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    body = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
    headers = {"Content-Disposition": 'attachment; filename="admin-audit-log.jsonl"'}
    return PlainTextResponse(content=body, headers=headers, media_type="application/jsonl")


@router.get("/audit-log/integrity")
def get_admin_audit_integrity():
    return {"integrity": verify_admin_audit_integrity()}
