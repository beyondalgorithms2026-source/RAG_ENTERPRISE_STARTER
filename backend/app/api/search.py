from fastapi import APIRouter

from app.core_rag.retrieval import SearchRequest, SearchResponse, perform_search


router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_endpoint(request: SearchRequest):
    return perform_search(request)
