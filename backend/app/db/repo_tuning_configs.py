import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.repo_jobs import create_ingestion_job
from app.db.repo_profiles import (
    PROFILE_TYPES_FOR_TUNING,
    get_active_profile_map,
    get_profile,
    is_registry_approved_profile,
    set_active_profile,
    upsert_profile,
)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _normalize_row(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key in ("selected_profiles_json", "resolved_config_json", "lineage_json"):
        payload[key] = payload.get(key) or {}
    return {key: _jsonable(value) for key, value in payload.items()}


def build_resolved_profile_bundle(selected_profiles: dict[str, str], retrieval_override_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for profile_type in PROFILE_TYPES_FOR_TUNING:
        profile_name = selected_profiles.get(profile_type)
        if not profile_name:
            raise ValueError(f"Missing selected profile for '{profile_type}'")
        profile = get_profile(profile_type, profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' of type '{profile_type}' not found")
        config = dict(profile["config_json"] or {})
        if profile_type == "retrieval" and retrieval_override_config:
            config.update(retrieval_override_config)
        resolved[profile_type] = {
            "profile_name": profile_name,
            "config": config,
            "updated_at": _jsonable(profile["updated_at"]),
        }
    return resolved


def sync_live_configuration_record() -> dict[str, Any]:
    selected_profiles = get_active_profile_map(list(PROFILE_TYPES_FOR_TUNING))
    if not selected_profiles:
        return {}
    resolved = build_resolved_profile_bundle(selected_profiles)
    sql = text(
        """
        INSERT INTO tuning_config_versions (
            version_label, config_kind, status, name, description,
            selected_profiles_json, resolved_config_json, lineage_json,
            created_by_external_user_id, created_by_email, updated_at
        )
        VALUES (
            'live-current', 'live', 'live', 'Production Live Configuration',
            'Current production-active retrieval and model configuration.',
            CAST(:selected_profiles AS jsonb), CAST(:resolved_config AS jsonb), CAST(:lineage_json AS jsonb),
            NULL, NULL, now()
        )
        ON CONFLICT (version_label)
        DO UPDATE SET
            config_kind = EXCLUDED.config_kind,
            status = EXCLUDED.status,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            selected_profiles_json = EXCLUDED.selected_profiles_json,
            resolved_config_json = EXCLUDED.resolved_config_json,
            lineage_json = EXCLUDED.lineage_json,
            updated_at = now()
        RETURNING id, version_label, config_kind, status, name, description,
                  selected_profiles_json, resolved_config_json, lineage_json,
                  created_by_external_user_id, created_by_email, created_at, updated_at
        """
    )
    lineage = {"source": "active_profiles", "profile_types": list(PROFILE_TYPES_FOR_TUNING)}
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "selected_profiles": json.dumps(selected_profiles),
                "resolved_config": json.dumps(resolved),
                "lineage_json": json.dumps(lineage),
            },
        ).mappings().one()
    return _normalize_row(row)


def get_live_configuration() -> dict[str, Any]:
    live = sync_live_configuration_record()
    if not live:
        return {}
    live["selected_profiles"] = live.pop("selected_profiles_json", {})
    live["resolved_config"] = live.pop("resolved_config_json", {})
    live["lineage"] = live.pop("lineage_json", {})
    return live


def list_candidate_drafts() -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT id, version_label, config_kind, status, name, description,
               selected_profiles_json, resolved_config_json, lineage_json,
               created_by_external_user_id, created_by_email, created_at, updated_at
        FROM tuning_config_versions
        WHERE config_kind = 'candidate'
        ORDER BY updated_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    drafts: list[dict[str, Any]] = []
    for row in rows:
        payload = _normalize_row(row)
        payload["selected_profiles"] = payload.pop("selected_profiles_json", {})
        payload["resolved_config"] = payload.pop("resolved_config_json", {})
        payload["lineage"] = payload.pop("lineage_json", {})
        drafts.append(payload)
    return drafts


def _validated_selected_profiles(selected_profiles: dict[str, str]) -> dict[str, str]:
    normalized = {str(key): str(value) for key, value in selected_profiles.items() if value}
    missing = [profile_type for profile_type in PROFILE_TYPES_FOR_TUNING if not normalized.get(profile_type)]
    if missing:
        raise ValueError(f"Missing profile selections for: {', '.join(missing)}")
    active_profiles = get_active_profile_map(list(PROFILE_TYPES_FOR_TUNING))
    for profile_type in ("embedding", "reranker", "llm"):
        profile_name = normalized[profile_type]
        if profile_name == active_profiles.get(profile_type):
            continue
        if not is_registry_approved_profile(profile_type, profile_name):
            raise ValueError(f"Profile '{profile_name}' of type '{profile_type}' is not an approved registry option")
    for profile_type in ("retrieval",):
        profile_name = normalized[profile_type]
        if not get_profile(profile_type, profile_name):
            raise ValueError(f"Profile '{profile_name}' of type '{profile_type}' not found")
    return normalized


def _validated_draft_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("Draft name is required")
    return normalized


def create_candidate_draft(
    *,
    name: str,
    description: str,
    selected_profiles: dict[str, str],
    retrieval_override_config: Optional[dict[str, Any]] = None,
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    normalized = _validated_selected_profiles(selected_profiles)
    resolved = build_resolved_profile_bundle(normalized, retrieval_override_config)
    live = get_live_configuration()
    draft_name = _validated_draft_name(name)
    sql = text(
        """
        INSERT INTO tuning_config_versions (
            version_label, config_kind, status, name, description,
            selected_profiles_json, resolved_config_json, lineage_json,
            created_by_external_user_id, created_by_email
        )
        VALUES (
            :version_label, 'candidate', 'draft', :name, :description,
            CAST(:selected_profiles AS jsonb), CAST(:resolved_config AS jsonb), CAST(:lineage_json AS jsonb),
            :created_by_external_user_id, :created_by_email
        )
        RETURNING id, version_label, config_kind, status, name, description,
                  selected_profiles_json, resolved_config_json, lineage_json,
                  created_by_external_user_id, created_by_email, created_at, updated_at
        """
    )
    with engine.begin() as conn:
        next_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM tuning_config_versions")).scalar_one()
        version_label = f"draft-{int(next_id)}"
        row = conn.execute(
            sql,
            {
                "version_label": version_label,
                "name": draft_name,
                "description": description.strip(),
                "selected_profiles": json.dumps(normalized),
                "resolved_config": json.dumps(resolved),
                "lineage_json": json.dumps(
                    {
                        "basis_live_version_label": live.get("version_label"),
                        "basis_live_updated_at": live.get("updated_at"),
                        "retrieval_override_config": retrieval_override_config or {},
                    }
                ),
                "created_by_external_user_id": actor.user_id if actor else None,
                "created_by_email": actor.email if actor else None,
            },
        ).mappings().one()
    payload = _normalize_row(row)
    payload["selected_profiles"] = payload.pop("selected_profiles_json", {})
    payload["resolved_config"] = payload.pop("resolved_config_json", {})
    payload["lineage"] = payload.pop("lineage_json", {})
    return payload


def update_candidate_draft(
    draft_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    selected_profiles: Optional[dict[str, str]] = None,
    retrieval_override_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    existing = get_candidate_draft(draft_id)
    if not existing:
        raise ValueError(f"Draft {draft_id} not found")
    normalized = existing["selected_profiles"]
    if selected_profiles is not None:
        normalized = _validated_selected_profiles(selected_profiles)
    lineage = dict(existing.get("lineage") or {})
    if retrieval_override_config is None:
        retrieval_override_config = dict(lineage.get("retrieval_override_config") or {})
    resolved = build_resolved_profile_bundle(normalized, retrieval_override_config)
    draft_name = _validated_draft_name(name if name is not None else existing["name"])
    sql = text(
        """
        UPDATE tuning_config_versions
        SET name = :name,
            description = :description,
            selected_profiles_json = CAST(:selected_profiles AS jsonb),
            resolved_config_json = CAST(:resolved_config AS jsonb),
            lineage_json = CAST(:lineage_json AS jsonb),
            updated_at = now()
        WHERE id = :draft_id AND config_kind = 'candidate'
        RETURNING id, version_label, config_kind, status, name, description,
                  selected_profiles_json, resolved_config_json, lineage_json,
                  created_by_external_user_id, created_by_email, created_at, updated_at
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "draft_id": draft_id,
                "name": draft_name,
                "description": (description if description is not None else existing["description"]).strip(),
                "selected_profiles": json.dumps(normalized),
                "resolved_config": json.dumps(resolved),
                "lineage_json": json.dumps(
                    {
                        **lineage,
                        "retrieval_override_config": retrieval_override_config or {},
                    }
                ),
            },
        ).mappings().first()
    if not row:
        raise ValueError(f"Draft {draft_id} not found")
    payload = _normalize_row(row)
    payload["selected_profiles"] = payload.pop("selected_profiles_json", {})
    payload["resolved_config"] = payload.pop("resolved_config_json", {})
    payload["lineage"] = payload.pop("lineage_json", {})
    return payload


def get_candidate_draft(draft_id: int) -> Optional[dict[str, Any]]:
    sql = text(
        """
        SELECT id, version_label, config_kind, status, name, description,
               selected_profiles_json, resolved_config_json, lineage_json,
               created_by_external_user_id, created_by_email, created_at, updated_at
        FROM tuning_config_versions
        WHERE id = :draft_id AND config_kind = 'candidate'
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"draft_id": draft_id}).mappings().first()
    if not row:
        return None
    payload = _normalize_row(row)
    payload["selected_profiles"] = payload.pop("selected_profiles_json", {})
    payload["resolved_config"] = payload.pop("resolved_config_json", {})
    payload["lineage"] = payload.pop("lineage_json", {})
    return payload


def _promotion_payload(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key in ("selected_profiles_json", "rollback_target_json"):
        payload[key] = payload.get(key) or {}
    return {key: _jsonable(value) for key, value in payload.items()}


def list_tuning_history(limit: int = 50) -> dict[str, Any]:
    live = get_live_configuration()
    with engine.connect() as conn:
        promotions = conn.execute(
            text(
                """
                SELECT id, promoted_config_id, previous_live_version_label, new_live_version_label,
                       action, promotion_note, selected_profiles_json, rollback_target_json,
                       actor_external_user_id, actor_email, created_at
                FROM tuning_promotion_events
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        versions = conn.execute(
            text(
                """
                SELECT id, version_label, config_kind, status, name, description,
                       selected_profiles_json, resolved_config_json, lineage_json,
                       created_by_external_user_id, created_by_email, created_at, updated_at
                FROM tuning_config_versions
                ORDER BY updated_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    normalized_versions = []
    for row in versions:
        item = _normalize_row(row)
        item["selected_profiles"] = item.pop("selected_profiles_json", {})
        item["resolved_config"] = item.pop("resolved_config_json", {})
        item["lineage"] = item.pop("lineage_json", {})
        normalized_versions.append(item)
    return {
        "live_configuration": live,
        "promotion_events": [_promotion_payload(row) for row in promotions],
        "versions": normalized_versions,
    }


def promote_candidate_to_live(
    *,
    draft_id: int,
    promotion_note: str,
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    draft = get_candidate_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft {draft_id} not found")
    live_before = get_live_configuration()
    selected_profiles = dict(draft.get("selected_profiles") or {})
    retrieval_override_config = dict((draft.get("lineage") or {}).get("retrieval_override_config") or {})
    if retrieval_override_config:
        source_retrieval_name = str(selected_profiles.get("retrieval") or "retrieval")
        promoted_retrieval_profile_name = f"{draft.get('version_label', f'draft-{draft_id}')}-retrieval"
        resolved_retrieval = ((draft.get("resolved_config") or {}).get("retrieval") or {}).get("config") or {}
        config_to_promote = dict(resolved_retrieval or retrieval_override_config)
        config_to_promote.setdefault("display_name", f"{draft.get('name', 'Candidate')} retrieval")
        config_to_promote["approval_status"] = "sandbox_promoted"
        config_to_promote["registry_entry"] = False
        upsert_profile("retrieval", promoted_retrieval_profile_name, config_to_promote, is_default=False)
        selected_profiles["retrieval"] = promoted_retrieval_profile_name
        lineage = dict(draft.get("lineage") or {})
        lineage["promoted_retrieval_profile_name"] = promoted_retrieval_profile_name
        lineage["promoted_from_retrieval_profile"] = source_retrieval_name
    else:
        lineage = {
            "source_draft_id": draft_id,
            "source_draft_version_label": draft.get("version_label"),
            "previous_live_version_label": live_before.get("version_label"),
        }
    resolved = build_resolved_profile_bundle(selected_profiles)
    version_label = f"live-{draft_id}-{int(__import__('time').time())}"
    with engine.begin() as conn:
        promoted = conn.execute(
            text(
                """
                INSERT INTO tuning_config_versions (
                    version_label, config_kind, status, name, description,
                    selected_profiles_json, resolved_config_json, lineage_json,
                    created_by_external_user_id, created_by_email
                )
                VALUES (
                    :version_label, 'live', 'live', :name, :description,
                    CAST(:selected_profiles AS jsonb), CAST(:resolved_config AS jsonb),
                    CAST(:lineage_json AS jsonb), :actor_id, :actor_email
                )
                RETURNING id, version_label, config_kind, status, name, description,
                          selected_profiles_json, resolved_config_json, lineage_json,
                          created_by_external_user_id, created_by_email, created_at, updated_at
                """
            ),
            {
                "version_label": version_label,
                "name": draft["name"],
                "description": draft["description"],
                "selected_profiles": json.dumps(selected_profiles),
                "resolved_config": json.dumps(resolved),
                "lineage_json": json.dumps(
                    {
                        **lineage,
                        "source_draft_id": draft_id,
                        "source_draft_version_label": draft.get("version_label"),
                        "previous_live_version_label": live_before.get("version_label"),
                    }
                ),
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).mappings().one()
        conn.execute(
            text("UPDATE tuning_config_versions SET status = 'archived' WHERE config_kind = 'live' AND version_label <> :version_label"),
            {"version_label": version_label},
        )
        conn.execute(
            text("UPDATE tuning_config_versions SET status = 'promoted' WHERE id = :draft_id"),
            {"draft_id": draft_id},
        )
    for profile_type, profile_name in selected_profiles.items():
        set_active_profile(profile_type, profile_name)
    sync_live_configuration_record()
    live_after = get_live_configuration()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tuning_promotion_events (
                    promoted_config_id, previous_live_version_label, new_live_version_label,
                    action, promotion_note, selected_profiles_json, rollback_target_json,
                    actor_external_user_id, actor_email
                )
                VALUES (
                    :promoted_config_id, :previous_live_version_label, :new_live_version_label,
                    'promote', :promotion_note, CAST(:selected_profiles AS jsonb),
                    CAST(:rollback_target AS jsonb), :actor_id, :actor_email
                )
                """
            ),
            {
                "promoted_config_id": int(promoted["id"]),
                "previous_live_version_label": live_before.get("version_label"),
                "new_live_version_label": version_label,
                "promotion_note": promotion_note.strip(),
                "selected_profiles": json.dumps(selected_profiles),
                "rollback_target": json.dumps(live_before),
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        )
    payload = _normalize_row(promoted)
    payload["selected_profiles"] = payload.pop("selected_profiles_json", {})
    payload["resolved_config"] = payload.pop("resolved_config_json", {})
    payload["lineage"] = payload.pop("lineage_json", {})
    return {"promoted_version": payload, "live_configuration": live_after, "previous_live_configuration": live_before}


def rollback_to_version(*, version_label: str, reason: str, actor: Optional[AuthenticatedUser] = None) -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, version_label, config_kind, status, name, description,
                       selected_profiles_json, resolved_config_json, lineage_json,
                       created_by_external_user_id, created_by_email, created_at, updated_at
                FROM tuning_config_versions
                WHERE version_label = :version_label
                """
            ),
            {"version_label": version_label},
        ).mappings().first()
    if not row:
        raise ValueError(f"Version {version_label} not found")
    target = _normalize_row(row)
    selected_profiles = dict(target.get("selected_profiles_json") or {})
    live_before = get_live_configuration()
    for profile_type, profile_name in selected_profiles.items():
        set_active_profile(profile_type, profile_name)
    sync_live_configuration_record()
    live_after = get_live_configuration()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tuning_promotion_events (
                    promoted_config_id, previous_live_version_label, new_live_version_label,
                    action, promotion_note, selected_profiles_json, rollback_target_json,
                    actor_external_user_id, actor_email
                )
                VALUES (
                    :promoted_config_id, :previous_live_version_label, :new_live_version_label,
                    'rollback', :promotion_note, CAST(:selected_profiles AS jsonb),
                    CAST(:rollback_target AS jsonb), :actor_id, :actor_email
                )
                """
            ),
            {
                "promoted_config_id": int(target["id"]),
                "previous_live_version_label": live_before.get("version_label"),
                "new_live_version_label": version_label,
                "promotion_note": reason.strip(),
                "selected_profiles": json.dumps(selected_profiles),
                "rollback_target": json.dumps(live_before),
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        )
    target["selected_profiles"] = target.pop("selected_profiles_json", {})
    target["resolved_config"] = target.pop("resolved_config_json", {})
    target["lineage"] = target.pop("lineage_json", {})
    return {"rolled_back_to": target, "live_configuration": live_after, "previous_live_configuration": live_before}


def create_embedding_experiment(
    *,
    candidate_config_id: Optional[int],
    basis_embedding_profile: str,
    target_embedding_profile: str,
    scope_type: str,
    source_ids: list[int],
    warning_acknowledged: bool,
    confirmation_count: int,
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    if scope_type not in {"selected_5_files", "all_files"}:
        raise ValueError("Embedding experiment scope must be selected_5_files or all_files")
    locked_source_ids = [int(item) for item in source_ids]
    if scope_type == "selected_5_files" and len(locked_source_ids) != 5:
        raise ValueError("Selected-file embedding experiments require exactly 5 source ids")
    if not warning_acknowledged or confirmation_count < 2:
        raise ValueError("Embedding experiments require warning acknowledgement and double confirmation")
    job_id: Optional[int] = None
    if scope_type == "all_files":
        job_id = create_ingestion_job(
            source_id=None,
            status="queued",
            stage="embedding_full_reindex_requested",
            priority=10,
            triggered_by="tuning_embedding_experiment",
            owner_external_user_id=actor.user_id if actor else None,
            owner_email=actor.email if actor else None,
            job_metadata_json={
                "candidate_config_id": candidate_config_id,
                "basis_embedding_profile": basis_embedding_profile,
                "target_embedding_profile": target_embedding_profile,
                "warning": "Full corpus re-embedding required before production promotion.",
            },
        )
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO embedding_experiment_runs (
                    candidate_config_id, basis_embedding_profile, target_embedding_profile,
                    scope_type, locked_source_ids_json, status, warning_acknowledged,
                    confirmation_count, job_id, actor_external_user_id, actor_email
                )
                VALUES (
                    :candidate_config_id, :basis_embedding_profile, :target_embedding_profile,
                    :scope_type, CAST(:locked_source_ids AS jsonb), 'locked',
                    :warning_acknowledged, :confirmation_count, :job_id, :actor_id, :actor_email
                )
                RETURNING id, candidate_config_id, basis_embedding_profile, target_embedding_profile,
                          scope_type, locked_source_ids_json, status, warning_acknowledged,
                          confirmation_count, job_id, metadata_json, actor_external_user_id,
                          actor_email, created_at, updated_at
                """
            ),
            {
                "candidate_config_id": candidate_config_id,
                "basis_embedding_profile": basis_embedding_profile,
                "target_embedding_profile": target_embedding_profile,
                "scope_type": scope_type,
                "locked_source_ids": json.dumps(locked_source_ids),
                "warning_acknowledged": warning_acknowledged,
                "confirmation_count": confirmation_count,
                "job_id": job_id,
                "actor_id": actor.user_id if actor else None,
                "actor_email": actor.email if actor else None,
            },
        ).mappings().one()
    return _jsonable(dict(row))


def list_embedding_experiments(limit: int = 50) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, candidate_config_id, basis_embedding_profile, target_embedding_profile,
                       scope_type, locked_source_ids_json, status, warning_acknowledged,
                       confirmation_count, job_id, metadata_json, actor_external_user_id,
                       actor_email, created_at, updated_at
                FROM embedding_experiment_runs
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]


def record_model_warmup(*, model_type: str, model_name: str, status: str, latency_ms: Optional[int], error_message: Optional[str], metadata_json: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO model_warmup_runs (
                    model_type, model_name, status, latency_ms, error_message, metadata_json
                )
                VALUES (
                    :model_type, :model_name, :status, :latency_ms, :error_message,
                    CAST(:metadata_json AS jsonb)
                )
                RETURNING id, model_type, model_name, status, latency_ms, error_message, metadata_json, created_at
                """
            ),
            {
                "model_type": model_type,
                "model_name": model_name,
                "status": status,
                "latency_ms": latency_ms,
                "error_message": error_message,
                "metadata_json": json.dumps(metadata_json or {}),
            },
        ).mappings().one()
    return _jsonable(dict(row))


def list_model_warmups(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, model_type, model_name, status, latency_ms, error_message, metadata_json, created_at
                FROM model_warmup_runs
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [_jsonable(dict(row)) for row in rows]
