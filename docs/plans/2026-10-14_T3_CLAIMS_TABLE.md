# T3 claims table — 2026-10-14 (step 11)

Every number or factual claim a visitor can see on the live demo or in the three READMEs, checked against its
source on 14 Oct. "Live" = `https://rag-enterprise-governance-demo.onrender.com` read in a browser on 14 Oct
(APP `945c89c`). Model switch to Claude Haiku 5.5 on both Render services: 2026-10-12 (STARTER `a8ce498`,
APP `33bf1d1`). Everything recorded before that used `gpt-4o-mini-2024-07-18`.

Status: **true** · **label** (true, but model/date missing) · **stale** (number out of date) · **wrong**.

## Live pages

| # | Claim | Where | Source | Value shown | Status | Fix (on `t3/close-2026-10-14`) |
|---|---|---|---|---|---|---|
| L1 | "As of 5 Oct 2026" | How it works, header | — | 5 Oct | stale | 14 Oct |
| L2 | Answer model | How it works diagram ("Claude · pinned model"); wire "embed · generate" | Render config, `/metrics/live` | Claude, no version; wire implies Claude embeds | wrong | Name Claude Haiku 5.5 for answers and OpenAI text-embedding-3-small for embeddings |
| L3 | APP 288 tests | How it works (diagram + repo card) | CI on main: 354; branch: 358 | 288 | stale | 358 |
| L4 | MCP 42 tests | How it works, MCP README | CI on main | 42 | true | — |
| L5 | STARTER 148 tests | How it works, STARTER README | CI on main `b774cab`: 163 run, 36 DB skips | 148 | stale | 163 (127 passed without DB, 36 skips) |
| L6 | Northwind v1 core 25/25 approved baseline | How it works results; Quality card | `northwind-openai-v1.json` | 25/25, no model/date | label | "gpt-4o-mini · 12 Sep 2026" |
| L7 | Northwind v2 expanded 82/90 candidate (3 failed, 5 review) | How it works results; Quality card | `status.json` (CI run 35186725102) | 82/90, no model/date | label | "gpt-4o-mini · 17 Sep 2026" |
| L8 | Northline demo set 15/20 | How it works results; Quality card (model shown) | `northline-scorecard.json` (5 Oct) | 15/20 | stale | 14 Oct Haiku 5.5 run (see decision D1) |
| L9 | Northline misses WQ-01/04/14/19/20 | Quality card | 5 Oct scorecard | 5 misses | stale | From the 14 Oct run |
| L10 | Refusals 5/5 Northline · 8/8 Northwind | How it works, exhibit 02 | 14 Oct run; status.json | 5/5 · 8/8 | true | add dates in results table |
| L11 | "A poisoned document planted in the Northline corpus was never cited" | How it works, exhibit 06 | poison-test (10-05) + poison-test-haiku (10-14): cited in P3 when asked about by name | never cited | wrong | "never treated as policy; cited only when asked about by name, and then described as a planted test line" |
| L12 | 20 red-team scenarios, 18 deterministic + 2 live, 20/20 defended | How it works exhibit 06; README | `red-team-release.json` (17 Sep) | 20/20 | true | add release date |
| L13 | "20 deterministic defenses · 2 live controls" | Security page summary | release: 18 deterministic + 2 live | 20 + 2 | wrong | "18 deterministic defenses · 2 live controls" |
| L14 | "Northline's equivalents are the WQ-12 access denial and the WQ-19 poison-document test" | Security page | WQ-19 = direct injection blocked at input; poison doc = P1–P5 probes | — | wrong | "WQ-12 access denial, WQ-19 direct-injection block, and the poisoned-document probes" |
| L15 | "Same question, same model, two paths" | Compare page | `before-after-recorded.json` 2026-09-23 | no model | label | "recorded 23 Sep 2026 on gpt-4o-mini" |
| L16 | "A full 90-question evaluation costs about $0.03" | How it works | eval-usage.json: $0.0376 (6 Oct), $0.0445/0.0455 (14 Oct), gpt-4o-mini | $0.03 | label | "about $0.04 with gpt-4o-mini (14 Oct)" |
| L17 | Timeline ends 5 Oct | How it works | — | — | stale | add 12 Oct (switch to Haiku 5.5) and 14 Oct (Haiku re-run, findings, fix) |
| L18 | Source counts (Northwind 28 / 14 visible; Northline 14 / 13 visible) | Ask, Documents, README | `/metrics/live`, `/corpus` | 28/14, 14/13 | true | — |
| L19 | "Restricted documents never leave the database" + WQ-12 | How it works exhibit 01 | 14 Oct ACL check; RT-06/RT-16 CI 14 Oct | — | true | — |
| L20 | All links on public pages and READMEs (28) | — | HTTP check 14 Oct | all resolve | true | — |
| L22 | "two live checks against the deployed backend" (RT-06/RT-16) | How it works exhibit 06; READMEs ("live backend controls") | CI P12B isolated stack, not the deployed backend | wrong | "live full-stack access-control checks in CI" |
| L21 | Banned wording (secure / certified / compliant / production client) | public pages + READMEs | grep 14 Oct | none | true | — |

