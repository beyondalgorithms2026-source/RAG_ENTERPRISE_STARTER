from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import logger
from app.db.repo_profiles import get_profile, list_profiles, set_active_profile, get_active_profile_name
from app.db.repo_traces import get_trace, get_trace_by_id, list_traces
from app.profiles.models import PROFILE_TYPE_MODELS
from app.profiles.resolver import get_active_profile_snapshot, get_effective_retrieval, invalidate_cache


router = APIRouter(prefix="/admin", tags=["admin"])


class ActiveProfileRequest(BaseModel):
    profile_type: str
    profile_name: str


class TraceListResponse(BaseModel):
    traces: list[dict]
    active_profiles: dict
    retrieval_settings: dict


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
        result.append({
            "id": row["id"],
            "profile_type": row["profile_type"],
            "name": row["name"],
            "config": row["config_json"],
            "is_default": row["is_default"],
            "is_active": row["name"] == active_map.get(row["profile_type"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        })
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
        raise HTTPException(status_code=422, detail=f"Profile config validation failed: {exc}")

    set_active_profile(body.profile_type, body.profile_name)
    invalidate_cache(body.profile_type)
    logger.info("Activated profile %s/%s", body.profile_type, body.profile_name)
    return {"status": "ok", "profile_type": body.profile_type, "profile_name": body.profile_name}


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
