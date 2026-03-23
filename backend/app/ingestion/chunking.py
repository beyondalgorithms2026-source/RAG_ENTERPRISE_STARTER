from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


MIN_WORDS = 120
TARGET_WORDS = 320
OVERLAP_WORDS = 40


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
) -> List[ChunkRecord]:
    text = _normalize_text(part.content_text)
    if not text:
        return []
    heading = _section_heading(part)
    windows = _split_word_windows(text)
    chunks: List[ChunkRecord] = []
    for offset, window in enumerate(windows):
        locator = _base_locator(part)
        if len(windows) > 1:
            locator["chunk_window"] = offset + 1
            locator["chunk_window_total"] = len(windows)
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


def _chunk_pdf(parts: Iterable[ParsedSourcePart]) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=f"page:{part.locator_json.get('page', part.part_index + 1)}",
            chunk_strategy="pdf_page",
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def _chunk_pptx(parts: Iterable[ParsedSourcePart]) -> List[ChunkRecord]:
    chunks: List[ChunkRecord] = []
    next_index = 0
    for part in parts:
        slide_number = part.locator_json.get("slide", part.part_index + 1)
        part_chunks = _chunk_single_part(
            start_index=next_index,
            part=part,
            section_path=f"slide:{slide_number}",
            chunk_strategy="pptx_slide",
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def _chunk_xlsx(parts: Iterable[ParsedSourcePart]) -> List[ChunkRecord]:
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
            if len(joined.split()) >= TARGET_WORDS:
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
) -> int:
    if not buffer_parts:
        return next_index
    combined = "\n\n".join(_normalize_text(part.content_text) for part in buffer_parts if _normalize_text(part.content_text)).strip()
    if not combined:
        return next_index

    first_part = buffer_parts[0]
    windows = _split_word_windows(combined)
    for offset, window in enumerate(windows):
        locator = _base_locator(first_part)
        locator["docx_part_indices"] = [part.part_index for part in buffer_parts]
        if len(windows) > 1:
            locator["chunk_window"] = offset + 1
            locator["chunk_window_total"] = len(windows)
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


def _chunk_docx(parts: Iterable[ParsedSourcePart]) -> List[ChunkRecord]:
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
            )
            buffer_parts = []
            table_chunks = _chunk_single_part(
                start_index=next_index,
                part=part,
                section_path=f"{current_heading} > {_section_heading(part)}",
                chunk_strategy="docx_table",
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
    )
    return chunks


def _chunk_email(parts: Iterable[ParsedSourcePart]) -> List[ChunkRecord]:
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
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def _chunk_text_parts(parts: Iterable[ParsedSourcePart], *, source_type: str) -> List[ChunkRecord]:
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
        )
        chunks.extend(part_chunks)
        next_index += len(part_chunks)
    return chunks


def chunk_parsed_document(parsed: ParsedSourceDocument) -> List[Dict[str, Any]]:
    parts = list(parsed.parts)
    if parsed.source_type == "pdf":
        chunks = _chunk_pdf(parts)
    elif parsed.source_type == "docx":
        chunks = _chunk_docx(parts)
    elif parsed.source_type == "pptx":
        chunks = _chunk_pptx(parts)
    elif parsed.source_type == "xlsx":
        chunks = _chunk_xlsx(parts)
    elif parsed.source_type == "eml":
        chunks = _chunk_email(parts)
    elif parsed.source_type in {"txt", "md"}:
        chunks = _chunk_text_parts(parts, source_type=parsed.source_type)
    else:
        chunks = []
    return [chunk.to_dict() for chunk in chunks]
