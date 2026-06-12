"""Eval pack builder (AR3).

Builds graded, labeled retrieval eval packs from two evidence sources:

1. **Chunk-grounded synthesis** — deterministic question variants derived from
   real corpus chunks. The source chunk is graded 3; same-source neighbor
   chunks are graded 1. Lexical bias is acknowledged: synthesized questions
   share vocabulary with their chunk, so they primarily measure ranking and
   candidate-pool regressions, not paraphrase robustness (that requires the
   human labeling workflow in docs/runbooks/EVAL_PACK_LABELING.md).
2. **Mined query events** — real questions from the M20 mining tables, junk-
   filtered, with relevance derived from the recorded trace's accessed chunks
   (grade 2). Derived cases carry review_status="unreviewed" until a human
   reviews them (AR12 quarantine rule: unreviewed cases are reported but do
   not gate).

Run: python -m app.eval.pack_builder  (writes backend/eval_packs/pack_*.json)
"""
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text

from app.db.db import engine

BUILDER_VERSION = "ar3.1"
PACKS_DIR = Path(__file__).resolve().parents[2] / "eval_packs"

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are", "was", "were", "have", "has",
    "had", "not", "but", "all", "can", "will", "into", "over", "under", "its", "their", "his",
    "her", "our", "your", "they", "them", "then", "than", "also", "been", "being", "would",
    "could", "should", "there", "here", "what", "when", "where", "which", "while", "about",
}

_JUNK_QUESTION_PATTERNS = [
    re.compile(r"[0-9a-f]{16,}", re.IGNORECASE),  # uuid-suffixed synthetic test questions
    re.compile(r"^\[redacted", re.IGNORECASE),
    re.compile(r"^missing (payroll policy|evidence)", re.IGNORECASE),
    re.compile(r"^m\d+ (answer|compare|eval) ", re.IGNORECASE),
    re.compile(r"keywordbanana|alpha semantic vector match", re.IGNORECASE),
]


def _salient_terms(chunk_text: str, limit: int = 4) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", chunk_text.lower())
    counted = Counter(word for word in words if word not in _STOPWORDS)
    return [word for word, _ in counted.most_common(limit)]


def _first_sentence(chunk_text: str, max_chars: int = 140) -> str:
    cleaned = re.sub(r"\s+", " ", chunk_text).strip()
    match = re.split(r"(?<=[.!?])\s", cleaned, maxsplit=1)
    sentence = match[0] if match else cleaned
    return sentence[:max_chars].strip()


def is_junk_mined_question(question: str) -> bool:
    cleaned = (question or "").strip()
    if len(cleaned) < 12:
        return True
    return any(pattern.search(cleaned) for pattern in _JUNK_QUESTION_PATTERNS)


def synthesize_question_variants(*, heading: str, chunk_text: str, file_name: str) -> list[dict[str, str]]:
    terms = _salient_terms(chunk_text)
    if not terms:
        return []
    variants: list[dict[str, str]] = []
    sentence = _first_sentence(chunk_text)
    if len(sentence.split()) >= 5:
        variants.append({"style": "lead_sentence", "question": sentence})
    topic = " ".join(terms[:3])
    heading_clean = re.sub(r"\s+", " ", heading or "").strip()
    if heading_clean:
        variants.append({"style": "heading_topic", "question": f"{heading_clean}: what is stated about {topic}?"})
    variants.append({"style": "salient_terms", "question": " ".join(terms)})
    return variants


def _corpus_filter_sql(corpus: Optional[str]) -> str:
    if corpus is None:
        return "COALESCE(s.source_metadata_json->>'corpus', '') = ''"
    return "s.source_metadata_json->>'corpus' = :corpus"


