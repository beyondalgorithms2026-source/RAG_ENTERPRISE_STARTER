from fastapi import APIRouter, Depends

from app.auth.context import AuthenticatedUser
from app.auth.dependencies import require_search_user
from app.core.rate_limit import rate_limit_search
from app.core_rag.retrieval import SearchRequest, SearchResponse, perform_search


router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_endpoint(
    request: SearchRequest,
    _user: AuthenticatedUser | None = Depends(require_search_user),
    _rate_limit: None = Depends(rate_limit_search),
):
    return perform_search(request)
