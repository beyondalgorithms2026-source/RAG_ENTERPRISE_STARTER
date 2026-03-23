from pathlib import Path
from typing import Callable, Dict

from .md import parse_md_bytes
from .email import parse_eml_bytes
from .models import ParsedSourceDocument
from .docx import parse_docx_bytes
from .pdf import parse_pdf_bytes
from .pptx import parse_pptx_bytes
from .txt import parse_txt_bytes
from .xlsx import parse_xlsx_bytes


AdapterFn = Callable[[bytes, str], ParsedSourceDocument]


_ADAPTERS: Dict[str, AdapterFn] = {
    "pdf": parse_pdf_bytes,
    "docx": parse_docx_bytes,
    "pptx": parse_pptx_bytes,
    "xlsx": parse_xlsx_bytes,
    "eml": parse_eml_bytes,
    "txt": parse_txt_bytes,
    "md": parse_md_bytes,
}


def get_adapter(source_type: str) -> AdapterFn:
    try:
        return _ADAPTERS[source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported source type: {source_type}") from exc


def parse_source_bytes(source_type: str, content: bytes, file_name: str) -> ParsedSourceDocument:
    adapter = get_adapter(source_type)
    return adapter(content, file_name)


def detect_source_type_from_path(file_path: str) -> str:
    return Path(file_path).suffix.lower().lstrip(".")
