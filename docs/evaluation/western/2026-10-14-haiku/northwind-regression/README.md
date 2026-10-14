# Northwind 90-case regression check for the WQ-04/WQ-14 fix — 2026-10-14

Synthetic corpora (Northwind Logistics + Operations Manual v3.2). Two paired CI runs on an isolated stack
(`full-eval.yml`, P12B: APP → MCP → STARTER → PostgreSQL/pgvector), identical except for the APP commit.

| | Baseline | With fix |
|---|---|---|
| APP | `945c89c` (live main) | `5862921` (T3 branch) |
| STARTER / MCP | `main` (`b774cab`) / `main` | same |
| Model (pinned by the workflow) | `gpt-4o-mini-2024-07-18` | same |
| Run | [38551336724](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP/actions/runs/38551336724) | [38551348891](https://github.com/beyondalgorithms2026-source/RAG_ENTERPRISE_LANGGRAPH_APP/actions/runs/38551348891) |
| Pass / fail / manual review | 79 / 4 / 7 | 79 / 4 / 7 |
| Refusals / safe boundaries | 8/8 · 2/2 | 8/8 · 2/2 |
| Infrastructure failures | 0 | 0 |
| RT-06 SQL authorization job | passed | passed |
| Generation cost (sanitized usage export) | $0.0445 | $0.0455 |

**Result: no regression.** Totals are identical. Four cases changed status in opposite directions
(OM-015 and OM-084: manual_review → pass; OM-040 and OM-045: pass → manual_review). In all four the APP
validation result was the same in both runs; the answer text differed (76 of 90 answers are word-for-word
identical between runs) and the grader scored the wording differently. None of the four is a question whose
classification changes under the fix: across all 200 eval questions only Western WQ-01, WQ-04 and WQ-14 change.
This matches the run-to-run variance recorded in the APP's v2 calibration notes (5–6 Oct 2026).

Per-case statuses: [`comparison.json`](comparison.json).

**Harness note.** The workflow's default STARTER ref (`codex/eval-correction`) no longer installs: it allows
SQLAlchemy 2.1, which needs psycopg v3, so the seed and RT-06 steps failed at import (runs 38544043503 and
38544054243, cancelled, no answers generated). APP `1b8ba5a` adds optional `app_ref` / `starter_ref` dispatch
inputs; defaults are unchanged. These runs used `starter_ref=main`, which pins SQLAlchemy < 2.1.

These runs check the APP code change only. They are not Claude Haiku 5.5 results and are not the published
Northwind baseline.
