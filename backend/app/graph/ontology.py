import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.core.config import settings


ONTOLOGY_ARTIFACT_VERSION = "m12-ontology-v1"
_ORG_SUFFIXES = {"Corp", "Corporation", "Inc", "LLC", "Ltd", "Company", "Co"}


@dataclass(frozen=True)
class OntologyResult:
    canonical_name: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    entity_type: str = "entity"
    tags: list[str] = field(default_factory=list)
    enabled: bool = False
    reason: str = "ontology_disabled"
    artifact_version: str = ONTOLOGY_ARTIFACT_VERSION


def _clean_entity_name(entity_name: str) -> str:
    return re.sub(r"\s+", " ", entity_name).strip(" ,.;:()[]{}\"'")


def _infer_entity_type(entity_name: str) -> str:
    if entity_name.startswith("Project "):
        return "project"
    parts = entity_name.split()
    if parts and parts[-1] in _ORG_SUFFIXES:
        return "organization"
    if entity_name.isupper() and 2 <= len(entity_name) <= 8:
        return "organization"
    if len(parts) == 2 and all(part[:1].isupper() for part in parts):
        return "person"
    return "entity"


def normalize_ontology_tags(
    *,
    candidate_tags: Optional[list[str]] = None,
    entity_name: Optional[str] = None,
    alias_map: Optional[Dict[str, str]] = None,
) -> OntologyResult:
    cleaned_name = _clean_entity_name(entity_name) if entity_name else None
    canonical_name = alias_map.get(cleaned_name, cleaned_name) if cleaned_name and alias_map else cleaned_name
    aliases = []
    if cleaned_name:
        aliases.append(cleaned_name)
    if canonical_name and canonical_name not in aliases:
        aliases.append(canonical_name)

    entity_type = _infer_entity_type(canonical_name or cleaned_name or "entity")
    if not settings.ENABLE_ONTOLOGY:
        return OntologyResult(
            canonical_name=canonical_name,
            aliases=aliases,
            entity_type=entity_type,
        )

    tags = list(candidate_tags or [])
    if entity_type not in tags:
        tags.append(entity_type)
    return OntologyResult(
        canonical_name=canonical_name,
        aliases=aliases,
        entity_type=entity_type,
        tags=tags,
        enabled=True,
        reason="m12_rule_based",
    )
