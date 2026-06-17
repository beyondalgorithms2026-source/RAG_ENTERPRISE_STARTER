from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from app.db.repo_corpora import get_corpus
from app.db.repo_sources import get_source_by_id


@dataclass(frozen=True)
class CorpusPolicy:
    name: str
    retrieval_default_mode: str
    chunk_target_words: int
    chunk_overlap_words: int
    strict_citations: bool
    parser_route: str
    structured_filters_enabled: bool = False
    transcript_metadata_enabled: bool = False
    attachment_aware: bool = False
    future_document_class_overrides: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_DEFAULT_POLICY = CorpusPolicy(
    name="default",
    retrieval_default_mode="hybrid",
    chunk_target_words=320,
    chunk_overlap_words=40,
    strict_citations=False,
    parser_route="standard_by_file_type",
)

_POLICIES: dict[str, CorpusPolicy] = {
    "default": _DEFAULT_POLICY,
    "legal": CorpusPolicy(
        name="legal",
        retrieval_default_mode="keyword",
        chunk_target_words=180,
        chunk_overlap_words=24,
        strict_citations=True,
        parser_route="legal_clause_focused",
    ),
    "transcripts": CorpusPolicy(
        name="transcripts",
        retrieval_default_mode="vector",
        chunk_target_words=220,
        chunk_overlap_words=90,
        strict_citations=False,
        parser_route="transcript_speaker_windowing",
        transcript_metadata_enabled=True,
    ),
    "db_rows": CorpusPolicy(
        name="db_rows",
        retrieval_default_mode="hybrid",
        chunk_target_words=120,
        chunk_overlap_words=16,
        strict_citations=True,
        parser_route="structured_row_serialization",
        structured_filters_enabled=True,
    ),
    "email_casework": CorpusPolicy(
        name="email_casework",
        retrieval_default_mode="hybrid",
        chunk_target_words=220,
        chunk_overlap_words=36,
        strict_citations=True,
        parser_route="header_body_attachment_aware",
        attachment_aware=True,
    ),
}


def get_corpus_policy(policy_name: Optional[str]) -> CorpusPolicy:
    normalized = str(policy_name or "").strip().lower()
    return _POLICIES.get(normalized, _DEFAULT_POLICY)


def resolve_policy_name_from_source_metadata(source_metadata: Optional[Dict[str, Any]]) -> str:
    metadata = dict(source_metadata or {})
    explicit_policy = str(metadata.get("corpus_policy") or "").strip().lower()
    if explicit_policy:
        return explicit_policy

    corpus_name = str(metadata.get("corpus") or "").strip()
    if corpus_name:
        corpus = get_corpus(corpus_name)
        if corpus:
            corpus_metadata = dict(corpus.get("metadata_json") or {})
            corpus_policy = str(corpus_metadata.get("policy") or corpus_name).strip().lower()
            if corpus_policy:
                return corpus_policy

    return "default"


def get_source_corpus_policy(source_id: Optional[int]) -> CorpusPolicy:
    if source_id is None:
        return _DEFAULT_POLICY
    source = get_source_by_id(source_id)
    if source is None:
        return _DEFAULT_POLICY
    return get_corpus_policy(resolve_policy_name_from_source_metadata(source.source_metadata_json))

