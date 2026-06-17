import zipfile
from io import BytesIO

from app.core.config import settings


_ZIP_BACKED_TYPES = {"docx", "pptx", "xlsx"}
_NESTED_ARCHIVE_EXTENSIONS = (".zip", ".7z", ".rar", ".tar", ".gz")


def validate_parser_input(source_type: str, content: bytes, file_name: str) -> None:
    if source_type not in _ZIP_BACKED_TYPES:
        return
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > settings.PARSER_MAX_ARCHIVE_FILES:
                raise ValueError(f"Unsafe archive: too many entries in {file_name}")
            expanded_bytes = sum(max(info.file_size, 0) for info in infos)
            compressed_bytes = sum(max(info.compress_size, 1) for info in infos)
            if expanded_bytes > settings.PARSER_MAX_EXPANDED_BYTES:
                raise ValueError(f"Unsafe archive: expanded size exceeds limit for {file_name}")
            ratio = expanded_bytes / max(compressed_bytes, 1)
            if ratio > settings.PARSER_MAX_COMPRESSION_RATIO:
                raise ValueError(f"Unsafe archive: compression ratio exceeds limit for {file_name}")
            nested = [info.filename for info in infos if info.filename.lower().endswith(_NESTED_ARCHIVE_EXTENSIONS)]
            if nested:
                raise ValueError(f"Unsafe archive: nested archive entries are not allowed in {file_name}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid archive-backed document: {file_name}") from exc