def build_synthetic_cases(*, corpus: Optional[str], max_cases: int, min_chunk_words: int = 25) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if corpus is not None:
        params["corpus"] = corpus
    sql = text(
        f"""
        SELECT ch.id, ch.source_id, ch.chunk_index, ch.heading, ch.chunk_text, s.file_name
        FROM chunks ch
        JOIN sources s ON s.id = ch.source_id
        WHERE {_corpus_filter_sql(corpus)}
          AND ch.embedding IS NOT NULL
        ORDER BY ch.source_id ASC, ch.chunk_index ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    neighbors: dict[tuple[int, int], int] = {(row[1], row[2]): row[0] for row in rows}
    cases: list[dict[str, Any]] = []
    for chunk_id, source_id, chunk_index, heading, chunk_text, file_name in rows:
        if len((chunk_text or "").split()) < min_chunk_words:
            continue
        relevant: dict[str, int] = {str(chunk_id): 3}
        for offset in (-1, 1):
            neighbor_id = neighbors.get((source_id, chunk_index + offset))
            if neighbor_id is not None:
                relevant[str(neighbor_id)] = 1
        for variant in synthesize_question_variants(heading=heading or "", chunk_text=chunk_text or "", file_name=file_name or ""):
            cases.append(
                {
                    "id": f"syn-{chunk_id}-{variant['style']}",
                    "question": variant["question"],
                    "provenance": "synthetic_chunk_grounded",
                    "variant_style": variant["style"],
                    "review_status": "auto_labeled",
                    "relevant": relevant,
                    "source_id": source_id,
                    "file_name": file_name,
                }
            )
            if len(cases) >= max_cases:
                return cases
    return cases


def build_mined_cases(*, max_cases: int) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT DISTINCT ON (qe.normalized_question)
               qe.question, qe.normalized_question, qe.retrieval_mode, rt.trace_json
        FROM query_events qe
        JOIN retrieval_traces rt ON rt.request_id = qe.request_id
        WHERE qe.question IS NOT NULL
        ORDER BY qe.normalized_question, qe.id DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    cases: list[dict[str, Any]] = []
    for question, normalized, retrieval_mode, trace_json in rows:
        if is_junk_mined_question(question):
            continue
        trace = trace_json or {}
        accessed = ((trace.get("acl") or {}).get("accessed_doc_ids") or []) if isinstance(trace, dict) else []
        cited_chunks = trace.get("cited_chunk_ids") if isinstance(trace, dict) else None
        relevant: dict[str, int] = {}
        for chunk_id in cited_chunks or []:
            relevant[str(chunk_id)] = 2
        if not relevant:
            continue  # no chunk-level evidence: needs human labeling, skip
        cases.append(
            {
                "id": f"mined-{abs(hash(normalized)) % 10**10}",
                "question": question,
                "provenance": "mined_query_event",
                "review_status": "unreviewed",
                "relevant": relevant,
                "retrieval_mode": retrieval_mode,
                "accessed_doc_ids": accessed,
            }
        )
        if len(cases) >= max_cases:
            break
    return cases


def build_pack(*, pack_name: str, corpus: Optional[str], max_synthetic: int = 400, max_mined: int = 200) -> dict[str, Any]:
    synthetic = build_synthetic_cases(corpus=corpus, max_cases=max_synthetic)
    mined = build_mined_cases(max_cases=max_mined) if corpus is None else []
    return {
        "pack": pack_name,
        "corpus": corpus or "general",
        "builder_version": BUILDER_VERSION,
        "built_at": int(time.time()),
        "case_counts": {
            "synthetic_chunk_grounded": len(synthetic),
            "mined_query_event": len(mined),
            "total": len(synthetic) + len(mined),
        },
        "cases": synthetic + mined,
    }


def write_pack(pack: dict[str, Any], directory: Path = PACKS_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"pack_{pack['pack']}.json"
    path.write_text(json.dumps(pack, indent=1) + "\n", encoding="utf-8")
    return path


def build_default_packs() -> list[Path]:
    targets = [("general", None), ("legal", "legal"), ("db_rows", "db_rows"), ("transcripts", "transcripts")]
    written: list[Path] = []
    for pack_name, corpus in targets:
        pack = build_pack(pack_name=pack_name, corpus=corpus)
        if pack["case_counts"]["total"] == 0:
            continue
        written.append(write_pack(pack))
    return written


if __name__ == "__main__":
    for path in build_default_packs():
        print(path)
