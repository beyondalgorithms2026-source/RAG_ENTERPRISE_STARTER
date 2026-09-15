"""Real STARTER-only candidate runs in an explicitly isolated test database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


def require_isolated_database(url: str) -> None:
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.startswith(
        "/b004_eval_"
    ):
        raise ValueError(
            "Candidate setup requires a localhost b004_eval_* database; shared/hosted databases are prohibited."
        )


def sanitize_report(value):
    if isinstance(value, dict):
        return {
            key: sanitize_report(item)
            for key, item in value.items()
            if key.lower()
            not in {
                "api_key",
                "password",
                "secret",
                "token",
                "authorization",
                "headers",
                "messages",
                "traceback",
                "storage_path",
                "system_prompt",
                "user_prompt",
                "prompt",
            }
            and not key.lower().endswith(("_api_key", "_password", "_secret"))
        }
    if isinstance(value, list):
        return [sanitize_report(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[redacted]", value)
        return re.sub(r"/Users/[^\s\"']+", "[path-redacted]", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--prepare", choices=["legacy", "full"])
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--case-id", action="append")
    args = parser.parse_args()
    require_isolated_database(os.environ.get("DATABASE_URL", ""))
    if args.output.exists():
        parser.error("refusing to overwrite a diagnostic run")
    # Dedicated process settings; never mutate a running visitor process/profile.
    os.environ["ANSWER_CONTEXT_SELECTION_ENABLED"] = str(args.candidate).lower()
    os.environ["ANSWER_PROMPT_CANDIDATE"] = str(args.candidate).lower()
    os.environ["ANSWER_CONTEXT_CHUNK_CAP_CHARS"] = "4000"
    from app.core.config import settings
    from app.core_rag import answering
    from app.core_rag.retrieval import SearchFilters
    from app.llm.client import verify_llm_ready
    from app.llm.prompt_registry import prompt_metadata
    from app.profiles.models import LLMProfileConfig
    from app.profiles.resolver import get_effective_retrieval, profile_overrides

    if args.prepare:
        from app.db.migrate import run_migrations
        from app.seed.public_demo import seed_public_demo

        corpus = Path(__file__).resolve().parents[3] / "corpus"
        sys.path.insert(0, str(corpus))
        from generate_corpus import write_corpus
        from library import DOCUMENTS

        documents = (
            DOCUMENTS if args.prepare == "full" else [d for d in DOCUMENTS if not d.source_file]
        )
        write_corpus(args.corpus_dir, documents, legacy_manifest=args.prepare == "legacy")
        run_migrations()
        seed_public_demo(args.corpus_dir)
    if args.setup_only:
        print("Isolated synthetic corpus prepared; no questions generated.")
        return 0
    payload = json.loads(args.pack.read_text())
    questions = [
        q for q in payload["questions"] if not args.case_id or q["case_id"] in args.case_id
    ]
    if args.case_id and len(questions) != len(set(args.case_id)):
        parser.error("unknown or duplicate selected case IDs")
    from app.db.db import engine
    from sqlalchemy import text

    # Source identification is limited to this run's generated corpus path.
    with engine.connect() as connection:
        sources = connection.execute(
            text("SELECT id, file_name FROM sources WHERE storage_path LIKE :prefix"),
            {"prefix": str(args.corpus_dir.resolve()) + "%"},
        ).all()
    manual_ids = [
        row.id for row in sources if row.file_name == "northwind-operations-manual-v3.2.md"
    ]
    if any(q["case_id"].startswith("OM-") for q in questions) and len(manual_ids) != 1:
        raise RuntimeError("infrastructure: exactly one seeded manual source is required")
    llm = LLMProfileConfig(
        provider="openai",
        model="gpt-4o-mini-2024-07-18",
        base_url="https://api.openai.com",
        api_key=settings.LLM_API_KEY,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=0,
        structured_output_mode="native_json",
    )
    retrieval = get_effective_retrieval().model_copy(update={"semantic_cache_enabled": False})
    original_builder = answering._build_context_blocks
    observed = []

    def observe(*a, **kw):
        blocks = original_builder(*a, **kw)
        observed.extend(blocks)
        return blocks

    # Observability wrapper calls the real implementation unchanged; no fake
    # retrieval, SQL, provider or generated response participates in this run.
    answering._build_context_blocks = observe
    rows = []
    report = {
        "scope": "starter-only-live",
        "baseline_eligible": False,
        "suite_version": payload.get("suite_version"),
        "configuration": {
            "candidate": args.candidate,
            "chunk_cap_chars": 4000,
            "llm": {"provider": llm.provider, "model": llm.model},
            "prompts": prompt_metadata(),
            "context_budget_chars": answering.MAX_TOTAL_CONTEXT_CHARS,
            "corpus_manifest_sha256": hashlib.sha256(
                (args.corpus_dir / "corpus-manifest.json").read_bytes()
            ).hexdigest(),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with profile_overrides(llm=llm, retrieval=retrieval, chunk_cap=4000):
            if not verify_llm_ready():
                raise RuntimeError("infrastructure: pinned LLM readiness failed")
            for q in questions:
                observed.clear()
                start = time.perf_counter()
                try:
                    response = answering.perform_ask(
                        answering.AskRequest(
                            question=q["question"],
                            k_chunks=6,
                            mode="hybrid",
                            bypass_cache=True,
                            filters=SearchFilters(source_id=manual_ids[0])
                            if q["case_id"].startswith("OM-")
                            else None,
                        )
                    )
                    from app.llm.usage import current_usage

                    if (response.debug_info or {}).get("error"):
                        raise RuntimeError("infrastructure: backend generation failed")

                    usage = current_usage()
                    row = {
                        "case_id": q["case_id"],
                        "question": q["question"],
                        "answer": response.answer,
                        "citations": [c.model_dump(mode="json") for c in response.citations],
                        "evidence": [
                            {
                                "snippet": b["snippet"],
                                "file_name": b["file_name"],
                                "heading": b["heading"],
                            }
                            for b in observed
                        ],
                        "selected_context": observed.copy(),
                        "usage": usage,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 3),
                        "retrieval_trace": (response.debug_info or {}).get("retrieval_trace", {}),
                        "failure_class": None,
                        "backend_answer_path": (response.debug_info or {}).get(
                            "answer_generation_path"
                        ),
                    }
                except Exception:
                    row = {
                        "case_id": q["case_id"],
                        "question": q["question"],
                        "answer": "",
                        "failure_class": "infrastructure",
                        "error": "starter_candidate_run_failed",
                    }
                rows.append(row)
                args.output.write_text(
                    json.dumps(sanitize_report(report), indent=2, default=str) + "\n"
                )
                print(
                    f"{q['case_id']}: {'infrastructure failure' if row['failure_class'] else 'answer recorded'}",
                    flush=True,
                )
    finally:
        answering._build_context_blocks = original_builder
    return 2 if any(r["failure_class"] for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
