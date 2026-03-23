M19 evaluation fixtures

These JSON case files are eval-only inputs. They are intentionally simple and inspectable:

- `retrieval_cases.json`: retrieval-mode relevance checks
- `answer_cases.json`: grounded ask-path checks
- `compare_cases.json`: explicit compare-path grouping and citation checks
- `benchmark_cases.json`: M20 same-query multi-mode benchmark cases

Some cases use runtime bindings such as `graph_source_id`, `temporal_source_id`, or `compare_source_ids`.
Those placeholders are filled by tests or ad-hoc eval runners against seeded local data.

Benchmark artifact examples live under:

- `benchmarks/`
