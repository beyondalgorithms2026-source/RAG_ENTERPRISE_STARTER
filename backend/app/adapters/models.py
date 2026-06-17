from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedSourcePart:
    part_type: str
    part_index: int
    title: Optional[str] = None
    locator_json: Dict[str, Any] = field(default_factory=dict)
    content_text: str = ""
    provenance_json: Dict[str, Any] = field(default_factory=dict)
    parent_part_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedAttachment:
    file_name: str
    content_type: Optional[str] = None
    size_bytes: int = 0
    content_disposition: Optional[str] = None
    content_id: Optional[str] = None
    content_bytes: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("content_bytes", None)
        return payload


@dataclass
class ParsedSourceDocument:
    source_type: str
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parts: List[ParsedSourcePart] = field(default_factory=list)
    attachments: List[ParsedAttachment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "title": self.title,
            "metadata": self.metadata,
            "parts": [part.to_dict() for part in self.parts],
            "attachments": [attachment.to_dict() for attachment in self.attachments],
            "warnings": list(self.warnings),
        }
