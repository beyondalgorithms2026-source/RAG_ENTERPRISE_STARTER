# Master Guide

This is the single best deep guide for understanding, operating, and reusing `RAG_MM_MASTER_POC`.

It is written for:
- first-time readers who need a fast orientation
- adopters forking the repo for a new RAG project
- maintainers who want one document that explains both the practical shape and the important caveats

This guide is intentionally self-contained. Other docs are still useful, but you should be able to understand the repo at a high level without leaving this file.

---

## Start Here: 60-Second Summary

### What this repo is

`RAG_MM_MASTER_POC` is an extraction-first, upload-based RAG base repo with:
- multi-format file ingestion
- chunking and embedding
- baseline retrieval and grounded answering
- optional temporal and graph enrichment
- explicit compare mode
- explicit router behavior when `mode` is omitted
- separate evaluation and benchmarking harnesses

### Who it is for

- teams starting a new RAG PoC from an existing base
- consultants or platform teams adapting one core to different domains
- maintainers who want a practical reference implementation rather than just milestone history

### Who it is not for

- teams expecting a production-ready enterprise platform on day one
- teams that require async ingestion, cloud-native storage, multi-tenant controls, or hardened migration tooling immediately
- teams that want a no-database or browser-only demo architecture

### Current maturity

- implemented through M20
- first hardening pass complete
- docs/package-up pass complete
- second hardening pass complete

Best current description:
- strong reusable PoC base
- safer and better documented than a one-off prototype
- not yet a hardened enterprise platform base

### Safest default usage path

If you are adopting this repo, the safest path is:
1. keep the current schema and baseline upload -> search -> ask flow
2. start with `hybrid`
3. treat `graph_hybrid`, `full`, router behavior, and compare mode as optional layers
4. add your own domain eval fixtures early
5. change providers and adapters before changing retrieval internals

### Biggest current limitations

- ingestion is synchronous
- uploads assume local filesystem storage
- important internal state still lives in JSON-heavy metadata
- migration discipline is improved but still lightweight
- graph and temporal support are conservative PoC layers, not enterprise-grade reasoning systems
- DB-backed tests still assume a working local Postgres setup

### Best reading order through this guide

If you only have a few minutes:
1. `Start Here: 60-Second Summary`
2. `Default Operating Profile`
3. `Retrieval Mode Matrix`
4. `What To Keep Vs What To Replace`
5. `Known Limitations / Do Not Assume`

If you are actively forking the repo:
1. the sections above
2. `Common Modification Playbooks`
3. `Repo Structure Chart`
4. `Enterprise Upgrade Path`
5. `Common Issues / Where To Look When Something Breaks`

