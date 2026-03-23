import json
import re
import time
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.core.logging import log_event, logger
from app.core_rag.retrieval import SearchFilters, SearchMode, SearchRequest, perform_search
from app.llm.client import generate_answer
from app.llm.prompts import REPAIR_PROMPT, SYSTEM_PROMPT, generate_user_prompt


MAX_CHUNK_CHARS = 1500
MAX_TOTAL_CONTEXT_CHARS = 10000


class AskRequest(BaseModel):
    question: str
    k_chunks: int = Field(default=6, le=20, description="Top N chunks to pull for context")
    filters: Optional[SearchFilters] = None
    mode: Optional[SearchMode] = Field(default=None)
    dry_run: bool = Field(default=False, description="Return the prompt without calling the LLM")


class CitationItem(BaseModel):
    citation_id: str
    source_id: int
    source_part_id: Optional[int] = None
    chunk_id: int
    file_name: str
    source_type: str
    heading: str
    locator: Optional[str] = None
    snippet: str


class AskResponse(BaseModel):
    answer: Optional[str] = None
    citations: List[CitationItem] = Field(default_factory=list)
    used_chunks_count: int = 0
    latency_ms: int = 0
    debug_info: Optional[dict[str, Any]] = None


class CompareRequest(BaseModel):
    question: str
    source_ids: List[int] = Field(default_factory=list, description="Explicit source ids to compare")
    k_chunks_per_source: int = Field(default=4, le=10, description="Top N chunks per source to pull for comparison")
    filters: Optional[SearchFilters] = None
    mode: Optional[SearchMode] = Field(default=None)
    dry_run: bool = Field(default=False, description="Return grouped compare prompt without calling the LLM")


class CompareSourceEvidence(BaseModel):
    source_id: int
    file_name: str
    source_type: str
    citations: List[CitationItem] = Field(default_factory=list)


class CompareResponse(BaseModel):
    answer: Optional[str] = None
    sources: List[CompareSourceEvidence] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)
    used_chunks_count: int = 0
    latency_ms: int = 0
    debug_info: Optional[dict[str, Any]] = None


def _build_context_blocks(raw_chunks) -> list[dict[str, Any]]:
    context_blocks = []
    total_chars = 0
    for index, chunk in enumerate(raw_chunks):
        snippet = chunk.snippet[:MAX_CHUNK_CHARS]
        if total_chars + len(snippet) > MAX_TOTAL_CONTEXT_CHARS:
            logger.warning(f"Context max size reached. Dropping remaining {len(raw_chunks) - index} lower-ranked chunks.")
            break

        block = {
            "citation_id": f"S{index + 1}",
            "source_id": chunk.source_id,
            "source_part_id": chunk.source_part_id,
            "chunk_id": chunk.chunk_id,
            "file_name": chunk.file_name,
            "source_type": chunk.source_type,
            "heading": chunk.heading,
            "locator": chunk.locator,
            "snippet": snippet,
        }
        context_blocks.append(block)
        total_chars += len(snippet)
    return context_blocks


def _parse_llm_json(raw_content: str):
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        return None


def _repair_llm_json(raw_content: str):
    log_event("ask.repair_json", stage="ask", status="repairing", reason="invalid_json")
    repair_user_prompt = f"Original question context...\n\n{REPAIR_PROMPT}\n\nThe invalid string you returned was:\n{raw_content}"
    repair_response = generate_answer(SYSTEM_PROMPT, repair_user_prompt)
    if repair_response.get("success"):
        return _parse_llm_json(repair_response["content"])
    return None


def _safe_citation_ids(*, parsed: dict[str, Any], context_blocks: list[dict[str, Any]]) -> list[str]:
    citations_list = parsed.get("citations", [])
    if not isinstance(citations_list, list):
        citations_list = []
    valid_citation_ids = {block["citation_id"] for block in context_blocks}
    return [citation_id for citation_id in citations_list if citation_id in valid_citation_ids]


def _materialize_citations(*, citation_ids: list[str], context_blocks: list[dict[str, Any]]) -> list[CitationItem]:
    final_citations: list[CitationItem] = []
    for safe_id in citation_ids:
        for block in context_blocks:
            if block["citation_id"] == safe_id:
                final_citations.append(
                    CitationItem(
                        citation_id=safe_id,
                        source_id=block["source_id"],
                        source_part_id=block["source_part_id"],
                        chunk_id=block["chunk_id"],
                        file_name=block["file_name"],
                        source_type=block["source_type"],
                        heading=block["heading"],
                        locator=block["locator"],
                        snippet=block["snippet"],
                    )
                )
                break
    return final_citations