## READMEs

| # | Claim | Where | Status | Fix |
|---|---|---|---|---|
| R1 | Current answer model never named | APP, STARTER, MCP READMEs | label | One line: answers by Claude Haiku 5.5 (since 12 Oct 2026), embeddings OpenAI text-embedding-3-small |
| R2 | 25/25 v1 baseline | APP, STARTER, MCP READMEs | label | "gpt-4o-mini, 12 Sep 2026" |
| R3 | 82/90 v2 candidate | APP, STARTER, MCP READMEs | label | "gpt-4o-mini, 17 Sep 2026" |
| R4 | STARTER "148 tests / 112 / 36" | STARTER README | stale | 163 / 127 / 36 (CI `b774cab`) |
| R5 | Northline scorecard link → `scorecard.md` | APP README | true (link) | content updated in step 5 |
| R6 | 20/20 red-team | all READMEs | true | — |

## Historical records (left as dated history)

| File | Claim | Decision |
|---|---|---|
| APP `BUILD_LOG.md` | "10 red-team scenarios: 9 defended, 0 failed, 1 requires_backend" (Aug–Sep entries) | Dated log entries; true when written; later entry records 20/20. Leave. |
| APP `docs/EVALUATION_CORRECTION_PROGRESS.md`, `RELIABILITY_FIX_VERIFICATION_2026-09-15.md` | "18 defended, 2 require backend" | Offline-run view, dated; consistent. Leave. |
| APP `status.json`, `red-team-release.json`, `candidate-v2-report.json` | evidence files | Checksum-pinned evidence; already carry model and date. Leave. |

## Result (14 Oct, on `t3/close-2026-10-14`)

All rows above marked stale / wrong / label are fixed on the branches: APP `ddc9bf6` (pages, Northline card,
README; 358 tests, ruff clean, cross-repo contract check passes; rendered and checked on a local preview of the
branch), STARTER README (models, 163 tests), MCP README (models). Every row is now **true** or **labelled with
date + model** on the branches. Live verification after the final merge happens in steps 12 and 14.
STARTER `docs/evaluation/western/scorecard.md` (linked from the pages) still shows the 5 Oct run until step 5.

## Live re-check after deploy (14 Oct, APP `691113c` live at 17:49:19 UTC)

All fixed rows confirmed on the live URL (desktop and 375 px phone width). One new row:

| # | Claim | Where | Observed | Status | Fix |
|---|---|---|---|---|---|
| L23 | "Internal and restricted documents are excluded by SQL before retrieval — their names do not appear." | APP README, Documents row | The Documents page deliberately notes "+1 restricted Northline document (incident SOP) exists"; a public policy cites `NL-OPS-SOP-INCIDENT` by ID. Restricted content is never listed or retrieved. | wrong (overstated) | Follow-up APP PR: "never listed or retrieved; the page notes only that one restricted Northline document (the incident SOP) exists." |
