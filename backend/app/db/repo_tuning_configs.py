import json
from typing import Any, Optional

from sqlalchemy import text

from app.auth.context import AuthenticatedUser
from app.db.db import engine
from app.db.repo_profiles import (
    PROFILE_TYPES_FOR_TUNING,
    get_active_profile_map,
    get_profile,
    is_registry_approved_profile,
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


def build_resolved_profile_bundle(selected_profiles: dict[str, str]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for profile_type in PROFILE_TYPES_FOR_TUNING:
        profile_name = selected_profiles.get(profile_type)
        if not profile_name:
            raise ValueError(f"Missing selected profile for '{profile_type}'")
        profile = get_profile(profile_type, profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' of type '{profile_type}' not found")
        resolved[profile_type] = {
            "profile_name": profile_name,
            "config": profile["config_json"] or {},
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
    for profile_type in ("embedding", "reranker", "llm"):
        profile_name = normalized[profile_type]
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
    actor: Optional[AuthenticatedUser] = None,
) -> dict[str, Any]:
    normalized = _validated_selected_profiles(selected_profiles)
    resolved = build_resolved_profile_bundle(normalized)
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
) -> dict[str, Any]:
    existing = get_candidate_draft(draft_id)
    if not existing:
        raise ValueError(f"Draft {draft_id} not found")
    normalized = existing["selected_profiles"]
    if selected_profiles is not None:
        normalized = _validated_selected_profiles(selected_profiles)
    resolved = build_resolved_profile_bundle(normalized)
    draft_name = _validated_draft_name(name if name is not None else existing["name"])
    sql = text(
        """
        UPDATE tuning_config_versions
        SET name = :name,
            description = :description,
            selected_profiles_json = CAST(:selected_profiles AS jsonb),
            resolved_config_json = CAST(:resolved_config AS jsonb),
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