def _strip_fake_citations(answer_text: str, safe_citations: list[str]) -> str:
    def strip_fake_citations(match):
        token = match.group(1)
        if token not in safe_citations:
            return ""
        return match.group(0)

    answer_text = re.sub(r"\[(S\d+)\]", strip_fake_citations, answer_text)
    answer_text = re.sub(r" +", " ", answer_text).strip()
    return answer_text


def _compare_user_prompt(*, question: str, source_blocks: list[dict[str, Any]]) -> str:
    lines = [
        "You are comparing evidence across explicitly selected uploaded sources.",
        "Use only the cited evidence blocks below.",
        "Group your reasoning by source before giving a concise comparison answer.",
        "Return strict JSON with keys: answer, citations.",
        "",
        f"QUESTION: {question}",
        "",
        "SOURCE EVIDENCE:",
    ]
    for source_block in source_blocks:
        lines.append(
            f"- SOURCE: {source_block['file_name']} (source_id={source_block['source_id']}, source_type={source_block['source_type']})"
        )
        for citation in source_block["citations"]:
            locator = citation["locator"] or "n/a"
            lines.append(
                f"  [{citation['citation_id']}] heading={citation['heading']} locator={locator} snippet={citation['snippet']}"
            )
    lines.append("")
    lines.append("Return only grounded claims supported by the listed citations.")
    return "\n".join(lines)


def _group_citations_by_source(citations: list[CitationItem]) -> list[CompareSourceEvidence]:
    grouped: dict[int, CompareSourceEvidence] = {}
    for citation in citations:
        bucket = grouped.get(citation.source_id)
        if bucket is None:
            bucket = CompareSourceEvidence(
                source_id=citation.source_id,
                file_name=citation.file_name,
                source_type=citation.source_type,
                citations=[],
            )
            grouped[citation.source_id] = bucket
        bucket.citations.append(citation)
    return list(grouped.values())


def perform_ask(request: AskRequest) -> AskResponse:
    start_time = time.time()
    log_event("ask.started", stage="ask", status="processing", requested_mode=request.mode)
    search_request = SearchRequest(
        question=request.question,
        k=request.k_chunks,
        filters=request.filters,
        mode=request.mode,
    )
    search_response = perform_search(search_request)
    raw_chunks = search_response.results
    context_blocks = _build_context_blocks(raw_chunks)

    user_prompt = generate_user_prompt(request.question, context_blocks)

    if request.dry_run:
        log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode)
        return AskResponse(
            used_chunks_count=len(context_blocks),
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={
                "prompt_length_chars": len(user_prompt),
                "context_blocks_passed": len(context_blocks),
                "mode": search_response.mode,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
            },
        )

    if not context_blocks:
        log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode, reason="no_context")
        return AskResponse(
            answer="Not found in provided sources.",
            used_chunks_count=0,
            latency_ms=int((time.time() - start_time) * 1000),
        )

    llm_response = generate_answer(SYSTEM_PROMPT, user_prompt)
    if not llm_response.get("success"):
        log_event("ask.failed", level=40, stage="ask", status="failed", requested_mode=request.mode, resolved_mode=search_response.mode, reason=str(llm_response.get("error")))
        return AskResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={"error": llm_response.get("error")},
        )

    raw_content = llm_response["content"]
    parsed = _parse_llm_json(raw_content)
    if not parsed:
        parsed = _repair_llm_json(raw_content)

    if not parsed:
        log_event("ask.failed", level=40, stage="ask", status="failed", requested_mode=request.mode, resolved_mode=search_response.mode, reason="json_parse_failed")
        return AskResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={"error": "JSON parse failed on both generation strings"},
        )

    answer_text = parsed.get("answer", "")
    safe_citations = _safe_citation_ids(parsed=parsed, context_blocks=context_blocks)
    answer_text = _strip_fake_citations(answer_text, safe_citations)
    final_citations = _materialize_citations(citation_ids=safe_citations, context_blocks=context_blocks)

    if len(final_citations) == 0 and "not found" not in answer_text.lower():
        answer_text = "Not found in provided sources."

    log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode)

    return AskResponse(
        answer=answer_text,
        citations=final_citations,
        used_chunks_count=len(context_blocks),
        latency_ms=int((time.time() - start_time) * 1000),
    )


