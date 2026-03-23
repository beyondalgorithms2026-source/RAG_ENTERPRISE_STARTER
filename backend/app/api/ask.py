from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core_rag.answering import AskRequest, AskResponse, perform_ask
from app.llm.client import verify_llm_ready


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest):
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )
    return perform_ask(request)
