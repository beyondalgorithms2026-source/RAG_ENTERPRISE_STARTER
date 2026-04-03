from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional

from app.adapters.models import ParsedSourceDocument, ParsedSourcePart
from app.corpus_policies import CorpusPolicy, get_corpus_policy


MIN_WORDS = 120
TARGET_WORDS = 320
OVERLAP_WORDS = 40
PDF_CROSS_PAGE_BRIDGE_WORDS = 140


@dataclass
class ChunkRecord:
    chunk_index: int
    source_part_id: Optional[int]
    heading: str
    section_path: str
    chunk_text: str
    token_count: int
    locator_json: Dict[str, Any]
    provenance_json: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "source_part_id": self.source_part_id,
            "heading": self.heading,
            "section_path": self.section_path,
            "chunk_text": self.chunk_text,
            "token_count": self.token_count,
            "locator_json": self.locator_json,
            "provenance_json": self.provenance_json,
        }


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _normalize_text(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    cleaned = "\n".join(line for line in lines if line.strip()).strip()
    return cleaned


def _split_word_windows(text: str, *, target_words: int = TARGET_WORDS, overlap_words: int = OVERLAP_WORDS) -> List[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= target_words:
        return [" ".join(words)]

    windows: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        windows.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(end - overlap_words, start + 1)
    return windows


def _transcript_metadata(text: str) -> Dict[str, Any]:
    speakers: List[str] = []
    for speaker in re.findall(r"(?:^|\s)([A-Z][A-Za-z0-9 .'-]{1,40}):", text):
        normalized = speaker.strip()
        if normalized not in speakers:
            speakers.append(normalized)
    timestamps = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text)
    metadata: Dict[str, Any] = {}
    if speakers:
        metadata["speakers"] = speakers
        metadata["speaker"] = speakers[0]
    if timestamps:
        metadata["time_start"] = timestamps[0]
        metadata["time_markers"] = timestamps[:6]
    return metadata


def _head_words(text: str, count: int) -> str:
    words = text.split()
    return " ".join(words[:count]) if words else ""


def _tail_words(text: str, count: int) -> str:
    words = text.split()
    return " ".join(words[-count:]) if words else ""


def _section_heading(part: ParsedSourcePart) -> str:
    if part.title:
        return part.title.strip()
    if part.part_type == "text_block":
        return "Text"
    if part.part_type == "page":
        return f"Page {part.locator_json.get('page', part.part_index + 1)}"
    if part.part_type == "slide":
        return f"Slide {part.locator_json.get('slide', part.part_index + 1)}"
    if part.part_type == "sheet":
        return str(part.locator_json.get("sheet", part.title or f"Sheet {part.part_index + 1}"))
    if part.part_type == "email_header":
        return "Email Headers"
    if part.part_type == "email_body":
        return "Email Body"
    if part.part_type == "table":
        return part.title or f"Table {part.part_index + 1}"
    return part.part_type.replace("_", " ").title()


def _base_locator(part: ParsedSourcePart) -> Dict[str, Any]:
    return dict(part.locator_json)


def _build_chunk(
    *,
    chunk_index: int,
    part: ParsedSourcePart,
    heading: str,
    section_path: str,
    chunk_text: str,
    locator_json: Dict[str, Any],
    chunk_strategy: str,
) -> ChunkRecord:
    provenance = dict(part.provenance_json)
    provenance.update(
        {
            "chunk_strategy": chunk_strategy,
            "source_part_index": part.part_index,
            "source_part_type": part.part_type,
        }
    )
    return ChunkRecord(
        chunk_index=chunk_index,
        source_part_id=None,
        heading=heading,
        section_path=section_path,
        chunk_text=chunk_text,
        token_count=estimate_tokens(chunk_text),
        locator_json=locator_json,
        provenance_json=provenance,
    )


def _chunk_single_part(
    *,
    start_index: int,
    part: ParsedSourcePart,
    section_path: str,
    chunk_strategy: str,
    policy: CorpusPolicy,
) -> List[ChunkRecord]:
    text = _normalize_text(part.content_text)
    if not text:
        return []
    heading = _section_heading(part)
    windows = _split_word_windows(
        text,
        target_words=policy.chunk_target_words,
        overlap_words=policy.chunk_overlap_words,
    )
    chunks: List[ChunkRecord] = []
    for offset, window in enumerate(windows):
        locator = _base_locator(part)
        if len(windows) > 1:
            locator["chunk_window"] = offset + 1
            locator["chunk_window_total"] = len(windows)
        if policy.transcript_metadata_enabled:
            locator.update(_transcript_metadata(window))
        chunks.append(
            _build_chunk(
                chunk_index=start_index + offset,
                part=part,
                heading=heading,
                section_path=section_path,
                chunk_text=window,
                locator_json=locator,
                chunk_strategy=chunk_strategy,
            )
        )
    return chunks


def _chunk_pdf(parts: Iterable[ParsedSourcePart], *, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    page_chunks: List[tuple[ParsedSourcePart, List[ChunkRecord]]] = []
    next_index = 0
    for part in parts:
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=f"page:{part.locator_json.get('page', part.part_index + 1)}",
            chunk_strategy="pdf_page",
            policy=policy,
        )
        chunks.extend(part_chunks)
        page_chunks.append((part, part_chunks))
        next_index += len(part_chunks)

    stitched_chunks: List[ChunkRecord] = []
    for current_index in range(1, len(page_chunks)):
        previous_part, previous_chunks = page_chunks[current_index - 1]
        current_part, current_chunks = page_chunks[current_index]
        if not previous_chunks or not current_chunks:
            continue

        previous_page = int(previous_part.locator_json.get("page", previous_part.part_index + 1))
        current_page = int(current_part.locator_json.get("page", current_part.part_index + 1))
        if current_page != previous_page + 1:
            continue

        previous_text = _tail_words(previous_chunks[-1].chunk_text, PDF_CROSS_PAGE_BRIDGE_WORDS)
        current_text = _head_words(current_chunks[0].chunk_text, PDF_CROSS_PAGE_BRIDGE_WORDS)
        stitched_text = f"{previous_text}\n\n{current_text}".strip()
        if len(stitched_text.split()) < 8:
            continue

        locator = {
            "page_start": previous_page,
            "page_end": current_page,
            "pages": [previous_page, current_page],
            "cross_page_stitch": True,
            "stitched_from_chunk_windows": [
                previous_chunks[-1].locator_json.get("chunk_window"),
                current_chunks[0].locator_json.get("chunk_window"),
            ],
        }
        provenance = dict(previous_part.provenance_json)
        provenance.update(
            {
                "chunk_strategy": "pdf_cross_page",
                "source_part_indices": [previous_part.part_index, current_part.part_index],
                "source_part_types": [previous_part.part_type, current_part.part_type],
                "stitched_from_pages": [previous_page, current_page],
                "stitched_from_chunk_indices": [previous_chunks[-1].chunk_index, current_chunks[0].chunk_index],
            }
        )
        stitched_chunks.append(
            ChunkRecord(
                chunk_index=next_index,
                source_part_id=None,
                heading=f"Pages {previous_page}-{current_page}",
                section_path=f"pages:{previous_page}-{current_page}",
                chunk_text=stitched_text,
                token_count=estimate_tokens(stitched_text),
                locator_json=locator,
                provenance_json=provenance,
            )
        )
        next_index += 1

    chunks.extend(stitched_chunks)
    return chunks


def _chunk_pptx(parts: Iterable[ParsedSourcePart], *, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        slide_number = part.locator_json.get("slide", part.part_index + 1)
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=f"slide:{slide_number}",
            chunk_strategy="pptx_slide",
            policy=policy,
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def _chunk_xlsx(parts: Iterable[ParsedSourcePart], *, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        lines = [line.strip() for line in part.content_text.splitlines() if line.strip()]
        if not lines:
            continue
        heading = _section_heading(part)
        sheet_name = part.locator_json.get("sheet", heading)
        batch: List[str] = []
        batch_rows: List[int] = []
        for line in lines:
            batch.append(line)
            if line.startswith("Row "):
                row_prefix = line.split(":", 1)[0].replace("Row ", "").strip()
                if row_prefix.isdigit():
                    batch_rows.append(int(row_prefix))
            joined = "\n".join(batch)
            if len(joined.split()) >= policy.chunk_target_words:
                locator = _base_locator(part)
                if batch_rows:
                    locator["range"] = f"{sheet_name}!rows {min(batch_rows)}-{max(batch_rows)}"
                chunks.append(
                    _build_chunk(
                        chunk_index=next_index,
                        part=part,
                        heading=heading,
                        section_path=f"sheet:{sheet_name}",
                        chunk_text=joined,
                        locator_json=locator,
                        chunk_strategy="xlsx_sheet_rows",
                    )
                )
                next_index += 1
                overlap = batch[-1:] if batch else []
                overlap_rows = batch_rows[-1:] if batch_rows else []
                batch = list(overlap)
                batch_rows = list(overlap_rows)
        if batch:
            locator = _base_locator(part)
            if batch_rows:
                locator["range"] = f"{sheet_name}!rows {min(batch_rows)}-{max(batch_rows)}"
            chunks.append(
                _build_chunk(
                    chunk_index=next_index,
                    part=part,
                    heading=heading,
                    section_path=f"sheet:{sheet_name}",
                    chunk_text="\n".join(batch),
                    locator_json=locator,
                    chunk_strategy="xlsx_sheet_rows",
                )
            )
            next_index += 1
    return chunks


def _flush_docx_buffer(
    *,
    chunks: List[ChunkRecord],
    next_index: int,
    section_heading: str,
    buffer_parts: List[ParsedSourcePart],
    policy: CorpusPolicy,
) -> int:
    if not buffer_parts:
        return next_index
    combined = "\n\n".join(_normalize_text(part.content_text) for part in buffer_parts if _normalize_text(part.content_text)).strip()
    if not combined:
        return next_index

    first_part = buffer_parts[0]
    windows = _split_word_windows(
        combined,
        target_words=policy.chunk_target_words,
        overlap_words=policy.chunk_overlap_words,
    )
    for offset, window in enumerate(windows):
        locator = _base_locator(first_part)
        locator["docx_part_indices"] = [part.part_index for part in buffer_parts]
        if len(windows) > 1:
            locator["chunk_window"] = offset + 1
            locator["chunk_window_total"] = len(windows)
        if policy.transcript_metadata_enabled:
            locator.update(_transcript_metadata(window))
        chunks.append(
            _build_chunk(
                chunk_index=next_index + offset,
                part=first_part,
                heading=section_heading,
                section_path=section_heading,
                chunk_text=window,
                locator_json=locator,
                chunk_strategy="docx_section_buffer",
            )
        )
    return next_index + len(windows)


def _chunk_docx(parts: Iterable[ParsedSourcePart], *, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    current_heading = "Document Start"
    buffer_parts: List[ParsedSourcePart] = []

    for part in parts:
        if part.part_type == "section":
            next_index = _flush_docx_buffer(
                chunks=chunks,
                next_index=next_index,
                section_heading=current_heading,
                buffer_parts=buffer_parts,
                policy=policy,
            )
            current_heading = _section_heading(part)
            buffer_parts = [part]
            continue
        if part.part_type == "table":
            next_index = _flush_docx_buffer(
                chunks=chunks,
                next_index=next_index,
                section_heading=current_heading,
                buffer_parts=buffer_parts,
                policy=policy,
            )
            buffer_parts = []
            table_chunks = _chunk_single_part(
                start_index=next_index,
                part=part,
                section_path=f"{current_heading} > {_section_heading(part)}",
                chunk_strategy="docx_table",
                policy=policy,
            )
            chunks.extend(table_chunks)
            next_index += len(table_chunks)
            continue
        buffer_parts.append(part)

    _flush_docx_buffer(
        chunks=chunks,
        next_index=next_index,
        section_heading=current_heading,
        buffer_parts=buffer_parts,
        policy=policy,
    )
    return chunks


def _chunk_email(parts: Iterable[ParsedSourcePart], *, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        section = part.locator_json.get("section", part.part_type)
        strategy = "email_headers" if part.part_type == "email_header" else "email_body"
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=f"email:{section}",
            chunk_strategy=strategy,
            policy=policy,
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def _chunk_text_parts(parts: Iterable[ParsedSourcePart], *, source_type: str, policy: CorpusPolicy) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        if source_type == "txt":
            section_path = f"text:{part.locator_json.get('section', 'body')}"
            chunk_strategy = "txt_body"
        else:
            section_name = part.title or part.locator_json.get("section") or "body"
            section_path = f"markdown:{section_name}"
            chunk_strategy = "md_section"
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=section_path,
            chunk_strategy=chunk_strategy,
            policy=policy,
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def chunk_parsed_document(parsed: ParsedSourceDocument, *, policy_name: Optional[str] = None) -> List[Dict[str, Any]]:
    parts = list(parsed.parts)
    resolved_policy = get_corpus_policy(policy_name or parsed.metadata.get("corpus_policy"))
    if parsed.source_type == "pdf":
        chunks = _chunk_pdf(parts, policy=resolved_policy)
    elif parsed.source_type == "docx":
        chunks = _chunk_docx(parts, policy=resolved_policy)
    elif parsed.source_type == "pptx":
        chunks = _chunk_pptx(parts, policy=resolved_policy)
    elif parsed.source_type == "xlsx":
        chunks = _chunk_xlsx(parts, policy=resolved_policy)
    elif parsed.source_type == "eml":
        chunks = _chunk_email(parts, policy=resolved_policy)
    elif parsed.source_type in {"txt", "md"}:
        chunks = _chunk_text_parts(parts, source_type=parsed.source_type, policy=resolved_policy)
    else:
        chunks = []
    return [
        {
            **chunk.to_dict(),
            "provenance_json": {
                **chunk.provenance_json,
                "corpus_policy": resolved_policy.name,
                "parser_route": resolved_policy.parser_route,
                "strict_citations": resolved_policy.strict_citations,
            },
        }
        for chunk in chunks
    ]
