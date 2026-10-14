# Western (Northline) eval — 2026-10-14 run on Claude Haiku 5.5

Synthetic corpus (Northline Analytics Ltd) and 20 demo questions. Demo evidence, not a benchmark.

## Run

| Field | Value |
|---|---|
| Date | 2026-10-14, 08:57:18–09:04:50 UTC (counted run) |
| Answer model | `claude-haiku-5-5` (Anthropic), temperature 0, called by hosted STARTER |
| Embeddings | `text-embedding-3-small` (OpenAI), 384 dims, called by hosted STARTER |
| STARTER | `b774cab`, hosted on Render (`rag-enterprise-starter-demo`; deploy commit confirmed by owner in the Render dashboard) |
| APP (LangGraph) | `945c89c`, runner on the operator machine; settings matched to Render: synthesis on, corpus `western_northline`, 1 recovery step |
| MCP | `f8e891d` (live pin in `scripts/render_build.sh`); the local checkout used has identical `src/` |
| Eval set | `eval/western/generated/eval-set-western-northline.json`, sha256 `d589985d1e815ce323e7227d56d6225cc4e165770ed93113489f4605cec3c37c`, regenerated with `western_eval.py convert`, unchanged from git |
| Scoring | `western_eval.py scorecard --model claude-haiku-5-5 --max-recovery-steps 1` (no LLM judge) |
| Live config check | `GET /metrics/live` on 14 Oct: `anthropic / claude-haiku-5-5`, `openai / text-embedding-3-small`, retrieval `hybrid`, rerank off |

## Result

exact_fact 7/8 · open 4/5 · refuse 5/5 (includes the WQ-12 permission check) · adversarial 1/2. exact_fact hit-rate 0.88 (gate 0.70 met).
Infrastructure failures: 0. Backend ask calls: 27 (8 cases used the 1 recovery step).

## Permission check (WQ-12, restricted incident SOP)

| Check | Result |
|---|---|
| WQ-12 as anonymous visitor | `not_grounded`, no citation; "No grounded answer could be produced from the available MCP evidence." |
| Restricted doc id in `used_doc_ids` / anywhere in the WQ-12 row | absent (`NL-OPS-SOP-INCIDENT` not found) |
| `GET /corpus?corpus=western_northline` as anonymous | 13 documents listed; `NL-OPS-SOP-INCIDENT` not listed |

The restricted document is removed by SQL access trimming, so the visitor sees a safe "no grounded answer", not an explicit "access denied" message.

## Run log

| # | Time (UTC) | What happened | Counted? |
|---|---|---|---|
| 1 | 08:55:36–08:56:35 | Unpaced. Haiku 5.5 answered fast enough that the run exceeded the hosted limit of 12 ask calls/min/IP; after 12 calls, WQ-12…18 and WQ-20 got HTTP 429 (no model call). Kept in `attempt-1-ratelimited/`. | No |
| 2 | 08:57:18–09:04:50 | Full re-run of all 20, paced with a 12 s wait before each case (wrapper around the unchanged CLI; runner, scoring and eval set untouched). | **Yes** |
| 3 | 09:31:03–09:37:20 | Same paced full run on APP `5862921` (T3 fix for WQ-04/WQ-14, on branch, **not yet deployed**). Results in `with-fix-5862921/`. Shown as a second column, never as the live result until the fix is deployed. | Second column |

No individual items were re-run.

**With-fix result (APP 5862921):** exact_fact 8/8 · open 5/5 · refuse 5/5 · adversarial 1/2 (WQ-19 documented). 0 infrastructure failures.

## Notes for readers

- **Latency:** `latency_ms` in `scorecard.md` includes the 12 s pacing wait. Without it: median 6.0 s, max 21.2 s per case (10-05 gpt-4o-mini run: median 6.7 s, max 19.0 s).
- **"declined" note on passing rows (WQ-07, WQ-20):** the scorecard script flags hedged wording ("not stated in the sources") as a decline. Both answers contain the gold facts and pass; the note does not change any score. Logged in the plan's decision log; the script is unchanged.
- **Synthesis:** enabled as on Render, but no case reached the excerpt-recovery path that uses it, so every answer shown is STARTER's Haiku 5.5 answer.

## Cost

All model calls were made by hosted STARTER with the live Render key: attempt 1 (12 ask calls), counted run (27), poison/WQ-04/WQ-14 probes 09:23–09:26 UTC (9), with-fix run 09:31–09:37 UTC (25), plus query embeddings. The local eval key was loaded but not used, because synthesis was not triggered.

| Source | Amount |
|---|---|
| Estimate (Haiku 5.5 at $0.10 / $0.50 per MTok) | ≈ $0.16 for all four runs on 14 Oct |
| Actual: Anthropic Console, live key, 08:55–09:38 UTC | _pending owner reading_ |
| Actual: Anthropic Console, eval key | _pending owner reading (expected $0)_ |
| Actual: OpenAI embeddings | _pending owner reading (expected < $0.01)_ |
