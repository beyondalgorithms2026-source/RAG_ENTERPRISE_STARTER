from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParsedSourcePart:
    part_type: str
    part_index: int
    title: str | None = None
    locator_json: dict[str, Any] = field(default_factory=dict)
    content_text: str = ""
    provenance_json: dict[str, Any] = field(default_factory=dict)
    parent_part_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedAttachment:
    file_name: str
    content_type: str | None = None
    size_bytes: int = 0
    content_disposition: str | None = None
    content_id: str | None = None
    content_bytes: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("content_bytes", None)
        return payload


@dataclass
class ParsedSourceDocument:
    source_type: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parts: list[ParsedSourcePart] = field(default_factory=list)
    attachments: list[ParsedAttachment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "title": self.title,
            "metadata": self.metadata,
            "parts": [part.to_dict() for part in self.parts],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "warnings": list(self.warnings),
        }
