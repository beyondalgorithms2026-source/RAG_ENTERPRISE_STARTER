# Upwork portfolio item — paste-ready (T3, 14 Oct 2026)

Upwork's portfolio guide (published 7 Jul 2026, checked 14 Oct 2026): fields are title, role, description, up to
five skills, media and a thumbnail; images 1000 × 750 px, up to 10 MB. Thumbnail: `upwork-snapshot-1000x750.png`.

## Title (62 characters)

Governed RAG: cited answers, access control in SQL, audit trail

## Your role

Sole builder: architecture, data layer, agent orchestration, evaluation and hosting.

## Description

Teams want answers from their own policy documents without the model guessing or showing files a person
shouldn't see.

I built a three-part governed RAG system. A FastAPI data layer stores documents in Postgres with pgvector, searches
by keyword and meaning together, and writes access rules into the search query itself, so restricted documents are
never retrieved for the wrong user. Every answer must cite a source passage, or it says it cannot answer. An
orchestration layer checks the evidence, retries narrower searches when it is weak, holds sensitive answers for
human approval, and records each run in a tamper-evident audit trail. A small MCP server sits between the two.

Results, on synthetic documents for two fictional companies: 19 of 20 on the Northline demo set with Claude Haiku
5.5 (14 Oct 2026; up from 15 of 20 on the previous model), and 20 of 20 red-team scenarios defended (18
deterministic checks plus 2 live access-control checks in CI).

Limits: synthetic data; a 20-question demo set run once, not a benchmark; free hosting with cold starts; not a
production or client deployment.

## Skills (five)

Retrieval-Augmented Generation · Python · PostgreSQL · LLM Evaluation · FastAPI

Alternates if Upwork suggests other tags: pgvector, Model Context Protocol, Anthropic Claude, LangGraph.

## Links (add as project URL / in the description)

- Live demo: https://rag-enterprise-governance-demo.onrender.com/app
- How it works (every claim with its proof): https://rag-enterprise-governance-demo.onrender.com/app/how-it-works
- Scorecard: https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_STARTER/blob/main/docs/evaluation/western/scorecard.md
- Code: https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP ·
  https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_STARTER ·
  https://github.com/beyondalgorithms2026-source/RAG_Langgraph_MCP_server

## Before pasting

- The live demo sleeps on free hosting; open it once so the first viewer doesn't wait.
- Do not add "secure", "certified", "compliant" or "production client" wording.
