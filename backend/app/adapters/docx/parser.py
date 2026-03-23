from io import BytesIO
from typing import Iterator, Tuple

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph
from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


def _iter_block_items(document: DocumentObject) -> Iterator[Tuple[str, object]]:
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield "paragraph", Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield "table", Table(child, document)


def parse_docx_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    parts = []
    warnings = []
    document = Document(BytesIO(content))
    paragraph_count = 0
    table_count = 0
    for part_index, (block_type, block) in enumerate(_iter_block_items(document)):
        if block_type == "paragraph":
            paragraph = block
            paragraph_text = paragraph.text.strip()
            if not paragraph_text:
                continue
            style_name = paragraph.style.name if paragraph.style is not None else None
            is_heading = bool(style_name and style_name.lower().startswith("heading"))
            parts.append(
                ParsedSourcePart(
                    part_type="section" if is_heading else "paragraph",
                    part_index=part_index,
                    title=paragraph_text if is_heading else None,
                    locator_json={"block": part_index + 1, "paragraph": paragraph_count + 1, "style": style_name},
                    content_text=paragraph_text,
                    provenance_json={"parser": "python-docx", "file_name": file_name},
                )
            )
            paragraph_count += 1
            continue
        table = block
        row_texts = []
        for row_index, row in enumerate(table.rows, start=1):
            cells = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
            if cells:
                row_texts.append(f"Row {row_index}: " + " | ".join(cells))
        table_text = "\n".join(row_texts).strip()
        if not table_text:
            continue
        parts.append(
            ParsedSourcePart(
                part_type="table",
                part_index=part_index,
                title=f"Table {table_count + 1}",
                locator_json={"block": part_index + 1, "table": table_count + 1},
                content_text=table_text,
                provenance_json={"parser": "python-docx", "file_name": file_name},
            )
        )
        table_count += 1

    if not parts:
        warnings.append("No DOCX content blocks with extractable text were found.")

    return ParsedSourceDocument(
        source_type="docx",
        title=file_name,
        metadata={
            "file_name": file_name,
            "paragraph_count": paragraph_count,
            "table_count": table_count,
            "section_count": sum(1 for part in parts if part.part_type == "section"),
        },
        parts=parts,
        warnings=warnings,
    )
