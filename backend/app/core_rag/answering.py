import json
import re
import time
from typing import Any, Callable, List, Optional

from pydantic import BaseModel, Field

from app.core.logging import log_event, logger
from app.actions.policy import clarification_contract, sensitivity_requires_approval
from app.core_rag.retrieval import SearchFilters, SearchMode, SearchRequest, perform_search
from app.auth.context import get_current_user
from app.db.repo_actions import create_approval_request, create_query_feedback
from app.db.repo_query_mining import record_query_event
from app.db.repo_semantic_cache import get_cache_entry, store_cache_entry
from app.db.repo_sources import get_source_by_id
from app.llm.client import generate_answer
from app.llm.prompts import REPAIR_PROMPT, SECOND_PASS_PROMPT, SYSTEM_PROMPT, generate_second_pass_prompt, generate_user_prompt
from app.profiles.resolver import get_effective_retrieval


MAX_CHUNK_CHARS = 1500
MAX_TOTAL_CONTEXT_CHARS = 10000
_STOPWORDS = {
    "a", "an", "and", "are", "around", "as", "at", "be", "by", "did", "do", "does", "for", "from",
    "had", "has", "have", "how", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the",
    "their", "this", "to", "was", "were", "what", "when", "where", "which", "who", "why", "with",
}


class AskRequest(BaseModel):
    question: str
    k_chunks: int = Field(default=6, le=20, description="Top N chunks to pull for context")
    filters: Optional[SearchFilters] = None
    mode: Optional[SearchMode] = Field(default=None)
    dry_run: bool = Field(default=False, description="Return the prompt without calling the LLM")
    deep_research: bool = Field(default=False, description="Use the slower high-recall retrieval path")
    custom_query: Optional[str] = Field(default=None, description="Optional retrieval-only query override")
    anchor_terms: List[str] = Field(default_factory=list, description="Optional manual anchor terms")
    exact_phrase_bias: Optional[str] = Field(default=None, description="Optional exact phrase to prioritize")
    expand_neighbors: bool = Field(default=False, description="Include neighboring chunks/pages when retrieval context may be split")
    force_rare_keyword_scan: bool = Field(default=False, description="Run an extra rare-keyword scan inside Deep Research")


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
    mode: Optional[str] = None


def _not_found_answer(question: str) -> str:
    return "Not found in provided sources."


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
    normalized_from_array = []
    seen: set[str] = set()
    for citation_id in citations_list:
        normalized = str(citation_id or "").strip().upper()
        if normalized in valid_citation_ids and normalized not in seen:
            normalized_from_array.append(normalized)
            seen.add(normalized)

    if normalized_from_array:
        return normalized_from_array

    answer_text = str(parsed.get("answer", "") or "")
    inline_ids = []
    for match in re.findall(r"\[(S\d+)\]", answer_text, flags=re.IGNORECASE):
        normalized = str(match).upper()
        if normalized in valid_citation_ids and normalized not in seen:
            inline_ids.append(normalized)
            seen.add(normalized)
    return inline_ids


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _question_terms(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[A-Za-z0-9]{3,}", str(question or "").lower())
        if token not in _STOPWORDS
    }


def _clean_sentence_candidate(sentence: str) -> str:
    sentence = _normalize_text(sentence)
    sentence = re.sub(r"^[,.;:)\]]+\s*", "", sentence)
    sentence = re.sub(r"\s+([,.;:?!])", r"\1", sentence)
    return sentence


def _sentence_score(*, sentence: str, question_terms: set[str], chunk_index: int) -> int:
    lowered = sentence.lower()
    terms_in_sentence = {token for token in re.findall(r"[A-Za-z0-9]{3,}", lowered) if token not in _STOPWORDS}
    overlap = len(question_terms & terms_in_sentence)
    year_mentions = len(re.findall(r"\b(?:19|20)\d{2}\b", sentence))
    list_bonus = 2 if any(marker in sentence for marker in ("e.g.", "such as", "including", "like ")) else 0
    length_bonus = 1 if 70 <= len(sentence) <= 320 else 0
    starts_cleanly = 0 if re.match(r"^[a-z]", sentence) else 2
    fragment_penalty = -4 if not re.search(r"[.!?]$", sentence) else 0
    early_chunk_bonus = max(0, 3 - chunk_index)
    return (overlap * 6) + (year_mentions * 3) + list_bonus + length_bonus + starts_cleanly + fragment_penalty + early_chunk_bonus