See also:
- [README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
- [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 1. Repo Identity And Maturity

`RAG_MM_MASTER_POC` is an extraction-first, upload-based RAG system with optional enrichment layers.

Its current design center is:
- take uploaded business-style documents
- normalize them through adapters
- chunk and embed them
- support baseline retrieval and grounded answer generation
- optionally layer graph-aware and temporal-aware behavior on top
- expose compare and evaluation as explicit surfaces instead of hidden automation

Current maturity in practical terms:
- good enough to reuse as a PoC starter
- clear enough to onboard new maintainers
- not yet strong enough to call a platform-grade reusable base without more hardening

### What this repo does now

Implemented behavior:
- `/upload` accepts `pdf`, `docx`, `pptx`, `xlsx`, `eml`, `txt`, and `md`
- `/corpus` exposes current source state
- `/search` supports `vector`, `keyword`, `hybrid`, `graph_hybrid`, and `full`
- `/deep_lookup` provides explicit source-scoped rescue retrieval
- `/ask` returns grounded answers with citations
- `/compare` returns explicit source-bucketed compare answers
- evaluation harnesses cover retrieval, answer, compare, and mode benchmarking

Current file-format notes:
- `txt` is handled as plain text only
- `md` is handled with lightweight heading-aware parsing and remains text-first, with no markdown rendering pipeline

### What remains optional

Optional or flag-controlled behavior:
- graph extraction/build/use
- temporal extraction/use
- lazy enrichment for `full`
- router behavior when `mode` is omitted
- compare-mode usage
- evaluation/benchmark workflows

### What remains deferred

Not implemented as a finished platform capability:
- async job orchestration
- object-storage-native uploads
- hardened migration history/framework
- enterprise observability and admin controls
- multi-tenant platform behavior
- rich compare UI

---

## 2. Default Operating Profile

This is the clearest single description of how the repo behaves by default today.

### Current default runtime behavior

Out of the box:
- the repo assumes local Postgres + pgvector
- files are stored locally on disk
- baseline retrieval default is `hybrid`
- explicit mode selection is preserved
- router behavior is enabled when `mode` is omitted
- lazy enrichment is allowed for source-scoped `full` requests
- graph and temporal build/use remain optional and flag-controlled

### Baseline modes

Baseline-safe modes:
- `vector`
- `keyword`
- `hybrid`

These do not require graph or temporal artifacts.

### Enrichment-backed modes

Optional, artifact-aware modes:
- `graph_hybrid`
- `full`

These still use baseline retrieval as the backbone, but may layer graph/temporal behavior on top when available.

### Compare mode explicitness

Compare behavior is:
- explicit only through `/compare`
- source-scoped
- not hidden inside `/ask`

### Deep lookup explicitness

Current deep lookup policy:
- explicit only through `/deep_lookup`
- requires explicit source ids
- is retrieval-only
- does not change normal `/search`, `/ask`, or `/compare` behavior unless explicitly called
- does not silently invoke router, graph, temporal, or indexing behavior

### Router behavior

Current router policy:
- only runs when `mode` is omitted
- never silently overrides explicit mode choice
- is conservative by design
- falls back to safer baseline behavior when uncertainty is high

### Lazy enrichment behavior

Current lazy enrichment behavior:
- only matters for source-scoped `full`
- is bounded to one attempt
- only runs when allowed and when prerequisites are present
- falls back safely when unavailable or failing

### Storage and runtime assumptions

Current operational posture:
- local-first
- PoC-oriented
- synchronous upload pipeline
- DB-backed tests and eval paths
- compact JSON metadata for graph/temporal/lazy state

See also:
- [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [architecture_overview.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)

---

## 3. Retrieval Mode Matrix

This is the most explicit current mode guide in the repo.

| Mode | What It Is | When To Use It | When Not To Use It | Depends On | Fallback Behavior | Baseline-Safe Or Enrichment-Dependent |
| --- | --- | --- | --- | --- | --- | --- |
| `vector` | embedding similarity only | semantic lookup, paraphrases, concept matching | exact-term lookups, quoted phrases, IDs | embeddings and embedding model | no enriched fallback; it is just vector search | baseline-safe |
| `keyword` | lexical/full-text retrieval only | exact phrases, names, IDs, highly lexical queries | fuzzy or paraphrased semantic questions | `search_tsv` and keyword index | no enriched fallback; it is just keyword search | baseline-safe |
| `hybrid` | vector + keyword baseline retrieval | safest default for most general usage | only when you intentionally need a narrower explicit mode | embeddings plus keyword index | native baseline path | baseline-safe |
| `graph_hybrid` | `hybrid` plus graph-aware candidate support | relationship-heavy questions when graph artifacts are current | if graph is disabled, missing, stale, or not useful for the query | graph artifacts for a scoped source plus baseline retrieval | explicit fallback to `hybrid` | enrichment-dependent |
| `full` | baseline retrieval plus available graph/temporal support and bounded readiness orchestration | time-sensitive, version-sensitive, or mixed graph+temporal questions | if source scope is unclear or you do not want optional enrichment behavior | baseline retrieval, optional artifacts, lazy enrichment flags | explicit fallback to `hybrid` | enrichment-dependent |
| `compare` | explicit multi-source answer surface via `/compare` | side-by-side reasoning across selected sources | normal single-source `/ask` flows or hidden automation | explicit source scope, ask/retrieval stack, grouped evidence orchestration | fails clearly or stays scoped instead of silently broadening | explicit surface, not a default baseline mode |

### Mode notes in plain language

`vector`
- strong when the user asks semantically
- weak when the user expects literal text hits

`keyword`
- strong when literal phrase matching matters
- weak for paraphrases

`hybrid`
- best default starting point for new adopters
- safest mode to keep while making early changes elsewhere

`graph_hybrid`
- should be treated as additive, not magical
- only pays off when graph artifacts are ready and the query really is relationship-heavy

`full`
- should not be treated as “always best”
- is useful when time/version context matters and source-scoped readiness exists

`compare`
- is not part of the normal `/ask` mode list
- is its own explicit answer surface

---

## 4. End-To-End System Flow

### Short version

1. upload a file
2. parse and normalize it
3. chunk it
4. embed chunks
5. optionally enrich/build graph-temporal artifacts
6. search or answer over the resulting corpus
7. optionally compare across explicit sources
8. evaluate behavior using separate eval harnesses

### More detailed runtime flow

1. `/upload`
   - validates file type and MIME
   - stores file metadata and bytes
   - creates source and ingestion-job records
2. parse and source-part persistence
   - adapter normalizes the source into a shared internal shape
   - source parts are stored for structure-aware provenance
3. chunking
   - content becomes source-aware chunks with headings, locators, and provenance
4. embedding
   - chunk embeddings are written to `chunks.embedding`
5. optional enrichment
   - entity/relation extraction may run
   - temporal extraction may run
   - source-level graph artifacts may be built
6. retrieval
   - `/search` or `/ask` resolves a mode directly or through the router
   - baseline retrieval runs first
   - optional graph/temporal support may layer on top
7. answering
   - `/ask` builds a grounded prompt and returns citations
   - `/compare` does explicit multi-source grouped reasoning
8. evaluation
   - eval harnesses run separately from production behavior

---

## 5. Repo Structure Chart

The repo is small enough to understand as a tree, but a few areas are already clear improvement hotspots.

`*` marks a likely future improvement hotspot.

```text
RAG_MM_MASTER_POC/
├── README.md
├── STATUS.md
├── RAG_Master_Revised_Project_Plan.md
├── docker-compose.yml
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   └── app/
│       ├── api/
│       │   ├── health.py
│       │   ├── upload.py
│       │   ├── corpus.py
│       │   ├── search.py
│       │   ├── ask.py
│       │   └── compare.py
│       ├── core/
│       │   ├── config.py
│       │   └── logging.py
│       ├── core_rag/
│       │   ├── answering.py
│       │   ├── query_router.py
│       │   ├── retrieval.py *
│       │   └── reranker.py
│       ├── db/
│       │   ├── db.py
│       │   ├── migrate.py *
│       │   ├── schema.sql
│       │   ├── repo_chunks.py
│       │   ├── repo_jobs.py
│       │   ├── repo_search.py
│       │   ├── repo_source_parts.py
│       │   └── repo_sources.py *
│       ├── embedding/
│       │   ├── embedder.py
│       │   └── process.py
│       ├── graph/
│       │   ├── extractor.py
│       │   ├── graph_index.py
│       │   ├── graph_retriever.py
│       │   ├── graph_store.py
│       │   ├── ontology.py
│       │   └── temporal.py
│       ├── ingestion/
│       │   ├── chunking.py
│       │   ├── enrichment.py *
│       │   └── jobs.py *
│       ├── llm/
│       │   ├── client.py
│       │   └── prompts.py
│       └── eval/
│           ├── retrieval_eval.py
│           ├── enriched_eval.py
│           └── compare_eval.py
├── backend/tests/
│   ├── smoke_test_base.py
│   ├── test_smoke_baseline.py
│   ├── test_smoke_enrichment.py
│   ├── test_smoke_router_compare_eval.py
│   ├── smoke_test_extracted.py
│   └── fixtures/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── upload.js
│   ├── corpus.js
│   └── ask.js
└── docs/
    ├── master_guide.md
    ├── configuration.md
    ├── architecture_overview.md
    ├── api_surface.md
    ├── module_map.md
    ├── adoption_guide.md
    ├── evaluation.md
    ├── internal_metadata_contracts.md
    ├── maintainer_runbook.md
    └── historical reference docs
```

### What the asterisks mean

- `retrieval.py *`
  - carries multiple mode paths, fallback rules, and optional enriched behavior
  - likely future improvement area because orchestration density grows here first

- `migrate.py *`
  - improved, but still lightweight compared with a stronger migration/versioning system
  - likely future improvement area for downstream reuse safety

- `repo_sources.py *`
  - central place for source metadata contracts
  - likely future improvement area because JSON metadata safety matters across retrieval, enrichment, and eval

- `enrichment.py *`
  - central enrichment and lazy-readiness orchestration layer
  - likely future improvement area because optional behavior collects here

- `jobs.py *`
  - central synchronous upload orchestration layer
  - likely future improvement area if moving to async/background workflows or alternate storage

### Where future improvements would likely happen first

If the repo grows, the first likely hotspots are:
- `backend/app/ingestion/jobs.py`
  - for async processing, cloud storage, stronger failure boundaries
- `backend/app/ingestion/enrichment.py`
  - for clearer build/orchestration separation
- `backend/app/core_rag/retrieval.py`
  - for retrieval policy complexity
- `backend/app/db/migrate.py`
  - for stronger versioning discipline
- `backend/app/db/repo_sources.py`
  - for metadata enforcement and safer update patterns

See also:
- [module_map.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 6. What To Keep Vs What To Replace

This table is written for people forking the repo.

| Area / Component | Keep As-Is | Replace Early | Replace Only If Scaling | Files Usually Touched First | What Must Be Re-Verified | Risk If Changed Casually |
| --- | --- | --- | --- | --- | --- | --- |
| schema | yes, for most forks | only if your source model is fundamentally different | yes, if you need tenancy or stronger ops controls | `backend/app/db/schema.sql`, `backend/app/db/repo_*`, `backend/app/db/migrate.py` | migrations, source/chunk persistence, upload -> ask flow | repo modules and assumptions drift fast |
| adapters/parsers | keep the adapter pattern | yes, if formats or extraction method differ | no | `backend/app/adapters/`, `backend/app/ingestion/jobs.py` | parsing, source parts, chunk provenance, upload flow | downstream chunk/provenance shape can break |
| chunking | keep current heuristics first | only if your documents are very different | yes, if recall/latency tuning becomes important | `backend/app/ingestion/chunking.py` | retrieval quality, snippets, citation usefulness, eval fixtures | subtle retrieval regressions |
| embedding model/provider | keep first for fast adoption | yes, if infra/domain requires it | no | `backend/app/embedding/embedder.py`, `backend/app/embedding/process.py`, `backend/app/core/config.py`, `backend/app/db/migrate.py` | vector dimension, migrations, retrieval modes, eval cases | stale vectors or dimension mismatch |
| LLM model/provider | keep first for fast adoption | yes, if policy/runtime requires it | no | `backend/app/llm/client.py`, `backend/app/llm/prompts.py`, `backend/app/core/config.py` | answer formatting, citations, compare output, answer eval | grounded answer behavior can regress |
| retrieval defaults | keep `hybrid` first | yes, if your users clearly need another default | yes, if tuning becomes sustained work | `backend/app/core/config.py`, `backend/app/core_rag/retrieval.py` | `/search`, `/ask`, router expectations, eval fixtures | hidden behavior drift |
| router | keep if conservative omitted-mode behavior helps | yes, if you want full manual control | yes, if routing becomes domain-specific | `backend/app/core_rag/query_router.py`, `backend/app/core/config.py` | omitted-mode behavior, fallback behavior, compare reuse | users may stop understanding mode selection |
| compare mode | keep if explicit multi-source reasoning matters | yes, if your product does not need compare | yes, if compare becomes a richer workflow/UI | `backend/app/api/compare.py`, `backend/app/core_rag/answering.py` | compare grouping, citations, source scope rules | `/ask` and `/compare` boundaries can blur |
| frontend | keep only as a demo shell | yes, for most product forks | yes | `frontend/` | basic upload/search/ask flow expectations | frontend can lag backend capability quickly |
| eval fixtures | keep the fixture structure | yes, replace with domain fixtures early | yes, expand if benchmarking grows | `backend/tests/fixtures/eval/`, `backend/app/eval/` | eval loading, case stability, benchmark usefulness | stale fixtures mislead tuning |
| graph/temporal layers | keep optional and conservative | yes, if your project does not benefit from them | yes, if you need richer reasoning | `backend/app/graph/`, `backend/app/ingestion/enrichment.py`, `backend/app/core_rag/retrieval.py` | artifact readiness, retrieval fallback, eval cases | metadata and retrieval assumptions can break subtly |
| storage model | keep local-first for PoC use | yes, if your deployment requires cloud storage early | yes | `backend/app/ingestion/jobs.py`, `backend/app/core/config.py`, deployment/runtime docs | upload flow, parser file access, debug artifact assumptions | path/file access assumptions break fast |
| migration flow | keep current lightweight model for PoCs | only if you already know you need stronger release/version discipline | yes | `backend/app/db/migrate.py`, `backend/app/db/schema.sql` | fresh setup, upgrades, embedding-dimension changes | upgrade drift and schema confusion |

See also:
- [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
- [evaluation.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)

---

## 7. Common Modification Playbooks

These playbooks are written as practical “what changes, what may break, what must be re-verified” guides.

### Playbook: Change The Embedding Model Or Provider

This is often a safe early change if you keep the rest of the retrieval stack stable.

What usually changes first:
- provider/model selection
- embedding client implementation
- config defaults

Files/modules most involved:
- `backend/app/embedding/embedder.py`
- `backend/app/embedding/process.py`
- `backend/app/core/config.py`
- `backend/app/db/migrate.py`

What may break:
- embedding dimension mismatch
- degraded semantic retrieval quality
- stale vectors after model changes

What must be re-verified:
- migration-time vector alignment
- `vector` and `hybrid` behavior
- benchmark/eval cases that depend on semantic similarity

Change class:
- safe early change if you re-verify dimension and retrieval behavior

### Playbook: Change The LLM Provider / Model

This is also a reasonable early change, but it affects answer formatting more than retrieval.

What usually changes first:
- provider endpoint/model
- readiness behavior
- prompt tuning

Files/modules most involved:
- `backend/app/llm/client.py`
- `backend/app/llm/prompts.py`
- `backend/app/core/config.py`
- `backend/app/core_rag/answering.py`

What may break:
- readiness checks
- output formatting
- citation formatting and repair behavior

What must be re-verified:
- `/ask` grounded answer output
- `/compare` grouped answer output
- answer/citation eval cases

Change class:
- safe early change if you keep answer-contract expectations stable

### Playbook: Change The Parser Method

This is safe only if you respect the current normalized output shapes.

What usually changes first:
- adapter selection
- parser logic for specific file types
- fixture data

Files/modules most involved:
- `backend/app/adapters/`
- `backend/app/ingestion/jobs.py`
- `backend/app/ingestion/chunking.py`
- parser fixtures

What may break:
- source-part extraction
- locator/provenance quality
- chunk boundaries
- retrieval snippets and citations

What must be re-verified:
- upload -> corpus -> search -> ask flow
- parser-specific chunk expectations
- provenance-sensitive citation behavior

Change class:
- moderate early change; safe only if parser output contracts remain stable

### Playbook: Move From Local Postgres To A Cloud DB

This is usually a later operational change, not the first thing to do in a fork.

What usually changes first:
- connection settings
- deployment/runtime assumptions
- migration/runbook expectations

Files/modules most involved:
- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/app/db/db.py`
- `backend/app/db/migrate.py`
- deployment and docs

What may break:
- connection assumptions
- pgvector availability
- migration flow expectations
- test and local-run instructions

What must be re-verified:
- migrations
- DB readiness checks
- vector and keyword indexing behavior
- smoke suite against the new target

Change class:
- later/scaling change

### Playbook: Move From Local File Storage To Object / Cloud Storage

This is a meaningful infrastructure change because ingestion currently expects local paths.

What usually changes first:
- upload storage handling
- runtime config
- parse-time file access assumptions

Files/modules most involved:
- `backend/app/ingestion/jobs.py`
- `backend/app/core/config.py`
- deployment/runtime docs

What may break:
- local path assumptions
- debug artifact writing
- file access during parse/chunk flow

What must be re-verified:
- `/upload`
- parsing and chunking
- debug/extracted artifact expectations
- runbook accuracy

Change class:
- later/scaling change

### Playbook: Move From Synchronous Ingestion To Async / Background Processing

This is one of the largest practical architecture changes.

What usually changes first:
- ingestion orchestration
- job stage handling
- readiness assumptions

Files/modules most involved:
- `backend/app/ingestion/jobs.py`
- `backend/app/ingestion/enrichment.py`
- `backend/app/db/repo_jobs.py`
- route-level behavior around upload readiness

What may break:
- same-request “upload becomes answerable immediately” assumptions
- job status/stage expectations
- tests that assume synchronous completion

What must be re-verified:
- upload lifecycle
- ingestion/enrichment observability
- corpus readiness expectations
- smoke flows and runbook instructions

Change class:
- later/scaling change

### Playbook: Change Retrieval Defaults Or Mode Policy

This is easy to do mechanically and easy to get wrong behaviorally.

What usually changes first:
- default mode config
- router rules
- mode-specific fallback expectations

Files/modules most involved:
- `backend/app/core/config.py`
- `backend/app/core_rag/retrieval.py`
- `backend/app/core_rag/query_router.py`

What may break:
- user expectations for omitted-mode requests
- benchmark comparability
- fallback clarity

What must be re-verified:
- manual mode selection
- router-on and router-off behavior
- compare omitted-mode behavior
- retrieval and benchmark evals

Change class:
- moderate change; safe only with eval coverage

### Playbook: Tighten Or Loosen Router Behavior

This is a policy change, not just a config change.

What usually changes first:
- query signal rules
- readiness gating
- fallback thresholds

Files/modules most involved:
- `backend/app/core_rag/query_router.py`
- `backend/app/core_rag/retrieval.py`
- `backend/app/core/config.py`

What may break:
- explainability of mode selection
- conservative fallback behavior
- adopter understanding of omitted-mode behavior

What must be re-verified:
- exact-match routing
- relationship-heavy routing
- temporal/full routing
- explicit mode non-override behavior

Change class:
- later tuning change unless you have a very clear product need

See also:
- [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [evaluation.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 8. Common Adopter Mistakes

This section is intentionally blunt.

### Mistake: Treating `full` as a universal best mode

Why it is a problem:
- `full` is not a magic super-mode
- it still relies on baseline retrieval
- its extra value depends on source scope, artifact readiness, and query type

Do instead:
- start with `hybrid`
- use `full` for temporal/version-sensitive or mixed enriched cases
- benchmark before treating it as a default

### Mistake: Changing metadata JSON casually

Why it is a problem:
- retrieval, enrichment, router behavior, and eval all depend on these internal shapes
- breakage can be subtle instead of immediate

Do instead:
- treat metadata JSON as an internal contract
- update [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md) first or alongside the change
- re-verify source metadata, retrieval fallback, and eval behavior

### Mistake: Swapping the embedding model without checking dimension and migration behavior

Why it is a problem:
- vector dimensions must stay aligned with the configured model
- stale embeddings can become invalid

Do instead:
- change the embedding model deliberately
- rerun migration logic
- re-verify vector and hybrid retrieval behavior

### Mistake: Assuming async ingestion already exists

Why it is a problem:
- current upload behavior is synchronous
- some tests and expectations rely on “upload becomes answerable in the same flow”

Do instead:
- treat async processing as a later architecture step
- document changed readiness behavior clearly if you add it

### Mistake: Assuming compare is part of the normal ask flow

Why it is a problem:
- compare is intentionally explicit
- forcing it into `/ask` would blur product behavior and answer expectations

Do instead:
- keep compare explicit unless you are intentionally redesigning the product surface

### Mistake: Assuming graph/temporal layers are enterprise-grade reasoning systems

Why it is a problem:
- current graph and temporal behavior is conservative and deterministic
- it is designed to be useful without over-claiming intelligence

Do instead:
- treat them as bounded enrichment layers
- evaluate whether they help your domain before leaning on them

### Mistake: Assuming tests are environment-free

Why it is a problem:
- the split smoke suite still depends on local Postgres and runtime setup

Do instead:
- treat current tests as strong PoC verification, not zero-infrastructure unit coverage
- improve isolation if your fork needs stronger CI safety

### Mistake: Assuming local defaults are production-ready

Why it is a problem:
- local Postgres, local file storage, router defaults, and lazy enrichment defaults are policy choices, not universal production answers

Do instead:
- decide your runtime policy deliberately
- align config, env example, and docs together

---

## 9. Known Limitations / Do Not Assume

Do not assume:
- ingestion is asynchronous; it is currently synchronous
- storage is cloud-native; it assumes local filesystem paths today
- metadata is strongly normalized; several internal contracts are still JSON-heavy
- migration/versioning is equivalent to a full framework; it is improved but still lightweight
- graph and temporal behavior are enterprise-grade reasoning systems; they are conservative PoC layers
- compare mode is a polished frontend capability; it remains backend-first
- tests are environment-free; DB-backed assumptions still exist
- router and lazy enrichment defaults are universal best practices; they are current policy choices

### Operationally useful reading of those limitations

This means:
- the repo is safest as a reusable PoC base
- adopters should change infra/runtime assumptions deliberately, not casually
- metadata and migration decisions deserve more care than the current small-file surface might suggest

See also:
- [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
- [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 10. Enterprise Upgrade Path

This section is practical, not aspirational.

### Phase 1: Reusable PoC

What this repo already has:
- upload-to-answer flow
- baseline retrieval and grounded answer flow
- explicit compare route
- optional graph/temporal enrichment
- evaluation and benchmarking harnesses
- current-state documentation

What is partial:
- migration safety
- metadata enforcement
- test isolation

What is missing:
- async operations
- cloud storage
- stronger operational controls

First engineering steps if staying in this phase:
- replace adapters/prompts/providers as needed
- add domain eval fixtures
- keep `hybrid` as the default baseline

### Phase 2: Production-ish

What this repo already has:
- clear module boundaries
- explicit config surfaces
- split smoke suite
- runbook and eval docs

What is partial:
- migration discipline
- metadata safety
- hotspot hardening

What is missing:
- stronger observability
- better environment-independent testing
- clearer infra/deployment controls

First engineering steps to move here:
- harden migrations further
- reduce environment-sensitive test assumptions
- tighten metadata enforcement and runtime tracing

### Phase 3: Enterprise

What this repo already has:
- a usable architectural backbone
- explicit retrieval/router/compare boundaries
- clear current-state docs

What is partial:
- eval discipline
- maintainability improvements

What is missing:
- async/background jobs
- object storage
- stronger migration/versioning
- richer observability
- stronger access/admin/runtime controls

First engineering steps to move here:
- introduce background job orchestration
- migrate upload storage off the local filesystem
- strengthen migration/versioning discipline
- add request/job tracing and operational controls

### Phase 4: Platform / Multi-Tenant Scale

What this repo already has:
- modular decomposition that could evolve into a stronger platform

What is partial:
- very little beyond structural starting points

What is missing:
- tenancy/workspace model
- quotas and isolation
- cost controls
- admin surfaces
- deployment automation
- platform-grade observability and lifecycle management

First engineering steps to move here:
- define tenancy and workspace boundaries first
- redesign storage, auth, and runtime control around that model
- treat this as platform work, not just another hardening pass

---

## 11. Enterprise Checklist

Use this as a blunt readiness checklist, not as a promise that the repo already satisfies it.

- [ ] async/background jobs
- [ ] cloud/object storage
- [ ] stronger migration/versioning discipline
- [ ] stronger metadata enforcement
- [ ] better observability and tracing
- [ ] stronger test isolation
- [ ] access control/admin/runtime controls
- [ ] cost controls and model controls
- [ ] multi-tenant or workspace design if relevant
- [ ] stronger deployment/ops automation

Practical interpretation:
- today the repo is best before most of these boxes
- that is acceptable for a reusable PoC base
- it is not enough to call the repo enterprise-ready

---

## 12. Common Issues / Where To Look When Something Breaks

### Upload / Parse / Chunk Issues

Look at:
- `backend/app/ingestion/jobs.py`
- `backend/app/ingestion/chunking.py`
- `backend/app/adapters/`

### Retrieval Issues

Look at:
- `backend/app/core_rag/retrieval.py`
- `backend/app/db/repo_search.py`
- `backend/app/core_rag/query_router.py`

### Enrichment / Graph / Temporal Issues

Look at:
- `backend/app/ingestion/enrichment.py`
- `backend/app/graph/`
- [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)

### Answer / Compare Issues

Look at:
- `backend/app/core_rag/answering.py`
- `backend/app/api/ask.py`
- `backend/app/api/compare.py`

### DB / Migration Issues

Look at:
- `backend/app/db/migrate.py`
- `backend/app/db/schema.sql`
- `backend/app/db/verify_db.py`

### Eval / Benchmark Issues

Look at:
- `backend/app/eval/`
- `backend/tests/fixtures/eval/`
- [evaluation.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)

See also:
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 13. Reading Order For New Maintainers

If you need the shortest practical maintainer reading order:
1. this guide
2. [README.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/README.md)
3. [configuration.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/configuration.md)
4. [architecture_overview.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
5. [module_map.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/module_map.md)
6. [api_surface.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
7. [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
8. [evaluation.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
9. [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)

---

## 14. Dense Technical Reference

This final section intentionally repeats the most important technical reference points so the file can stand alone.

### Enrichment Layers Explained Simply

#### Entity / Relation Enrichment

Purpose:
- extract lightweight structured hints from chunks
- feed graph artifact construction

#### Temporal Enrichment

Purpose:
- extract dates, windows, and document version references
- help `full` apply time-sensitive support conservatively

#### Graph Artifacts

Purpose:
- store compact source-scoped graph snapshots for relationship-aware retrieval support

#### Lazy Enrichment

Purpose:
- allow bounded source-scoped readiness work for `full` if artifacts are missing or stale

Current limit:
- one attempt
- explicit fallback
- no hidden background loop

#### Router Policy

Purpose:
- choose a mode only when `mode` is omitted
- preserve explicit caller choice

#### Compare Mode

Purpose:
- provide explicit source-bucketed reasoning across multiple sources

### What To Change First In A Fork

Recommended first changes:
1. update project identity and docs
2. choose your embedding and LLM providers
3. decide whether router and lazy enrichment should remain enabled
4. add domain fixtures
5. only then change deeper retrieval or ingestion behavior

### How To Reuse This Repo Safely

Keep first:
- backend folder structure
- schema and repo module pattern
- baseline retrieval/answer flow
- eval harness separation

Replace early if needed:
- adapters
- prompts
- provider defaults
- demo/frontend scope

Replace later if scaling:
- storage model
- ingestion orchestration
- migration discipline
- metadata enforcement

### Essential Internal Caveat

The most important internal caution in this repo is that metadata contracts matter.
If you change source metadata or chunk metadata casually, retrieval, enrichment, router, compare, and eval behavior can all drift at once.

See also:
- [internal_metadata_contracts.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/internal_metadata_contracts.md)
- [evaluation.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/evaluation.md)
- [maintainer_runbook.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/maintainer_runbook.md)
