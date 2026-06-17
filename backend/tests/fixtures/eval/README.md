M19 evaluation fixtures

These JSON case files are eval-only inputs. They are intentionally simple and inspectable:

- `retrieval_cases.json`: retrieval-mode relevance checks
- `router_cases.json`: router benchmark cases across quote / code / semantic / temporal query sets
- `answer_cases.json`: grounded ask-path checks
- `compare_cases.json`: explicit compare-path grouping and citation checks
- `benchmark_cases.json`: M20 same-query multi-mode benchmark cases
- `corpus_policy_cases.json`: M9 corpus-policy eval matrix across legal, transcript, and structured-row behaviors

Some cases use runtime bindings such as `graph_source_id`, `temporal_source_id`, or `compare_source_ids`.
Those placeholders are filled by tests or ad-hoc eval runners against seeded local data.

Benchmark cases may also declare `fusion_methods` when the same query should be compared across both `linear` and `rrf` hybrid fusion settings.

Benchmark cases may also declare `rerank_variants` with `label` and `overrides` fields to compare rerank-off vs rerank-on behavior under the same query.

Benchmark artifact examples live under:

- `benchmarks/`