def _extract_inline_citations(answer_text: str) -> list[str]:
    seen: set[str] = set()
    inline_ids: list[str] = []
    for match in re.findall(r"\[(S\d+)\]", str(answer_text or ""), flags=re.IGNORECASE):
        normalized = str(match).upper()
        if normalized not in seen:
            inline_ids.append(normalized)
            seen.add(normalized)
    return inline_ids


def _answer_fallback_reason(*, answer_text: str, question: str, safe_citations: list[str]) -> Optional[str]:
    cleaned = _normalize_text(answer_text)
    if not cleaned:
        return "empty_answer"
    if "not found" in cleaned.lower():
        return "not_found_answer"
    if len(cleaned) < 30:
        return "answer_too_short"
    if re.match(r"^[a-z]", cleaned):
        return "answer_starts_mid_sentence"
    if not safe_citations:
        return "no_valid_citations"
    question_terms = _question_terms(question)
    if question_terms:
        answer_terms = set(re.findall(r"[A-Za-z0-9]{3,}", cleaned.lower()))
        if len(question_terms & answer_terms) == 0:
            return "question_terms_missing"
    return None


def _merge_debug_info(*, retrieval_trace: Optional[dict[str, Any]], answer_generation_path: str, fallback_reason: Optional[str] = None, error: Optional[str] = None, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    debug_info: dict[str, Any] = {}
    if retrieval_trace:
        debug_info["retrieval_trace"] = retrieval_trace
    debug_info["answer_generation_path"] = answer_generation_path
    debug_info["fallback_reason"] = fallback_reason
    if error:
        debug_info["error"] = error
    if extra:
        debug_info.update(extra)
    return debug_info


def _citation_sensitivity_payload(citations: list[CitationItem]) -> list[dict[str, Any]]:
    payload = []
    for citation in citations:
        source = get_source_by_id(citation.source_id)
        payload.append(
            {
                "source_id": citation.source_id,
                "file_name": citation.file_name,
                "sensitivity_label": source.sensitivity_label if source else None,
            }
        )
    return payload


def _record_missing_evidence_feedback(*, question: str, retrieval_trace: Optional[dict[str, Any]], answer_path: str) -> None:
    try:
        actor = get_current_user()
        create_query_feedback(
            question=question,
            feedback_type="missing_evidence",
            rating=None,
            reason="automatic_not_found",
            suggested_source=None,
            request_id=str((retrieval_trace or {}).get("request_id") or "") or None,
            answer_path=answer_path,
            actor=actor,
            metadata_json={"automatic": True},
        )
    except Exception as exc:
        logger.debug("Failed to record missing evidence feedback: %s", exc)


def _maybe_gate_sensitive_answer(*, request: AskRequest, answer_text: str, citations: list[CitationItem], debug_info: dict[str, Any]) -> Optional[AskResponse]:
    needs_approval, reasons = sensitivity_requires_approval(
        question=request.question,
        citations=_citation_sensitivity_payload(citations),
    )
    if not needs_approval:
        return None
    actor = get_current_user()
    approval_id = create_approval_request(
        approval_type="sensitive_answer",
        reason=", ".join(reasons),
        actor=actor,
        requested_payload_json={"question": request.question, "mode": request.mode, "reasons": reasons},
        response_payload_json={"answer": answer_text, "citations": [citation.model_dump() for citation in citations], "debug_info": debug_info},
    )
    gated_debug = dict(debug_info)
    gated_debug["approval"] = {"approval_id": approval_id, "status": "pending", "reasons": reasons}
    gated_debug["clarification"] = clarification_contract(request.question, answer_path="pending_approval", evidence_count=len(citations))
    return AskResponse(
        answer=f"This answer may contain sensitive information and is pending human approval. Approval request #{approval_id} has been queued.",
        citations=[],
        used_chunks_count=len(citations),
        latency_ms=0,
        debug_info=gated_debug,
        mode=request.mode,
    )


def _record_answer_trace(
    *,
    retrieval_trace: Optional[dict[str, Any]],
    ask_latency_ms: int,
    answer_generation_path: str,
    fallback_reason: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not retrieval_trace:
        return retrieval_trace

    trace_payload = dict(retrieval_trace)
    latency_payload = dict(trace_payload.get("latency_ms") or {})
    if "search_total" not in latency_payload and "total" in latency_payload:
        latency_payload["search_total"] = latency_payload["total"]
    latency_payload["ask"] = ask_latency_ms
    latency_payload["total"] = ask_latency_ms
    trace_payload["latency_ms"] = latency_payload
    trace_payload["answer_generation_path"] = answer_generation_path
    if fallback_reason is not None:
        trace_payload["fallback_reason"] = fallback_reason
    if error:
        trace_payload["answer_error"] = error

    request_id = trace_payload.get("request_id")
    if not request_id:
        return trace_payload

    try:
        from app.db.repo_traces import update_trace

        update_trace(
            request_id=request_id,
            answer_path=answer_generation_path,
            fallback_reason=fallback_reason,
            latency_ms=latency_payload,
            trace_json=trace_payload,
            score_diagnostics=trace_payload.get("score_diagnostics"),
        )
    except Exception as exc:
        logger.debug("Failed to update retrieval trace for ask request: %s", exc)
    return trace_payload


def _generate_second_pass_answer(*, question: str, context_blocks: list[dict[str, Any]], prior_answer: str, fallback_reason: str) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not context_blocks:
        return None, "no_context_blocks"

    repair_user_prompt = generate_second_pass_prompt(
        question=question,
        context_blocks=context_blocks,
        prior_answer=prior_answer,
        fallback_reason=fallback_reason,
    )
    repair_response = generate_answer(SECOND_PASS_PROMPT, repair_user_prompt)
    if not repair_response.get("success"):
        return None, str(repair_response.get("error") or "second_pass_failed")

    parsed = _parse_llm_json(repair_response["content"])
    if not parsed:
        parsed = _repair_llm_json(repair_response["content"])
    if not parsed:
        return None, "second_pass_json_parse_failed"
    return parsed, None


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

def _perform_ask_internal(request: AskRequest, progress_callback: Optional[Callable[[int, str], None]] = None) -> AskResponse:
    start_time = time.time()
    log_event("ask.started", stage="ask", status="processing", requested_mode=request.mode)
    if progress_callback:
        progress_callback(10, "Searching sources")
    search_request = SearchRequest(
        question=request.question,
        k=request.k_chunks,
        filters=request.filters,
        mode=request.mode,
        deep_research=request.deep_research,
        custom_query=request.custom_query,
        anchor_terms=request.anchor_terms,
        exact_phrase_bias=request.exact_phrase_bias,
        expand_neighbors=request.expand_neighbors,
        force_rare_keyword_scan=request.force_rare_keyword_scan,
    )
    search_response = perform_search(search_request)
    raw_chunks = search_response.results
    context_blocks = _build_context_blocks(raw_chunks)
    if progress_callback:
        progress_callback(42, f"Retrieved {len(raw_chunks)} candidate chunks")

    user_prompt = generate_user_prompt(request.question, context_blocks)

    if request.dry_run:
        ask_latency_ms = int((time.time() - start_time) * 1000)
        retrieval_trace = _record_answer_trace(
            retrieval_trace=search_response.debug_info,
            ask_latency_ms=ask_latency_ms,
            answer_generation_path="dry_run",
        )
        if progress_callback:
            progress_callback(100, "Prompt assembly complete")
        log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode)
        return AskResponse(
            used_chunks_count=len(context_blocks),
            latency_ms=ask_latency_ms,
            debug_info={
                "prompt_length_chars": len(user_prompt),
                "context_blocks_passed": len(context_blocks),
                "mode": search_response.mode,
                "retrieval_trace": retrieval_trace,
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
            },
            mode=search_response.mode,
        )

    if not context_blocks:
        ask_latency_ms = int((time.time() - start_time) * 1000)
        retrieval_trace = _record_answer_trace(
            retrieval_trace=search_response.debug_info,
            ask_latency_ms=ask_latency_ms,
            answer_generation_path="not_found",
        )
        if progress_callback:
            progress_callback(100, "No grounded context found")
        log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode, reason="no_context")
        _record_missing_evidence_feedback(question=request.question, retrieval_trace=retrieval_trace, answer_path="not_found")
        return AskResponse(
            answer=_not_found_answer(request.question),
            used_chunks_count=0,
            latency_ms=ask_latency_ms,
            mode=search_response.mode,
            debug_info={
                "retrieval_trace": retrieval_trace,
                "answer_generation_path": "not_found",
                "clarification": clarification_contract(
                    request.question,
                    answer_path="not_found",
                    evidence_count=0,
                    source_scoped=bool(request.filters and request.filters.source_id is not None),
                ),
            },
        )

    if progress_callback:
        progress_callback(70, "Generating grounded answer")
    llm_response = generate_answer(SYSTEM_PROMPT, user_prompt)
    if not llm_response.get("success"):
        ask_latency_ms = int((time.time() - start_time) * 1000)
        retrieval_trace = _record_answer_trace(
            retrieval_trace=search_response.debug_info,
            ask_latency_ms=ask_latency_ms,
            answer_generation_path="not_found",
            error=str(llm_response.get("error")),
        )
        if progress_callback:
            progress_callback(100, "Answer generation failed")
        log_event("ask.failed", level=40, stage="ask", status="failed", requested_mode=request.mode, resolved_mode=search_response.mode, reason=str(llm_response.get("error")))
        return AskResponse(
            answer=_not_found_answer(request.question),
            latency_ms=ask_latency_ms,
            debug_info=_merge_debug_info(
                retrieval_trace=retrieval_trace,
                answer_generation_path="not_found",
                error=str(llm_response.get("error")),
                extra={
                    "clarification": clarification_contract(
                        request.question,
                        answer_path="not_found",
                        evidence_count=0,
                        source_scoped=bool(request.filters and request.filters.source_id is not None),
                    )
                },
            ),
            mode=search_response.mode,
        )

    raw_content = llm_response["content"]
    if progress_callback:
        progress_callback(84, "Validating citations")
    parsed = _parse_llm_json(raw_content)
    if not parsed:
        parsed = _repair_llm_json(raw_content)

    if not parsed:
        ask_latency_ms = int((time.time() - start_time) * 1000)
        retrieval_trace = _record_answer_trace(
            retrieval_trace=search_response.debug_info,
            ask_latency_ms=ask_latency_ms,
            answer_generation_path="not_found",
            error="JSON parse failed on both generation strings",
        )
        if progress_callback:
            progress_callback(100, "Answer parsing failed")
        log_event("ask.failed", level=40, stage="ask", status="failed", requested_mode=request.mode, resolved_mode=search_response.mode, reason="json_parse_failed")
        return AskResponse(
            answer=_not_found_answer(request.question),
            latency_ms=ask_latency_ms,
            debug_info=_merge_debug_info(
                retrieval_trace=retrieval_trace,
                answer_generation_path="not_found",
                error="JSON parse failed on both generation strings",
                extra={
                    "clarification": clarification_contract(
                        request.question,
                        answer_path="not_found",
                        evidence_count=0,
                        source_scoped=bool(request.filters and request.filters.source_id is not None),
                    )
                },
            ),
            mode=search_response.mode,
        )

    answer_text = parsed.get("answer", "")
    safe_citations = _safe_citation_ids(parsed=parsed, context_blocks=context_blocks)
    answer_text = _strip_fake_citations(answer_text, safe_citations)
    answer_generation_path = "llm"
    fallback_reason = _answer_fallback_reason(
        answer_text=answer_text,
        question=request.question,
        safe_citations=safe_citations,
    )
    repair_attempted = False
    if fallback_reason and context_blocks and "not found" not in answer_text.lower():
        repair_attempted = True
        repaired_parsed, repair_error = _generate_second_pass_answer(
            question=request.question,
            context_blocks=context_blocks,
            prior_answer=answer_text,
            fallback_reason=fallback_reason,
        )
        if repaired_parsed:
            repaired_safe_citations = _safe_citation_ids(parsed=repaired_parsed, context_blocks=context_blocks)
            repaired_answer_text = _strip_fake_citations(repaired_parsed.get("answer", ""), repaired_safe_citations)
            repaired_reason = _answer_fallback_reason(
                answer_text=repaired_answer_text,
                question=request.question,
                safe_citations=repaired_safe_citations,
            )
            if repaired_reason is None or "not found" in repaired_answer_text.lower():
                answer_text = repaired_answer_text
                safe_citations = repaired_safe_citations
                answer_generation_path = "repair"
                fallback_reason = fallback_reason
            else:
                fallback_reason = f"{fallback_reason}; repair_unsuitable:{repaired_reason}"
        elif repair_error:
            fallback_reason = f"{fallback_reason}; repair_error:{repair_error}"

    final_citations = _materialize_citations(citation_ids=safe_citations, context_blocks=context_blocks)
    final_reason = _answer_fallback_reason(
        answer_text=answer_text,
        question=request.question,
        safe_citations=safe_citations,
    )

    if (repair_attempted and final_reason and "not found" not in str(answer_text).lower()) or (
        len(final_citations) == 0 and "not found" not in answer_text.lower()
    ):
        answer_text = "Not found in provided sources."
        answer_generation_path = "not_found"
    elif "not found" in str(answer_text).lower():
        answer_generation_path = "not_found"
    if answer_generation_path == "not_found":
        final_citations = []
        _record_missing_evidence_feedback(question=request.question, retrieval_trace=search_response.debug_info, answer_path="not_found")
        answer_text = _not_found_answer(request.question)

    if progress_callback:
        progress_callback(100, "Grounded answer ready")
    log_event("ask.completed", stage="ask", status="completed", requested_mode=request.mode, resolved_mode=search_response.mode)
    ask_latency_ms = int((time.time() - start_time) * 1000)
    retrieval_trace = _record_answer_trace(
        retrieval_trace=search_response.debug_info,
        ask_latency_ms=ask_latency_ms,
        answer_generation_path=answer_generation_path,
        fallback_reason=fallback_reason,
    )

    debug_info = _merge_debug_info(
        retrieval_trace=retrieval_trace,
        answer_generation_path=answer_generation_path,
        fallback_reason=fallback_reason,
        extra={
            "clarification": clarification_contract(
                request.question,
                answer_path=answer_generation_path,
                evidence_count=len(final_citations),
                source_scoped=bool(request.filters and request.filters.source_id is not None),
            )
        },
    )
    gated_response = _maybe_gate_sensitive_answer(
        request=request,
        answer_text=answer_text,
        citations=final_citations,
        debug_info=debug_info,
    )
    if gated_response is not None:
        gated_response.latency_ms = ask_latency_ms
        return gated_response

    return AskResponse(
        answer=answer_text,
        citations=final_citations,
        used_chunks_count=len(context_blocks),
        latency_ms=ask_latency_ms,
        mode=search_response.mode,
        debug_info=debug_info,
    )


