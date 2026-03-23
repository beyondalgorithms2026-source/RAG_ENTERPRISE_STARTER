from fastapi import APIRouter, HTTPException

from app.core_rag.retrieval import DeepLookupRequest, DeepLookupResponse, perform_deep_lookup
from app.db.repo_sources import get_sources_by_ids


router = APIRouter()

MAX_DEEP_LOOKUP_SOURCE_IDS = 3


def _normalize_source_ids(source_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for source_id in source_ids:
        if source_id in seen:
            continue
        seen.add(source_id)
        normalized.append(source_id)
    return normalized


@router.post("/deep_lookup", response_model=DeepLookupResponse)
def deep_lookup_endpoint(request: DeepLookupRequest):
    normalized_source_ids = _normalize_source_ids(request.source_ids)
    if not normalized_source_ids:
        raise HTTPException(status_code=400, detail={"error": "source_ids_required"})
    if len(normalized_source_ids) > MAX_DEEP_LOOKUP_SOURCE_IDS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "too_many_source_ids",
                "max_source_ids": MAX_DEEP_LOOKUP_SOURCE_IDS,
                "source_ids": normalized_source_ids,
            },
        )

    existing_sources = get_sources_by_ids(normalized_source_ids)
    missing_source_ids = [source_id for source_id in normalized_source_ids if source_id not in existing_sources]
    if missing_source_ids:
        raise HTTPException(
            status_code=404,
            detail={"error": "source_ids_not_found", "missing_source_ids": missing_source_ids},
        )

    normalized_request = request.model_copy(update={"source_ids": normalized_source_ids})
    return perform_deep_lookup(normalized_request)
