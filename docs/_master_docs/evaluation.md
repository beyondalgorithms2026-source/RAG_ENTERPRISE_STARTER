# Evaluation Guide

This document explains the current evaluation harnesses added through M20.

For a repo-wide orientation first:
- [master_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)

## Eval Modules

Current eval-only modules:
- [backend/app/eval/retrieval_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/retrieval_eval.py)
- [backend/app/eval/enriched_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/enriched_eval.py)
- [backend/app/eval/compare_eval.py](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/backend/app/eval/compare_eval.py)

These are evaluation-only surfaces and should not change production behavior.

## Fixture Locations

Current eval fixtures live under:
- `backend/tests/fixtures/eval/`

Current fixture files:
- `retrieval_cases.json`
- `answer_cases.json`
- `compare_cases.json`
- `benchmark_cases.json`

Benchmark artifact examples live under:
- `backend/tests/fixtures/eval/benchmarks/`

## Fixture Authoring Basics

All current eval fixtures are JSON files under `backend/tests/fixtures/eval/`.

Keep fixtures:
- small enough to read by hand
- source-scoped where possible
- explicit about expected evidence
- stable across reruns

Avoid:
- brittle exact-answer expectations
- hidden dependence on whichever source ids happen to exist in one local DB
- overly broad “this mode must always win” assumptions

### Source Id Bindings

Some fixture cases refer to runtime source ids that are only known after seeding test data.

Handle that by:
- using stable placeholder-style fixture fields
- passing runtime bindings when invoking the eval harness
- keeping the fixture itself portable instead of baking in local DB ids

Good rule:
- fixtures should describe the case
- runtime bindings should attach fixture placeholders to real seeded source ids

## How To Add A New Retrieval Case

File:
- `backend/tests/fixtures/eval/retrieval_cases.json`

Use retrieval cases when you want to evaluate:
- `vector`
- `keyword`
- `hybrid`
- `graph_hybrid`
- `full`
- explicit `deep_lookup` retrieval

Fields that matter most:
- `id`
- `surface`
- `question`
- `request`
- `expected_mode` or `acceptable_modes`
- `expected_source_ids`
- `expected_keywords_any`
- `expected_keywords_all`
- `expected_fallback`

Practical guidance:
- prefer expected evidence presence over exact ranking of every row
- keep lexical cases clearly lexical
- keep semantic cases free of exact-term-only shortcuts
- for enriched modes, make the artifact dependency obvious in the case notes
- use `surface: "deep_lookup"` for explicit source-scoped rescue retrieval cases

## How To Add A New Answer Case

File:
- `backend/tests/fixtures/eval/answer_cases.json`

Use answer cases when you want to evaluate:
- grounded `/ask` behavior
- citation support
- safe fallback or “not found” behavior

Fields that matter most:
- `id`
- `question`
- `request`
- `expected_citation_source_ids`
- `expected_keywords_any`
- `expected_keywords_all`
- `expected_fallback`

Practical guidance:
- do not require one exact answer wording
- check whether cited evidence supports the answer
- prefer support checks like source coverage, snippet overlap, and key terms

## How To Add A New Compare Case

File:
- `backend/tests/fixtures/eval/compare_cases.json`

Use compare cases when you want to evaluate:
- explicit `/compare` behavior
- grouped evidence by source
- compare citation discipline

Fields that matter most:
- `id`
- `question`
- `request`
- `expected_source_ids`
- `expected_citation_source_ids`
- `expected_keywords_any`
- `expected_fallback`

Practical guidance:
- keep compare scope explicit with source ids or clearly bound source scope
- verify grouped evidence, not just one final answer string
- avoid compare cases that silently depend on corpus-wide discovery

## How To Add A New Benchmark Case

File:
- `backend/tests/fixtures/eval/benchmark_cases.json`

Use benchmark cases when you want to run the same query across:
- `vector`
- `keyword`
- `hybrid`
- `graph_hybrid`
- `full`
- and, where relevant, explicit `deep_lookup`

Fields that matter most:
- `id`
- `category`
- `question`
- `notes`
- runtime source binding fields if needed

Practical guidance:
- choose cases that make tradeoffs visible
- prefer one clear question pattern per case:
  - simple lookup
  - exact-term lookup
  - cross-file summary
  - relationship-heavy query
  - temporal query
- keep benchmark expectations descriptive rather than prescriptive

## Keeping Fixtures Stable And Inspectable

Recommended habits:
- keep cases short and concrete
- use obvious filenames and ids
- write notes explaining why a case exists
- make fallback expectations explicit when relevant
- keep one fixture change tied to one behavior question when possible

Avoid brittle expectations such as:
- exact long answer text
- exact floating-point scores
- exact ranking beyond the evidence that actually matters

Prefer expectations such as:
- expected source appears
- citation source is correct
- expected key evidence terms are present
- fallback was or was not observed

## What Gets Evaluated

Retrieval modes:
- `vector`
- `keyword`
- `hybrid`
- `graph_hybrid`
- `full`

Additional evaluation coverage:
- ask grounding behavior
- citation correctness checks
- fallback behavior
- compare-mode grouped evidence behavior
- same-query multi-mode benchmarking

## Report Style

The current harnesses are JSON-first and intentionally simple.

Current report shape is centered on:
- `summary`
- `results`
- `failures`
- `report_path`

This is meant for inspectable debugging and iteration, not a complex scoring platform.

## Current Evaluation Principles

- pass/fail plus observed details is preferred over brittle exact-answer matching
- grounding and citation support matters more than verbatim wording
- compare evaluation remains explicit and source-scoped
- fallback behavior is evaluated as a first-class outcome

## Recommended Usage

Use the eval harnesses to compare:
- baseline retrieval behavior
- enriched retrieval behavior
- full-mode behavior with and without usable artifacts
- compare-mode grounded grouping behavior
- same-query behavior across `vector`, `keyword`, `hybrid`, `graph_hybrid`, and `full`

## M20 Mode Comparison Benchmarking

The M20 benchmark harness is intended to make complexity measurable rather than assumed.

Current benchmark scope:
- simple lookup
- exact-term lookup
- cross-file summary
- relationship-heavy query
- temporal query

Current benchmark output is descriptive, not prescriptive:
- it records what happened per mode
- it does not declare a universal winner
- it is meant to show when enriched modes help and when they do not for the current dataset and case set

Current deep lookup note:
- `deep_lookup` is retrieval-only
- benchmark retrieval relevance remains meaningful for that mode
- answer and citation sections are not applicable in the same way they are for `/ask`-backed modes

Current benchmark report includes per mode:
- retrieval relevance summary
- citation quality summary
- answer clarity note/pass heuristic
- latency
- failure-mode note

Example benchmark run:

```bash
cd backend
PYTHONPATH=. venv/bin/python -m app.eval.compare_eval \
  --bind benchmark_source_id=123 \
  --report ../backend/tests/fixtures/eval/benchmarks/local_benchmark_report.json
```

Use runtime bindings when fixture cases refer to seeded source ids.

When adapting this repo:
- keep eval fixtures domain-specific
- avoid coupling eval success to one exact answer wording
- preserve the separation between eval code and production code

## Related Docs

- [master_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/master_guide.md)
- [api_surface.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/api_surface.md)
- [adoption_guide.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/adoption_guide.md)
- [architecture_overview.md](/Users/Work/local_dev/RAG%20workflow/RAG_MM_MASTER_POC/docs/architecture_overview.md)
