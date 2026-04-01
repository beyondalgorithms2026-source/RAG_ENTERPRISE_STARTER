import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.context import AuthenticatedUser
from app.auth.dependencies import require_authenticated_user
from app.core.config import settings
from app.core_rag.answering import AskRequest, AskResponse, perform_ask, _perform_ask_internal
from app.llm.client import verify_llm_ready


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest, user: AuthenticatedUser | None = Depends(require_authenticated_user)):
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )
    return perform_ask(request)


@router.post("/ask/stream")
def ask_stream_endpoint(request: AskRequest, user: AuthenticatedUser | None = Depends(require_authenticated_user)):
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )

    def generate():
        events: list[str] = []

        def emit(progress: int, label: str):
            events.append(json.dumps({"type": "progress", "progress": progress, "label": label}) + "\n")

        emit(4, "Receiving question")
        emit(8, "Routing retrieval strategy")
        result = _perform_ask_internal(request, progress_callback=emit)
        for event in events:
            yield event
        yield json.dumps({"type": "result", "result": result.model_dump()}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
