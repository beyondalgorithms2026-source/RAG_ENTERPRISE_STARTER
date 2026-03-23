import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.core.config import settings
from app.graph.ontology import normalize_ontology_tags


EXTRACTOR_ARTIFACT_VERSION = "m12-rule-based-extractor-v1"
_PAREN_ALIAS_PATTERN = re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)+)\s+\(([A-Z]{2,8})\)")
_ENTITY_PATTERN = re.compile(r"\b(?:[A-Z]{2,8}|[A-Z][a-z]+(?: [A-Z][A-Za-z]+){0,3})\b")
_RELATION_PATTERNS = (
    ("reports_to", re.compile(r"(?P<subject>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8}) reports to (?P<object>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8})")),
    ("works_with", re.compile(r"(?P<subject>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8}) works with (?P<object>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8})")),
    ("manages", re.compile(r"(?P<subject>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8}) manages (?P<object>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8})")),
    ("owns", re.compile(r"(?P<subject>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8}) owns (?P<object>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8})")),
    ("supports", re.compile(r"(?P<subject>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8}) supports (?P<object>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3}|[A-Z]{2,8})")),
)
_ENTITY_STOPWORDS = {"Page", "Section", "Text", "Match", "One", "Two"}


@dataclass(frozen=True)
class EnrichmentArtifacts:
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    ontology_tags: list[str] = field(default_factory=list)
    temporal_metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


def _dedupe_names(names: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for name in names:
        cleaned = re.sub(r"\s+", " ", name).strip(" ,.;:()[]{}\"'")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _build_alias_map(chunk_text: str) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    for full_name, alias in _PAREN_ALIAS_PATTERN.findall(chunk_text):
        cleaned_full = re.sub(r"\s+", " ", full_name).strip()
        alias_map[alias.strip()] = cleaned_full
        alias_map[cleaned_full] = cleaned_full
    return alias_map


def _extract_candidate_entities(chunk_text: str) -> list[str]:
    matches = [match.group(0) for match in _ENTITY_PATTERN.finditer(chunk_text)]
    candidates = []
    for name in matches:
        parts = name.split()
        if all(part in _ENTITY_STOPWORDS for part in parts):
            continue
        if len(parts) == 1 and name not in {"IBM"} and not name.isupper():
            continue
        candidates.append(name)
    return _dedupe_names(candidates)


def _extract_entities(chunk_text: str, alias_map: Dict[str, str]) -> list[dict[str, Any]]:
    entities = []
    for surface_text in _extract_candidate_entities(chunk_text):
        ontology = normalize_ontology_tags(entity_name=surface_text, alias_map=alias_map)
        entities.append(
            {
                "surface_text": surface_text,
                "canonical_name": ontology.canonical_name or surface_text,
                "entity_type": ontology.entity_type,
                "ontology_tags": ontology.tags,
                "aliases": ontology.aliases,
                "provenance": {
                    "artifact_version": EXTRACTOR_ARTIFACT_VERSION,
                    "method": "rule_based_entity_extractor",
                },
            }
        )
    return entities


def _extract_relations(chunk_text: str, alias_map: Dict[str, str]) -> list[dict[str, Any]]:
    relation_text = _PAREN_ALIAS_PATTERN.sub(r"\1", chunk_text)
    relations = []
    for relation_type, pattern in _RELATION_PATTERNS:
        for match in pattern.finditer(relation_text):
            subject_ontology = normalize_ontology_tags(entity_name=match.group("subject"), alias_map=alias_map)
            object_ontology = normalize_ontology_tags(entity_name=match.group("object"), alias_map=alias_map)
            subject_name = subject_ontology.canonical_name or match.group("subject")
            object_name = object_ontology.canonical_name or match.group("object")
            if subject_name == object_name:
                continue
            relations.append(
                {
                    "relation_type": relation_type,
                    "subject": subject_name,
                    "object": object_name,
                    "subject_surface_text": match.group("subject"),
                    "object_surface_text": match.group("object"),
                    "evidence_text": match.group(0),
                    "provenance": {
                        "artifact_version": EXTRACTOR_ARTIFACT_VERSION,
                        "method": "rule_based_relation_extractor",
                    },
                }
            )
    return relations


def run_enrichment_extractors(
    *,
    chunk_text: str,
    source_id: Optional[int] = None,
    chunk_id: Optional[int] = None,
) -> EnrichmentArtifacts:
    extraction_enabled = bool(settings.EXTRACT_ENTITIES or settings.EXTRACT_RELATIONS or settings.ENABLE_ONTOLOGY)
    if not extraction_enabled:
        return EnrichmentArtifacts(
            provenance={
                "artifact_version": EXTRACTOR_ARTIFACT_VERSION,
                "enabled": False,
                "reason": "enrichment_flags_disabled",
                "source_id": source_id,
                "chunk_id": chunk_id,
                "input_chars": len(chunk_text),
            }
        )

    alias_map = _build_alias_map(chunk_text)
    entities = _extract_entities(chunk_text, alias_map)
    relations = _extract_relations(chunk_text, alias_map) if settings.EXTRACT_RELATIONS else []
    ontology_tags = sorted({tag for entity in entities for tag in entity.get("ontology_tags", [])})

    return EnrichmentArtifacts(
        entities=entities,
        relations=relations,
        ontology_tags=ontology_tags,
        provenance={
            "artifact_version": EXTRACTOR_ARTIFACT_VERSION,
            "enabled": True,
            "reason": "m12_rule_based",
            "source_id": source_id,
            "chunk_id": chunk_id,
            "input_chars": len(chunk_text),
            "debug": {
                "alias_map": alias_map,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "ontology_tag_count": len(ontology_tags),
            },
        }
    )
