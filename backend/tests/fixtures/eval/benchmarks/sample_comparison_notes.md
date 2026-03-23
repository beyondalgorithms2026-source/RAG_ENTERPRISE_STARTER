# Sample Benchmark Notes

These notes are an example of how to interpret the M20 benchmark output without inventing a universal winner.

## Relationship-Heavy Case

- `hybrid` returned grounded evidence quickly and passed the benchmark expectations.
- `graph_hybrid` also passed and resolved through the graph-aware path.
- For this dataset, graph support may be justified when relationship wording is strong and graph artifacts are current.

## Temporal Case

- `full` may help when temporal metadata is available and the query is clearly time-sensitive.
- If temporal artifacts are missing or stale, the report should show that through fallback or failure-mode observations rather than silently assuming benefit.

## Interpretation Rule

- Treat benchmark output as evidence for this dataset and case set.
- Do not turn a single benchmark pass into a universal policy.
- Use per-case observations, citation quality, and latency together.
