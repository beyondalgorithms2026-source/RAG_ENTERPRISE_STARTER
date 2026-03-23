import re
from typing import List, Optional

from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _decode_text(content: bytes) -> str:
    return content.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def _append_part(
    parts: List[ParsedSourcePart],
    *,
    title: Optional[str],
    heading_level: Optional[int],
    lines: List[str],
    file_name: str,
) -> None:
    body_text = "\n".join(lines).strip()
    if not title and not body_text:
        return
    locator = {"section": title or "body"}
    if heading_level is not None:
        locator["heading_level"] = heading_level
    parts.append(
        ParsedSourcePart(
            part_type="section" if title else "text_block",
            part_index=len(parts),
            title=title,
            locator_json=locator,
            content_text=body_text or (title or ""),
            provenance_json={"parser": "markdown_lightweight", "file_name": file_name},
        )
    )


def parse_md_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    text = _decode_text(content)
    parts: List[ParsedSourcePart] = []
    current_title: Optional[str] = None
    current_level: Optional[int] = None
    current_lines: List[str] = []

    for raw_line in text.split("\n"):
        heading_match = _HEADING_RE.match(raw_line)
        if heading_match:
            _append_part(
                parts,
                title=current_title,
                heading_level=current_level,
                lines=current_lines,
                file_name=file_name,
            )
            current_title = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = []
            continue
        current_lines.append(raw_line)

    _append_part(
        parts,
        title=current_title,
        heading_level=current_level,
        lines=current_lines,
        file_name=file_name,
    )

    warnings = []
    if not parts:
        warnings.append("No Markdown body text found.")

    heading_count = sum(1 for part in parts if part.part_type == "section")
    return ParsedSourceDocument(
        source_type="md",
        title=file_name,
        metadata={"file_name": file_name, "heading_count": heading_count, "part_count": len(parts)},
        parts=parts,
        warnings=warnings,
    )
