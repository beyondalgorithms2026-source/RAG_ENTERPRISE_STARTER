import json
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.context import AuthenticatedUser, reset_current_user, set_current_user
from app.auth.dependencies import require_authenticated_user
from app.core.config import settings
from app.core_rag.answering import AskRequest, AskResponse, perform_ask, _perform_ask_internal
from app.db.repo_governance import is_restricted
from app.llm.client import verify_llm_ready


router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest, user: AuthenticatedUser | None = Depends(require_authenticated_user)):
    restriction = is_restricted(user, {"query_block"})
    if restriction:
        raise HTTPException(status_code=403, detail={"error": "query_blocked", "message": restriction.get("reason")})
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
    restriction = is_restricted(user, {"query_block"})
    if restriction:
        raise HTTPException(status_code=403, detail={"error": "query_blocked", "message": restriction.get("reason")})
    if not request.dry_run and not verify_llm_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_not_ready",
                "message": f"The configured LLM provider or model '{settings.LLM_MODEL}' is unreachable.",
            },
        )

    def generate():
        events: Queue[str | AskResponse | Exception | None] = Queue()
        worker_user = user

        def emit(progress: int, label: str):
            events.put(json.dumps({"type": "progress", "progress": progress, "label": label}) + "\n")

        def run() -> None:
            token = set_current_user(worker_user)
            try:
                emit(4, "Receiving question")
                emit(8, "Routing retrieval strategy")
                result = _perform_ask_internal(request, progress_callback=emit)
                events.put(result)
            except Exception as exc:  # pragma: no cover - surfaced to client
                events.put(exc)
            finally:
                reset_current_user(token)
                events.put(None)

        Thread(target=run, daemon=True).start()

        while True:
            try:
                event = events.get(timeout=0.25)
            except Empty:
                continue
            if event is None:
                break
            if isinstance(event, Exception):
                raise event
            if isinstance(event, AskResponse):
                yield json.dumps({"type": "result", "result": event.model_dump()}) + "\n"
                continue
            yield event

    return StreamingResponse(generate(), media_type="application/x-ndjson")
