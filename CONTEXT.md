# CONTEXT.md — High-level Project Overview (Enterprise RAG Starter)

**Objective (one sentence)**  
Build an enterprise-usable RAG system based on the existing stable baseline that supports SSO + ACL security trimming, multi-source ingestion (cloud DB + enterprise email), configurable retrieval/model controls, end-user chat UI + admin console, tool actions with approvals, feedback loops, and per-corpus indexing policies — without breaking baseline correctness.

**Current baseline (what the codebase already does today)**
This repository is already more than a basic RAG demo. It supports document-type-specific parsing and chunking, one dense embedding path, multiple retrieval modes, heuristic query routing, optional cross-encoder reranking, graph and temporal enrichment layers, a deep-research retrieval path, and several offline evaluation harnesses.  
It is best described as a strong PoC-grade retrieval system rather than an enterprise-final retrieval platform.  
The main retrieval baseline today is hybrid search with linear score fusion (combined_score = 0.65 * vector_score + 0.35 * keyword_score). Several levers are already present (custom query text, exact phrase bias, anchor-term extraction, source/locator filters, deep-research, optional reranking, graph/temporal boosts).  
Missing enterprise levers (semantic cache, full query rewriting/HyDE, field-weighted keyword indexing, MMR diversity, real user-query mining loop) will be added in later milestones.

**What the system DOES**
- Claude-like chat UI with grounded answers + citations
- Fast/Slow toggle
- Feedback loop
- Admin console for corpus management, profiles, reindexing, evals, traces
- Pluggable connectors (uploads, DB, later email)
- Observability (latency, traces, scores)
- Security: SSO + ACL trimming at retrieval time

**What it does NOT do (initially)**
- Multi-tenant SaaS, full async pipelines, sovereign data residency, perfect answers, real-time transactional ERP without tools.

**Architecture (two planes)**
- Ingestion Plane: connectors → parsing → chunking → embeddings → index
- Query Plane: Auth → ACL trimming → retrieval routing → rerank → generation → citations + logging

**Milestone order reminder**  
Follow the exact order in `docs/02_Enterprise_RAG_Project_Plan_Milestones.md` (we are now at M1 or later — M0 baseline import is already complete).
