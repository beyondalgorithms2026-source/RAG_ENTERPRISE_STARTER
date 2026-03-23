# Parser Capability Matrix

Active technical reference.

See also:
- [docs/README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/README.md)
- [docs/module_map.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)

This document captures the current parser adapter coverage implemented in `backend/app/adapters/`.

## Supported currently

| Source Type | Adapter Path | Canonical Part Types | Locator Shape | Notes |
|---|---|---|---|---|
| PDF | `backend/app/adapters/pdf/` | `page` | `{"page": n}` | Uses `pypdf` for digital PDF page-by-page text extraction |
| DOCX | `backend/app/adapters/docx/` | `section`, `paragraph`, `table` | `{"block": n, ...}` | Uses `python-docx` to preserve document-order paragraphs and tables |
| PPTX | `backend/app/adapters/pptx/` | `slide` | `{"slide": n}` | Uses `python-pptx` for slide text and notes extraction |
| XLSX | `backend/app/adapters/xlsx/` | `sheet` | `{"sheet": "Sheet1", "range": "A1:C4"}` | Uses `openpyxl` for workbook/sheet/cell extraction |
| EML | `backend/app/adapters/email/` | `email_header`, `email_body` | `{"section": "...", "body_format": "..."}` | Uses stdlib email parsing plus BeautifulSoup HTML fallback text handling |
| TXT | `backend/app/adapters/txt/` | `text_block` | `{"section": "body"}` | Decodes plain text, normalizes line endings, and preserves body text without invented structure |
| MD | `backend/app/adapters/md/` | `section`, `text_block` | `{"section": "...", "heading_level": n}` | Lightweight heading-aware parsing for `#`, `##`, `###`; links, lists, and code fences remain literal text |

## Canonical Representation

All M5 adapters normalize into one shared internal shape:

- `ParsedSourceDocument`
- `ParsedSourcePart`
- `ParsedAttachment`

This shape is designed to remain compatible with the current `source_parts`-oriented schema without introducing M6 chunking behavior.

## Explicit M5 Limits

- MSG adapter is not implemented in M5.
- PDF support is limited to digital/text PDFs and does not include OCR for scanned/image-only files.
- Debug artifact persistence is optional and disabled by default.
- Chunking, embedding, retrieval, and UI behavior remain out of scope for this milestone.
- DOCX extraction is parser-level only; it does not yet create citation-safe chunk boundaries.
- PPTX extraction preserves slide-level text and notes, not full visual layout semantics.
- XLSX extraction preserves workbook/sheet/cell values, not spreadsheet formulas as formulas or chart semantics.
- EML extraction preserves strong header/body/attachment metadata with HTML fallback text, but not attachment content parsing.
- TXT extraction is plain-text only and does not infer richer document structure.
- Markdown extraction is text-first only; it does not render HTML, build a full markdown AST, or add special semantics for tables, lists, or fenced code blocks.
