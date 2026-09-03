# Enterprise RAG — data layer

The data layer of a three-part governed retrieval system: PostgreSQL with pgvector,
hybrid retrieval, citations, and **access control enforced inside the retrieval SQL**.

**This is one of three repositories.** Start here:
**[Governed RAG — agent layer](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP)**
· **[Evaluation report](https://beyondalgorithms2026-source.github.io/RAG_ENTERPRISE_LANGGRAPH_APP/evaluation/)**

## The problem this solves

Two people ask an internal assistant the same question about salary bands. One works in
HR and may see the answer. One does not.

Most systems solve this by filtering results after retrieval, or in the user interface.
Both are the same mistake: the data has already left the database. If any layer above
leaks, logs, or caches the result, the control is gone.

Here, access control is composed into the retrieval query itself. A document the user may
not see is never selected, never scored, never ranked, never returned. There is nothing
to filter out afterwards, because it was never fetched.

## What happens when the system does not know

It returns a grounded refusal rather than an uncited answer. Citation enforcement is part
of the answer path: an answer that cannot be tied to retrieved text is not released as a
verified answer. The layer above then decides whether to retry, escalate to human review,
or stop.

Measured behaviour, on a 25-question evaluation: **five of five** questions with no
supporting document in the corpus were refused.

## The test evidence

**[The full evaluation report is here.](https://beyondalgorithms2026-source.github.io/RAG_ENTERPRISE_LANGGRAPH_APP/evaluation/)**

This repository's own suite has 36 test files. Twenty-two require a live migrated
Postgres, because testing SQL-level access control against anything other than a real
query planner proves very little. Those are skipped — visibly, with a reason — when no
database is present.

```
Offline:  27 passed, 34 skipped, 0 failures
```

Set `RAG_REQUIRE_DB=1` to turn the skips into failures, so a CI job that is supposed to
have a database cannot pass by skipping everything.

## What this is NOT

- **Not deployed anywhere.** A self-built proof of concept — no client environment, no
  users, no real workload.
- **Not multi-tenant, and not multi-worker.** Single-process by design and guarded
  against being run otherwise.
- **Agentic actions do not dispatch.** `send_email`, `send_slack` and
  `create_calendar_event` prepare and record but never send. The approval, policy and
  audit machinery around them is real; the outbound effect is deliberately absent.
- **`AUTH_MODE=password` is not implemented.** It is reserved and says so.
- **Retrieval enhancements ship off by design.** Reranking, MMR, query transformation,
  rewrite, expansion, HyDE and multi-query are implemented and switched off. An operator
  enables them per corpus; the agent layer cannot reach them. The published evaluation
  measures both states.

## What is here

| | |
|---|---|
| Retrieval | Hybrid vector + keyword over pgvector, with linear or RRF fusion |
| Access control | Five strategies, composed into retrieval SQL, from open to time-bound per-document grants |
| Citations | Enforced on the answer path; safe not-found beats an uncited answer |
| Providers | LLM provider swappable by environment variable — OpenAI-compatible, Ollama, Anthropic, vLLM, Azure |
| Governance | Approval gates, hash-chained audit, admin console, evaluation packs |
| Console | Next.js admin interface with no external dependencies — renders with the network blocked |

## Setup

Requires Docker and Python 3.12.

```bash
docker compose up -d
cd backend && python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then set the four secrets it names
python -m app.db.migrate
```

The four secrets have **no defaults in source** — the application refuses to start
without them and tells you which is missing. Generate each with:

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

Load the synthetic demo corpus — 27 invented HR and policy documents for a fictional
company, with public, internal and restricted classifications that become real access
grants:

```bash
python corpus/generate_corpus.py --out ~/.rag-enterprise/uploads
cd backend && python -m app.seed.public_demo
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Licence

Apache-2.0.
