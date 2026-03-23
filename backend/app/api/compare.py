from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core_rag.answering import CompareRequest, CompareResponse, perform_compare
from app.llm.client import verify_llm_ready


router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
def compare_endpoint(request: CompareRequest):
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )
    return perform_compare(request)