def perform_compare(request: CompareRequest) -> CompareResponse:
    start_time = time.time()
    log_event("compare.started", stage="compare", status="processing", requested_mode=request.mode)
    source_ids = [source_id for source_id in request.source_ids if source_id is not None]
    if len(source_ids) < 2:
        log_event("compare.failed", level=40, stage="compare", status="failed", requested_mode=request.mode, reason="compare_requires_at_least_two_source_ids")
        return CompareResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={"error": "compare_requires_at_least_two_source_ids"},
        )

    source_blocks: list[dict[str, Any]] = []
    all_context_blocks: list[dict[str, Any]] = []
    citation_index = 1
    total_used_chunks = 0
    resolved_modes: list[str] = []

    for source_id in source_ids:
        scoped_filters = SearchFilters(
            source_type=request.filters.source_type if request.filters else None,
            source_id=source_id,
            source_part_id=request.filters.source_part_id if request.filters else None,
            locator_filter=request.filters.locator_filter if request.filters else None,
        )
        search_response = perform_search(
            SearchRequest(
                question=request.question,
                k=request.k_chunks_per_source,
                filters=scoped_filters,
                mode=request.mode,
            )
        )
        resolved_modes.append(search_response.mode)
        raw_chunks = search_response.results
        source_contexts = []
        for chunk in raw_chunks:
            snippet = chunk.snippet[:MAX_CHUNK_CHARS]
            block = {
                "citation_id": f"S{citation_index}",
                "source_id": chunk.source_id,
                "source_part_id": chunk.source_part_id,
                "chunk_id": chunk.chunk_id,
                "file_name": chunk.file_name,
                "source_type": chunk.source_type,
                "heading": chunk.heading,
                "locator": chunk.locator,
                "snippet": snippet,
            }
            source_contexts.append(block)
            all_context_blocks.append(block)
            citation_index += 1
        total_used_chunks += len(source_contexts)
        if source_contexts:
            source_blocks.append(
                {
                    "source_id": source_contexts[0]["source_id"],
                    "file_name": source_contexts[0]["file_name"],
                    "source_type": source_contexts[0]["source_type"],
                    "citations": source_contexts,
                }
            )

    if request.dry_run:
        user_prompt = _compare_user_prompt(question=request.question, source_blocks=source_blocks)
        log_event("compare.completed", stage="compare", status="completed", requested_mode=request.mode, reason="dry_run")
        return CompareResponse(
            sources=[
                CompareSourceEvidence(
                    source_id=item["source_id"],
                    file_name=item["file_name"],
                    source_type=item["source_type"],
                    citations=_materialize_citations(
                        citation_ids=[citation["citation_id"] for citation in item["citations"]],
                        context_blocks=all_context_blocks,
                    ),
                )
                for item in source_blocks
            ],
            citations=_materialize_citations(
                citation_ids=[block["citation_id"] for block in all_context_blocks],
                context_blocks=all_context_blocks,
            ),
            used_chunks_count=total_used_chunks,
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={
                "compare_mode": True,
                "source_ids": source_ids,
                "resolved_modes": resolved_modes,
                "context_blocks_passed": total_used_chunks,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
            },
        )

    if not all_context_blocks:
        log_event("compare.completed", stage="compare", status="completed", requested_mode=request.mode, reason="no_context")
        return CompareResponse(
            answer="Not found in provided sources.",
            used_chunks_count=0,
            latency_ms=int((time.time() - start_time) * 1000),
        )

    user_prompt = _compare_user_prompt(question=request.question, source_blocks=source_blocks)
    llm_response = generate_answer(SYSTEM_PROMPT, user_prompt)
    if not llm_response.get("success"):
        log_event("compare.failed", level=40, stage="compare", status="failed", requested_mode=request.mode, reason=str(llm_response.get("error")))
        return CompareResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={"error": llm_response.get("error")},
        )

    parsed = _parse_llm_json(llm_response["content"])
    if not parsed:
        parsed = _repair_llm_json(llm_response["content"])
    if not parsed:
        log_event("compare.failed", level=40, stage="compare", status="failed", requested_mode=request.mode, reason="json_parse_failed")
        return CompareResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info={"error": "JSON parse failed on both generation strings"},
        )

    answer_text = _strip_fake_citations(parsed.get("answer", ""), _safe_citation_ids(parsed=parsed, context_blocks=all_context_blocks))
    final_citations = _materialize_citations(
        citation_ids=_safe_citation_ids(parsed=parsed, context_blocks=all_context_blocks),
        context_blocks=all_context_blocks,
    )
    if len(final_citations) == 0 and "not found" not in answer_text.lower():
        answer_text = "Not found in provided sources."

    log_event("compare.completed", stage="compare", status="completed", requested_mode=request.mode)

    return CompareResponse(
        answer=answer_text,
        sources=_group_citations_by_source(final_citations),
        citations=final_citations,
        used_chunks_count=total_used_chunks,
        latency_ms=int((time.time() - start_time) * 1000),
    )
