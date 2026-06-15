# CONTEXT.md — High-level Project Overview (Enterprise RAG Starter)

**Objective (one sentence)**  
Build an enterprise-usable RAG system based on the existing stable baseline that supports SSO + ACL security trimming, multi-source ingestion (cloud DB + enterprise email), configurable retrieval/model controls, end-user chat UI + admin console, tool actions with approvals, feedback loops, and per-corpus indexing policies — without breaking baseline correctness.

**Current phase**  
AR0–AR18 is complete. AR18 made health, cost, flywheel, embedding, and providers first-class modules with server-enforced endpoint gating and a deployment-wide runtime module manager. AR19 console component/form refactoring is next; M20–M30 manual verification notes also remain open.

**Current baseline (what the codebase already does today)**
This repository is substantially more real than a typical RAG demo. It supports document-type-specific parsing and chunking, one dense embedding path, multiple retrieval modes, heuristic query routing, optional cross-encoder reranking, graph and temporal enrichment layers, a deep-research retrieval path, governed tuning (drafts/compare/promote/rollback), semantic cache with governance, ~80 admin endpoints, pervasive trace observability, and citation provenance enforcement.  
It is best described as a **strong PoC with genuine starter scaffolding** — past demo, not yet enterprise starter.  
The main retrieval baseline is hybrid search with linear score fusion (combined_score = α × vector_score + (1-α) × keyword_score, default α=0.65). AR14 added field-weighted FTS, real optional MMR, and committed ablation evidence for anchor, graph, temporal, and deep-research scoring.

**What the system DOES**
- Chat UI with grounded answers + enforced citation provenance (whitelist, stripping, forced not-found)
- Hybrid retrieval with traced routing, fusion, and rerank decisions
- SQL-level access trimming (5 strategies) threaded through every retrieval path
- Admin console: profiles, tuning, sandbox compare, cache policies, traces, audit, governance
- Generation provider console: create/update/test/activate provider profiles with write-only API keys
- Runtime cost budget, model price table, and promotion enforcement controls with audited precedence
- Deployment-wide admin module composition with runtime overrides, audited changes, and server-enforced disabled endpoints
- Connectors: uploads (7 adapters), DB sync, .eml parsing
- Observability: per-stage latency, full decision traces, query mining tables
- Governed config change: drafts → compare → promote → rollback → audit trail

**What it does NOT do**
- Multi-tenant SaaS, full async pipelines, sovereign data residency, or unrestricted multi-worker deployment. Mailbox/archive synchronization is not implemented; email ingestion remains uploaded `.eml`.
- Built-in encrypted secret storage: provider API keys are write-only through APIs and audit-safe, but database-at-rest encryption or an external secret manager remains deployment responsibility.

**Architecture (two planes)**
- Ingestion Plane: connectors → parsing → chunking → embeddings → index (single in-process worker)
- Query Plane: Auth → ACL trimming → query transform → retrieval routing → fusion → rerank → generation → citation enforcement → cache → traces

**Critical audit-identified gaps (AR-series targets)**
1. Regression suite broken (55/57 errors from dimension mismatch) → AR1
2. Governance is workflow not enforcement (draft active as live, wrong registry metadata) → AR2
3. Eval packs too thin to gate anything (~28 cases, keyword-only) → AR3
4. Promotion path has no eval requirement → AR4
5. Query transform is a stub behind real governance → AR5
6. Cache naming is false ("semantic" = exact-match) → AR6
7. Embedding model swap lifecycle unmanaged → AR7
8. Single-machine, single-process assumptions block adoption → AR8
9. Ollama-only LLM provider → AR9

**Milestone plans**
- M-series: `docs/02_Enterprise_RAG_Project_Plan_Milestones.md` (DO NOT MODIFY)
- AR-series: `docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md` (active work track)
- Audit baseline: `docs/03_Enterprise_RAG_Independent_Product_Audit_2026_06_11.md`
