from fastapi import APIRouter, Depends, HTTPException

from app.auth.context import AuthenticatedUser
from app.auth.dependencies import require_ask_user
from app.core.config import settings
from app.core.rate_limit import rate_limit_compare
from app.core_rag.answering import CompareRequest, CompareResponse, perform_compare
from app.llm.client import verify_llm_ready


router = APIRouter()


@router.post("/compare", response_model=CompareResponse)
def compare_endpoint(
    request: CompareRequest,
    _user: AuthenticatedUser | None = Depends(require_ask_user),
    _rate_limit: None = Depends(rate_limit_compare),
):
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )
    return perform_compare(request)
