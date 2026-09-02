"""Generate the synthetic public demo corpus.

Every document produced here is invented. See corpus/README.md for why this exists
and how the classifications map onto the seeded ACL.

Deterministic: the corpus is data (corpus/library.py), not generated prose, so the
same input always produces byte-identical output and eval numbers computed against
it are reproducible.

    python corpus/generate_corpus.py --out ~/.rag-enterprise/uploads
    python corpus/generate_corpus.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from library import DOCUMENTS, EVAL_QUESTIONS, Document  # noqa: E402

VALID_CLASSIFICATIONS = {"public", "internal", "restricted"}
VALID_OWNER_GROUPS = {"people-operations", "finance", "security", "legal", "operations"}


def check() -> list[str]:
    """Validate the corpus before it is written or ingested.

    Catches the failure that matters most here: an eval question pointing at a
    document that does not exist. That is how a question set silently stops
    testing what it claims to test.
    """
    problems: list[str] = []
    slugs = [d.slug for d in DOCUMENTS]

    for slug in slugs:
        if slugs.count(slug) > 1:
            problems.append(f"duplicate slug: {slug}")

    for document in DOCUMENTS:
        if document.classification not in VALID_CLASSIFICATIONS:
            problems.append(f"{document.slug}: unknown classification {document.classification!r}")
        if document.owner_group not in VALID_OWNER_GROUPS:
            problems.append(f"{document.slug}: unknown owner_group {document.owner_group!r}")
        if document.body.count("##") < 3:
            problems.append(f"{document.slug}: fewer than 3 sections")

    known = set(slugs)
    for question in EVAL_QUESTIONS:
        if question.expected_document is None:
            if question.expected_fact is not None:
                problems.append(f"unanswerable question carries an expected_fact: {question.question!r}")
            continue
        if question.expected_document not in known:
            problems.append(
                f"eval question points at a document that does not exist: "
                f"{question.expected_document!r} ({question.question!r})"
            )
        if not question.expected_fact:
            problems.append(f"answerable question has no expected_fact: {question.question!r}")

    if not any(q.expected_document is None for q in EVAL_QUESTIONS):
        problems.append("no unanswerable questions: the refusal path would be untested")

    return problems


def write_corpus(out_dir: Path, documents: list[Document]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    for document in documents:
        (out_dir / document.filename()).write_text(document.render(), encoding="utf-8")

    # The manifest is what the seed pack reads. Classification and owning group
    # travel with the documents so ACL is defined alongside them rather than
    # configured separately and drifting.
    manifest = {
        "corpus": "northwind-public-demo",
        "synthetic": True,
        "note": "Every document is invented. No real company or person is represented.",
        "document_count": len(documents),
        "documents": [
            {k: v for k, v in asdict(d).items() if k != "body"} | {"filename": d.filename()}
            for d in documents
        ],
        "eval_questions": [asdict(q) for q in EVAL_QUESTIONS],
    }
    (out_dir / "corpus-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"out_dir": str(out_dir), "count": len(documents)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="~/.rag-enterprise/uploads", help="Output directory.")
    parser.add_argument("--check", action="store_true", help="Validate the corpus and exit.")
    args = parser.parse_args()

    problems = check()
    if problems:
        print("Corpus validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.check:
        answerable = sum(1 for q in EVAL_QUESTIONS if q.expected_document)
        unanswerable = len(EVAL_QUESTIONS) - answerable
        by_class: dict[str, int] = {}
        for d in DOCUMENTS:
            by_class[d.classification] = by_class.get(d.classification, 0) + 1
        print(f"OK: {len(DOCUMENTS)} documents {by_class}")
        print(f"OK: {answerable} answerable eval questions, {unanswerable} unanswerable by design")
        return 0

    result = write_corpus(Path(args.out).expanduser(), DOCUMENTS)
    print(f"Wrote {result['count']} synthetic documents to {result['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