def perform_ask(request: AskRequest) -> AskResponse:
    actor = get_current_user()
    retrieval_profile = get_effective_retrieval()
    if retrieval_profile.semantic_cache_enabled and not request.dry_run:
        cached = get_cache_entry(question=request.question, retrieval_mode=request.mode, actor=actor)
        if cached:
            answer_json = cached.get("answer_json") or {}
            citations_json = cached.get("citations_json") or []
            return AskResponse(
                answer=answer_json.get("answer"),
                citations=[CitationItem(**item) for item in citations_json],
                used_chunks_count=int(answer_json.get("used_chunks_count") or 0),
                latency_ms=0,
                mode=answer_json.get("mode") or request.mode,
                debug_info={
                    "semantic_cache": {"hit": True, "cache_entry_id": cached.get("id")},
                    "answer_generation_path": "semantic_cache",
                },
            )

    response = _perform_ask_internal(request)
    debug_info = response.debug_info or {}
    answer_path = str(debug_info.get("answer_generation_path") or "unknown")
    retrieval_trace = debug_info.get("retrieval_trace") or {}
    event_type = "no_evidence" if answer_path == "not_found" else "ask_completed"
    try:
        record_query_event(
            question=request.question,
            event_type=event_type,
            answer_path=answer_path,
            request_id=retrieval_trace.get("request_id"),
            retrieval_mode=response.mode,
            latency_ms=response.latency_ms,
            actor=actor,
            metadata_json={"used_chunks_count": response.used_chunks_count, "citation_count": len(response.citations)},
        )
    except Exception as exc:  # pragma: no cover - observability should not fail answers
        logger.debug("Failed to record query event: %s", exc)

    if retrieval_profile.semantic_cache_enabled and not request.dry_run and response.answer and answer_path not in {"approval_required", "not_found"}:
        try:
            store_cache_entry(
                question=request.question,
                retrieval_mode=request.mode,
                answer_json={
                    "answer": response.answer,
                    "used_chunks_count": response.used_chunks_count,
                    "latency_ms": response.latency_ms,
                    "mode": response.mode,
                },
                citations_json=[citation.model_dump() for citation in response.citations],
                retrieved_chunk_ids=[int(citation.chunk_id) for citation in response.citations],
                ttl_seconds=retrieval_profile.semantic_cache_ttl_seconds,
                metadata_json={"source": "perform_ask"},
            )
        except Exception as exc:  # pragma: no cover - cache should not fail answers
            logger.debug("Failed to store semantic cache entry: %s", exc)
    return response


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
            debug_info=_merge_debug_info(
                retrieval_trace=None,
                answer_generation_path="not_found",
                error=str(llm_response.get("error")),
            ),
        )

    parsed = _parse_llm_json(llm_response["content"])
    if not parsed:
        parsed = _repair_llm_json(llm_response["content"])
    if not parsed:
        log_event("compare.failed", level=40, stage="compare", status="failed", requested_mode=request.mode, reason="json_parse_failed")
        return CompareResponse(
            answer="Not found in provided sources.",
            latency_ms=int((time.time() - start_time) * 1000),
            debug_info=_merge_debug_info(
                retrieval_trace=None,
                answer_generation_path="not_found",
                error="JSON parse failed on both generation strings",
            ),
        )

    safe_citation_ids = _safe_citation_ids(parsed=parsed, context_blocks=all_context_blocks)
    answer_text = _strip_fake_citations(parsed.get("answer", ""), safe_citation_ids)
    answer_generation_path = "llm"
    fallback_reason = _answer_fallback_reason(
        answer_text=answer_text,
        question=request.question,
        safe_citations=safe_citation_ids,
    )
    repair_attempted = False
    if fallback_reason and all_context_blocks and "not found" not in answer_text.lower():
        repair_attempted = True
        repaired_parsed, repair_error = _generate_second_pass_answer(
            question=request.question,
            context_blocks=all_context_blocks,
            prior_answer=answer_text,
            fallback_reason=fallback_reason,
        )
        if repaired_parsed:
            repaired_safe_citation_ids = _safe_citation_ids(parsed=repaired_parsed, context_blocks=all_context_blocks)
            repaired_answer_text = _strip_fake_citations(repaired_parsed.get("answer", ""), repaired_safe_citation_ids)
            repaired_reason = _answer_fallback_reason(
                answer_text=repaired_answer_text,
                question=request.question,
                safe_citations=repaired_safe_citation_ids,
            )
            if repaired_reason is None or "not found" in repaired_answer_text.lower():
                answer_text = repaired_answer_text
                safe_citation_ids = repaired_safe_citation_ids
                answer_generation_path = "repair"
            else:
                fallback_reason = f"{fallback_reason}; repair_unsuitable:{repaired_reason}"
        elif repair_error:
            fallback_reason = f"{fallback_reason}; repair_error:{repair_error}"
    final_citations = _materialize_citations(
        citation_ids=safe_citation_ids,
        context_blocks=all_context_blocks,
    )
    final_reason = _answer_fallback_reason(
        answer_text=answer_text,
        question=request.question,
        safe_citations=safe_citation_ids,
    )
    if (repair_attempted and final_reason and "not found" not in str(answer_text).lower()) or (
        len(final_citations) == 0 and "not found" not in answer_text.lower()
    ):
        answer_text = "Not found in provided sources."
        answer_generation_path = "not_found"
    elif "not found" in str(answer_text).lower():
        answer_generation_path = "not_found"
    if answer_generation_path == "not_found":
        final_citations = []

    log_event("compare.completed", stage="compare", status="completed", requested_mode=request.mode)

    return CompareResponse(
        answer=answer_text,
        sources=_group_citations_by_source(final_citations),
        citations=final_citations,
        used_chunks_count=total_used_chunks,
        latency_ms=int((time.time() - start_time) * 1000),
        debug_info=_merge_debug_info(
            retrieval_trace=None,
            answer_generation_path=answer_generation_path,
            fallback_reason=fallback_reason,
        ),
    )
