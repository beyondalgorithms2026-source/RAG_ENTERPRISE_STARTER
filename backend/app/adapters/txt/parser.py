from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


def _decode_text(content: bytes) -> str:
    return content.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def parse_txt_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    text = _decode_text(content).strip()
    parts = []
    warnings = []
    if text:
        parts.append(
            ParsedSourcePart(
                part_type="text_block",
                part_index=0,
                title=None,
                locator_json={"section": "body"},
                content_text=text,
                provenance_json={"parser": "plain_text", "file_name": file_name},
            )
        )
    else:
        warnings.append("No TXT body text found.")

    return ParsedSourceDocument(
        source_type="txt",
        title=file_name,
        metadata={"file_name": file_name, "line_count": len(text.splitlines()) if text else 0},
        parts=parts,
        warnings=warnings,
    )
