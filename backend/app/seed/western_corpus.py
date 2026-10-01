"""Seed the synthetic Northline Analytics (Western) corpus.

The documents in `corpus/western/` and the manifest in `eval/western/MANIFEST.csv` are
produced outside this repository. This module validates them and loads them through the
same repository-layer path as the Northwind pack (`app.seed.public_demo`): sources,
chunks, ACL grants, then `process_embeddings`. It never edits the files.

    cd backend
    python -m app.seed.western_corpus --dry-run            # validate, chunk, estimate cost; no DB, no API
    python -m app.seed.western_corpus --apply              # write sources/chunks/ACL, embed new chunks
    python -m app.seed.western_corpus --wipe --confirm western_northline

Sources are tagged `source_metadata_json.corpus = "western_northline"` so a request can
be scoped to this corpus (see `app.core_rag.corpus_scope`).

Access model
------------
Manifest classifications map onto the demo's labels. Anonymous visitors retrieve only
`public`. `NL-SEC-DATA-RETENTION-2026` is published although the manifest marks it
Confidential, because the owner selected it as a public demo document; the incident SOP
stays restricted so the corpus shows an access-controlled refusal.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, settings
from app.core.logging import log_event
from app.seed.public_demo import _chunks_for_document

SEED_PACK = "western_northline"
CORPUS = "western_northline"
COMPANY = "Northline Analytics Ltd"
BUCKET_LABEL = "Northline Analytics (US/EU)"
ALL_EMPLOYEES = "all-employees"
PARSER_ROUTE = "production_markdown"

CORPUS_DIR = Path(REPO_ROOT) / "corpus" / "western"
MANIFEST_PATH = Path(REPO_ROOT) / "eval" / "western" / "MANIFEST.csv"
STORAGE_PREFIX = "corpus/western"

CLASSIFICATION_MAP = {"Internal": "public", "Confidential": "restricted"}
CLASSIFICATION_OVERRIDES = {"NL-SEC-DATA-RETENTION-2026": "public"}
# Listed in the manifest but, per eval/western/EVAL_README.md, not searchable policy.
EXCLUDED_IDS = {"NL-CORPUS-NOTES-2026"}

OWNER_GROUP_BY_PREFIX = {
    "HR": "people-operations",
    "FIN": "finance",
    "PROC": "finance",
    "SEC": "security",
    "OPS": "operations",
    "CS": "operations",
    "POLICY": "legal",
    "TEST": "security",
}

# This corpus must stay free of Indian tax/payroll identifiers (Track B scope).
GST_INDIA_GUARD = re.compile(r"\b(?:GSTIN|GST|HSN|SAC|PAN|IFSC|INR|EPF|India|Indian)\b|₹")

EMBEDDING_USD_PER_MILLION_TOKENS = 0.02


class WesternCorpusError(ValueError):
    """The Western corpus files are missing, inconsistent, or out of scope."""


@dataclass(frozen=True)
class WesternDocument:
    doc_id: str
    filename: str
    path: Path
    content: str
    indexed_text: str
    classification: str
    source_classification: str
    owner_group: str
    front_matter: dict[str, str] = field(default_factory=dict)

    @property
    def storage_path(self) -> str:
        return f"{STORAGE_PREFIX}/{self.filename}"

    @property
    def content_sha256(self) -> str:
        return sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def title(self) -> str:
        return self.front_matter.get("title") or self.doc_id

    @property
    def test_fixture(self) -> bool:
        return self.front_matter.get("doc_type") == "test_fixture"


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    """Return (front matter, text to index).

    Files start with a `SYNTHETIC` marker, then a `---` block of `key: value` lines.
    Both are metadata (recorded as `synthetic: true` and source metadata), so neither is
    indexed as a chunk of its own; the file on disk is unchanged.
    """
    match = re.match(r"\A(?:[^\n]*\n)*?---\n(?P<meta>.*?)\n---\n", content, re.S)
    if not match:
        return {}, content
    front_matter: dict[str, str] = {}
    for line in match.group("meta").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            front_matter[key.strip()] = value.strip()
    return front_matter, content[match.end() :].lstrip("\n")


def _owner_group(doc_id: str) -> str:
    parts = doc_id.split("-")
    prefix = parts[1] if len(parts) > 1 else ""
    group = OWNER_GROUP_BY_PREFIX.get(prefix)
    if group is None:
        raise WesternCorpusError(f"{doc_id}: no owner group for id prefix {prefix!r}")
    return group


def _guard_hits(text: str) -> list[str]:
    return sorted({match.group(0) for match in GST_INDIA_GUARD.finditer(text)})


def load_documents(
    corpus_dir: Path = CORPUS_DIR, manifest_path: Path = MANIFEST_PATH
) -> list[WesternDocument]:
    """Validate the manifest against the files and return the documents to seed.

    Fails closed: any problem is reported before anything is written.
    """
    if not manifest_path.exists():
        raise WesternCorpusError(f"No manifest at {manifest_path}")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    problems: list[str] = []
    documents: list[WesternDocument] = []
    seen_ids: set[str] = set()
    listed_files: set[str] = set()

    for index, row in enumerate(rows, start=2):
        doc_id = (row.get("id") or "").strip()
        filename = (row.get("filename") or "").strip()
        if not doc_id or not filename:
            problems.append(f"manifest line {index}: id and filename are required")
            continue
        if doc_id in seen_ids:
            problems.append(f"manifest line {index}: duplicate id {doc_id}")
            continue
        seen_ids.add(doc_id)
        if doc_id in EXCLUDED_IDS:
            continue
        listed_files.add(filename)
        hits = _guard_hits(" ".join(str(value or "") for value in row.values()))
        if hits:
            problems.append(f"{doc_id}: manifest row matches GST/India guard {hits}")

        path = corpus_dir / filename
        if Path(filename).name != filename or path.suffix != ".md":
            problems.append(f"{doc_id}: filename must be a plain .md name, got {filename!r}")
            continue
        if not path.exists():
            problems.append(f"{doc_id}: file not found: {filename}")
            continue

        source_classification = (row.get("classification") or "").strip()
        classification = CLASSIFICATION_OVERRIDES.get(
            doc_id, CLASSIFICATION_MAP.get(source_classification)
        )
        if classification is None:
            problems.append(f"{doc_id}: unknown classification {source_classification!r}")
            continue

        content = path.read_text(encoding="utf-8")
        front_matter, indexed_text = _split_front_matter(content)
        if front_matter.get("id") and front_matter["id"] != doc_id:
            problems.append(f"{doc_id}: front matter id is {front_matter['id']!r}")
        if front_matter.get("classification") not in {None, source_classification}:
            problems.append(
                f"{doc_id}: front matter classification {front_matter.get('classification')!r} "
                f"disagrees with manifest {source_classification!r}"
            )
        hits = _guard_hits(content)
        if hits:
            problems.append(f"{doc_id}: document matches GST/India guard {hits}")
        if not indexed_text.strip():
            problems.append(f"{doc_id}: document has no text to index")

        try:
            owner_group = _owner_group(doc_id)
        except WesternCorpusError as exc:
            problems.append(str(exc))
            continue

        documents.append(
            WesternDocument(
                doc_id=doc_id,
                filename=filename,
                path=path,
                content=content,
                indexed_text=indexed_text,
                classification=classification,
                source_classification=source_classification,
                owner_group=owner_group,
                front_matter=front_matter,
            )
        )

    if corpus_dir.exists():
        for path in sorted(corpus_dir.glob("*.md")):
            if path.name not in listed_files:
                problems.append(f"{path.name}: present in corpus/western but not in the manifest")

    if problems:
        raise WesternCorpusError("Western corpus validation failed:\n  - " + "\n  - ".join(problems))
    return documents


def _chunks(document: WesternDocument) -> list[dict[str, Any]]:
    chunks = _chunks_for_document(
        content=document.indexed_text, file_name=document.filename, parser_route=PARSER_ROUTE
    )
    for chunk in chunks:
        provenance = dict(chunk.get("provenance_json") or {})
        provenance.update({"seed_pack": SEED_PACK, "doc_id": document.doc_id})
        chunk["provenance_json"] = provenance
    return chunks


def _estimated_tokens(text: str) -> int:
    # A deliberately conservative approximation; the provider bills actual tokens.
    return max(1, len(text) // 4)


def dry_run(documents: list[WesternDocument]) -> dict[str, Any]:
    """Chunk every document and estimate embedding cost without touching DB or API."""
    per_document = []
    total_tokens = 0
    for document in documents:
        chunks = _chunks(document)
        tokens = sum(_estimated_tokens(chunk["chunk_text"]) for chunk in chunks)
        total_tokens += tokens
        per_document.append(
            {
                "doc_id": document.doc_id,
                "classification": document.classification,
                "source_classification": document.source_classification,
                "owner_group": document.owner_group,
                "test_fixture": document.test_fixture,
                "chunks": len(chunks),
                "estimated_tokens": tokens,
            }
        )
    return {
        "mode": "dry_run",
        "corpus": CORPUS,
        "documents": len(documents),
        "chunks": sum(item["chunks"] for item in per_document),
        "estimated_embedding_tokens": total_tokens,
        "estimated_embedding_usd": round(
            total_tokens * EMBEDDING_USD_PER_MILLION_TOKENS / 1_000_000, 6
        ),
        "classification_counts": {
            label: sum(1 for item in per_document if item["classification"] == label)
            for label in sorted({item["classification"] for item in per_document})
        },
        "per_document": per_document,
    }


def _source_metadata(document: WesternDocument) -> dict[str, Any]:
    return {
        "seed_pack": SEED_PACK,
        "corpus": CORPUS,
        "company": COMPANY,
        "bucket_label": BUCKET_LABEL,
        "synthetic": True,
        "classification": document.classification,
        "source_classification": document.source_classification,
        "owner_group": document.owner_group,
        "title": document.title,
        "doc_id": document.doc_id,
        "doc_type": document.front_matter.get("doc_type"),
        "jurisdiction": document.front_matter.get("jurisdiction"),
        "effective": document.front_matter.get("effective"),
        "supersedes": document.front_matter.get("supersedes"),
        "test_fixture": document.test_fixture,
        "parser_route": PARSER_ROUTE,
        "source_file": document.doc_id,
    }


def apply(documents: list[WesternDocument], *, embed: bool = True) -> dict[str, Any]:
    from app.db.repo_acl import ensure_group, replace_source_acl
    from app.db.repo_chunks import check_chunks_exist, delete_chunks_for_source, insert_chunks
    from app.db.repo_sources import (
        get_source_by_seed_identity,
        update_source_storage_path,
        upsert_source,
    )

    for group in {ALL_EMPLOYEES, *(document.owner_group for document in documents)}:
        ensure_group(group)

    stats: dict[str, Any] = {"sources": 0, "chunks": 0, "unchanged": 0, "restricted": 0}
    source_ids: list[int] = []
    for document in documents:
        existing = get_source_by_seed_identity(
            seed_pack=SEED_PACK,
            source_file=document.doc_id,
            preferred_storage_path=document.storage_path,
        )
        if existing and existing.storage_path != document.storage_path:
            update_source_storage_path(existing.id, document.storage_path)
        content_unchanged = bool(
            existing
            and existing.hash_sha256 == document.content_sha256
            and check_chunks_exist(existing.id)
        )
        source_id = upsert_source(
            storage_path=document.storage_path,
            file_name=document.filename,
            source_type="md",
            mime_type="text/markdown",
            sensitivity_label=document.classification,
            hash_sha256=document.content_sha256,
            file_size_bytes=len(document.content.encode("utf-8")),
            ingestion_status="embedded",
            enrichment_status="not_started",
            source_metadata_json=_source_metadata(document),
        )
        source_ids.append(source_id)

        chunks: list[dict[str, Any]] = []
        if content_unchanged:
            stats["unchanged"] += 1
        else:
            delete_chunks_for_source(source_id)
            chunks = _chunks(document)
            if chunks:
                insert_chunks(source_id, chunks)

        groups = (
            [document.owner_group] if document.classification == "restricted" else [ALL_EMPLOYEES]
        )
        replace_source_acl(source_id=source_id, group_names=groups)
        stats["sources"] += 1
        stats["chunks"] += len(chunks)
        stats["restricted"] += int(document.classification == "restricted")

    if embed:
        from app.embedding.process import process_embeddings

        # Scoped per source so this pack never pays to embed anything else.
        stats["embedding"] = [process_embeddings(source_id=source_id) for source_id in source_ids]
    return stats


def wipe(*, confirm: str) -> dict[str, Any]:
    if confirm != SEED_PACK:
        raise WesternCorpusError(f"--wipe requires --confirm {SEED_PACK}")
    from sqlalchemy import text

    from app.db.db import engine

    with engine.begin() as conn:
        deleted = [
            int(row[0])
            for row in conn.execute(
                text(
                    "DELETE FROM sources WHERE source_metadata_json->>'seed_pack' = :seed_pack "
                    "RETURNING id"
                ),
                {"seed_pack": SEED_PACK},
            )
        ]
    return {"mode": "wipe", "seed_pack": SEED_PACK, "deleted_source_ids": sorted(deleted)}


def auto_seed_western_corpus() -> dict[str, Any] | None:
    """Startup hook. A bad corpus drop is logged and skipped, never fatal to the demo."""
    if not settings.WESTERN_CORPUS_AUTOSEED:
        return None
    try:
        stats = apply(load_documents())
    except Exception as exc:
        log_event(
            "western_corpus.autoseed_failed",
            level=40,
            stage="startup",
            status="failed",
            reason=str(exc)[:500],
        )
        return None
    log_event("western_corpus.autoseeded", stage="startup", status="completed", **{
        key: stats[key] for key in ("sources", "chunks", "unchanged", "restricted")
    })
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true", help="Validate and estimate; no DB or API.")
    action.add_argument("--apply", action="store_true", help="Write sources, chunks and ACL.")
    action.add_argument("--wipe", action="store_true", help="Delete only this seed pack's sources.")
    parser.add_argument("--no-embed", action="store_true", help="With --apply, skip embedding.")
    parser.add_argument("--confirm", default="", help=f"Required with --wipe: {SEED_PACK}.")
    args = parser.parse_args(argv)

    try:
        if args.wipe:
            result = wipe(confirm=args.confirm)
        else:
            documents = load_documents()
            result = dry_run(documents) if args.dry_run else apply(documents, embed=not args.no_embed)
    except WesternCorpusError as exc:
        print(str(exc))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
