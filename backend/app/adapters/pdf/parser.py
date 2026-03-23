from io import BytesIO

from pypdf import PdfReader
from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


def parse_pdf_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    reader = PdfReader(BytesIO(content))
    warnings = []
    parts = []
    for index, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if not text:
            warnings.append(f"Page {index + 1} did not yield extractable digital text.")
        parts.append(
            ParsedSourcePart(
                part_type="page",
                part_index=index,
                title=f"Page {index + 1}",
                locator_json={"page": index + 1},
                content_text=text,
                provenance_json={"parser": "pypdf", "file_name": file_name},
            )
        )

    return ParsedSourceDocument(
        source_type="pdf",
        title=file_name,
        metadata={"file_name": file_name, "page_count": len(reader.pages)},
        parts=parts,
        warnings=warnings,
    )
