# CLAUDE.md — Operating Manual (Enterprise RAG Starter)

This is the canonical model/agent operating manual for this repo. `AGENTS.md` is a short
mirror for Codex and defers to this file. If they ever disagree, this file wins; for
*current project state*, `STATUS.md` wins over both.

## 1. Repository identity

**What this is:** an Enterprise RAG Starter — a FastAPI + Postgres/pgvector backend and a
Next.js enterprise console for grounded retrieval with citations, SQL-level access
trimming (ACL), admin governance (drafts → compare → promote → rollback → audit), eval
packs, traces, and scenario-based reuse (`scenarios/*`). Built on the stable
RAG_MM_MASTER_POC baseline.

**What it is not:** a multi-tenant SaaS, an async pipeline platform, a multi-worker
deployment (single-process by design; guarded), a live-mailbox email connector (email =
uploaded `.eml`), or a marketing demo.

**Core philosophy:**
- Retrieval + governance are the hard parts. The LLM is last-mile generation.
- Every change preserves baseline correctness, citation provenance, and security
  boundaries. ACL trimming happens inside SQL retrieval queries, never only in UI.
- Retrieval changes must be measurable, reversible, explainable, traced, and eval-backed.

**Working style (owner preference):** work milestone-by-milestone; be concise; output the
code changes, not essays; after finishing a milestone reply "Milestone complete. Ready
for next prompt."; never re-quote CLAUDE.md/CONTEXT.md/STATUS.md content back.

## 2. Canonical reading order

1. `README.md` → `CONTEXT.md` → `STATUS.md` (always, at session start).
2. Then by task: the relevant milestone plan (tracks below) and runbook(s) in
   `docs/runbooks/`.
3. For ANY UI work: `web/DESIGN.md` and the `design-language` skill
   (`.claude/skills/design-language/SKILL.md`) — before touching code.
4. When docs conflict: `STATUS.md` = current posture > `README.md` = first-contact path >
   `docs/04_repo_navigation_blueprint.md` = canonical locations > runbooks = procedure.
   Imported docs under `docs/_master_docs/` and `docs/README_from_master.md` are
   reference-only, never current truth.

**Milestone tracks** (numbering is disjoint across tracks):
- **M-series** (`docs/02_Enterprise_RAG_Project_Plan_Milestones.md`) — original plan.
  M0–M33 complete; M20–M30 manual verification closure notes remain open. This file is
  read-only for UX/AR work.
- **AR-series** (`docs/04_Enterprise_RAG_Audit_Remediation_Milestones.md`) — audit
  remediation. **AR0–AR20 complete.** The 2026-06-11 audit findings quoted in older docs
  (broken 384/768 suite, stub query transform, exact-match "semantic" cache, no-op MMR,
  draft-active profile, thin eval packs) are **fixed** — do not re-internalize them.
- **UX-series** (`docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md`) —
  UX0–UX10 complete (2026-06-17), plus follow-ups UX11/UX12 (2026-06-30). UX0's design
  language remains binding on all frontend work forever.
- Current work is post-plan polish/features; `STATUS.md` names the current milestone.

## 3. Canonical paths

| Area | Path |
|---|---|
| Backend (active) | `backend/` — FastAPI, SQLAlchemy, pydantic-settings, `unittest` |
| API routes | `backend/app/api/` (admin surface mostly in `admin.py`) |
| Retrieval core | `backend/app/core_rag/` (retrieval, answering, router, transform, reranker, scoring, answer_strategy) |
| SQL retrieval + ACL | `backend/app/db/repo_search.py`, `backend/app/auth/access_strategy.py`, `backend/app/db/repo_acl.py` |
| Auth/identity/admin gating | `backend/app/auth/` (service, dependencies, admin_modules, high_impact) |
| Migrations / schema | `backend/app/db/migrate.py`, `schema.sql`, `repair_coherence.py` |
| Embedding + swap lifecycle | `backend/app/embedding/` (`lifecycle.py`) |
| LLM providers | `backend/app/llm/providers.py` (OpenAI-compatible / Ollama / Anthropic), `client.py` |
| Eval | `backend/app/eval/`, packs in `backend/eval_packs/`, fixtures in `backend/tests/fixtures/eval/` |
| Tests | `backend/tests/` (unittest, DB-backed against local Postgres) |
| Frontend (active) | `web/` — Next.js 15 App Router, React 19, TS strict, pnpm |
| UI primitives | `web/components/ui/*`, icons/avatars in `web/components/icons.tsx` |
| Design source of truth | `web/DESIGN.md` (mirrored by `.claude/skills/design-language/SKILL.md`) |
| Legacy UI | `frontend/` — fallback only, never build here |
| Scenario packs | `scenarios/` (enterprise_oidc_acl, employee_wide_rag, small_enterprise_corpus_acl, research_no_auth) |
| Milestone notes | `docs/milestones/` |
| Runbooks | `docs/runbooks/` |
| Local generated reports | `data/reports/` (git-ignored) |
| Reference-only | `docs/_master_docs/`, `web/stitch-reference/` (out of build) |

There is **no repository CI** (no `.github/workflows`). Verification is local:
Makefile targets + the checks named in each milestone's DoD.

## 4. Operating workflow

- Work milestone-by-milestone. When told "next milestone" / "Start X", execute exactly
  that milestone's Goal + Deliverables + DoD from its plan file — nothing more.
- Asked only to inspect/plan/audit? Report findings; edit nothing.
- Before starting: read the milestone's Goal, Deliverables, DoD, and re-run checks; read
  the runbook it names.
- After finishing: update `STATUS.md` (current + demote prior), add a concise note
  `docs/milestones/<ID>_<slug>.md`, run the required checks (§5), and report real results
  (including failures/flakes — the suite has a known access-request suite-order flake
  that passes in isolated rerun; say so if seen, don't hide it).
- Keep changes scoped. No drive-by refactors, no renames outside scope
  (e.g. `stitch-*` class renames are explicitly out of scope).

## 5. Commands

```bash
# DB (pgvector/pgvector:pg16, host port 55432, named volume)
docker compose up -d

# Dev (backend :8000 + web :3001 together; runs migrate first)
make dev-web

# Backend migrations only
cd backend && . .venv/bin/activate && python -m app.db.migrate

# Backend full test suite (DB-backed; ~357 tests as of UX12)
make test
# equivalently: cd backend && . .venv/bin/activate && python -m unittest discover -s tests

# Focused test module
cd backend && . .venv/bin/activate && python -m unittest tests.test_smoke_baseline

# Docs/onboarding contract checks
make reader-clarity-check

# Scenario validation suite (access strategy, admin modules, build packs, posture)
make scenario-validate

# Frontend type + build gate
cd web && npx tsc --noEmit && pnpm run build

# Repo hygiene (tracked-noise guard)
make repo-hygiene-check

# Eval pack run (AR3 flagship pack; reports default to data/reports/)
cd backend && . .venv/bin/activate && python -m app.eval.pack_eval --help

# Coherence repair (registry/profile/ledger drift)
cd backend && . .venv/bin/activate && python -m app.db.repair_coherence

# Seed enterprise ACL demo data
make seed-enterprise-acl
```

Local URLs: backend `http://127.0.0.1:8000` (health `/health`), web
`http://127.0.0.1:3001`. Dev logins: `test-user@ragenterprise.local` /
`test-admin@ragenterprise.local`, password `password123`. Local LLM path needs Ollama.

## 6. UI rules (binding on ALL frontend work)

- Read `web/DESIGN.md` first, every time. It names the one canonical choice per
  component/token; the skill file mirrors it.
- **No external UI dependencies, ever.** No Google Fonts, no CDN icon fonts (Material
  Symbols), no third-party image hosts. Fonts are self-hosted (`web/app/fonts/`), icons
  are inline SVG via `components/icons.tsx` (`MaterialIcon`), avatars are `Monogram`.
  The UI must render fully with the network blocked.
- One system per need: buttons `.stitch-button*`; forms `components/ui/*`
  (`Field`, `TextInput`, `NumberInput`, `Select`, `Textarea`, `Toggle`, `FormActions`);
  tables `.admin-table-scroll` > `.admin-data-table`; master/detail
  `.admin-sticky-detail`; badges `.badge -is-good/-is-warning/-is-danger`.
- No new tokens, hex values, spacing values, or CSS classes unless you also update
  `web/DESIGN.md` (and the mirror skill). Tokens live only in `app/globals.css :root`.
- `globals.css` stays sectioned (TOC header, banner-delimited sections), no orphaned
  selectors, no `AR##`/historical narration comments.
- No new Stitch wording in comments/copy and no new `stitch-*` class names; existing
  `.stitch-button*` identifiers stay (renaming is out of scope).
- Lime is accent, never status. Every data surface needs empty/loading/error states.
  Unwired controls use the "coming soon" pattern, not removal.
- Per-panel checklist: `docs/runbooks/UI_CONSISTENCY_CHECKLIST.md`.

## 7. Retrieval / governance rules

- **ACL in SQL.** Access trimming is composed into retrieval SQL via
  `access_strategy.source_access_sql` → `repo_search.py`. Never filter results only in
  Python or the UI. All 5 strategies (`none`, `employee_all`, `corpus_level`,
  `document_acl`, `document_acl_with_time_bound_grants`) must keep working.
- **Citations are the product.** Preserve the whitelist/stripping/forced-not-found
  contract in `core_rag/answering.py`; safe not-found beats an uncited answer. Keep
  source metadata and freshness on every result path.
- **Everything traced.** Retrieval decisions (routing, fusion, rerank, transform,
  degraded modes, retries) must land in traces; don't add silent behavior.
- **Eval evidence required.** Retrieval-behavior changes need before/after eval-pack or
  focused-test evidence (AR3 pack + `tuning_eval_runs` gate; enforcement is `warn` in
  `APP_ENV=local`, `require` elsewhere). Changes must be reversible (flag/profile).
- **Never hardcode embedding dimensions.** Derive from the live DB column (AR1).
  Dimension-changing model swaps go through the lifecycle
  (`POST /admin/embedding/swap/*`, `docs/runbooks/EMBEDDING_MODEL_SWAP.md`); direct
  activation of an incompatible profile is blocked by design (422
  `embedding_reindex_required`) — don't work around it.
- **Single-worker runtime.** Queue, rate limiter, and model singletons are
  single-process; the app refuses `WEB_CONCURRENCY>1` unless `ALLOW_MULTI_WORKER=true`.
  Don't casually introduce multi-worker assumptions. Sandbox/candidate profile overrides
  use the `profile_overrides` ContextVar — never module-global monkeypatching.
- Semantic cache is governed per policy (`match_mode` exact vs semantic); it is globally
  off unless a policy enables it. Disabled admin modules are **server-enforced 403**, not
  just hidden nav — gate new admin endpoints through `auth/admin_modules.py`.

## 8. Documentation rules

- `README.md` = first-contact path; `STATUS.md` = current state (update it every
  milestone); `docs/04_repo_navigation_blueprint.md` = canonical locations; runbooks =
  procedure. `docs/_master_docs/` + `docs/README_from_master.md` are imported reference,
  not current truth.
- UX/AR work must not modify `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.
- Every milestone gets a short note in `docs/milestones/` (what changed, verification
  commands + results).
- New docs get linked from the reader paths (`make reader-clarity-check` enforces the
  onboarding contract).

## 9. Git / artifact rules

- Long-lived dev branch: `RAG_Enterprise_Dev` (PRs usually target `master` only for true
  integration diffs — confirm the base before interpreting diff counts). Short-lived
  branches: `codex/`, `fix/`, `docs/` + slug.
- Milestone tags: stable lowercase (e.g. `ux12-reranker-retry-menu-2026-06-30`); one tag
  per milestone outcome.
- Never commit: `backend/.env`, `web/.env.local`, `web/tsconfig.tsbuildinfo`, build
  caches, root-level eval outputs, `data/` contents. `make repo-hygiene-check` guards
  the known offenders.
- Eval/report outputs go to `data/reports/` (ignored); keep one only by moving it to a
  documented location under `docs/` or test fixtures with a stable name.
- One commit = one milestone or one coherent fix set; imperative message; no generated
  noise mixed into functional commits.

## 10. Mistakes weaker models make here (and the prevention rule)

1. **Trusting stale audit findings** (384-dim errors, stub transform, exact-match cache,
   no-op MMR) quoted in older docs/CONTEXT → those were remediated in AR1–AR14. Rule:
   `STATUS.md` + `docs/milestones/` define current truth; verify any old claim there.
2. **Building in `frontend/`** → it is legacy fallback only. Rule: all UI work happens in
   `web/`; touch `frontend/` only when explicitly validating `/frontend` compat.
3. **Adding a CDN/Google dependency** (font, icon font, remote avatar) → Rule: grep your
   diff for `fonts.googleapis`, `gstatic`, `googleusercontent`, `cdn`; the UI must render
   network-blocked.
4. **Inventing a second button/control/table system** → Rule: reuse `.stitch-button*`,
   `components/ui/*`, `.admin-data-table`; if the primitive doesn't exist, extend
   `web/DESIGN.md` first, deliberately.
5. **Editing the M-series plan during UX/AR work** → Rule:
   `docs/02_…Milestones.md` is read-only for those tracks.
6. **Skipping `web/DESIGN.md`** and styling from taste → Rule: load the design-language
   skill before the first UI edit; no new token/hex/class without a DESIGN.md update.
7. **Filtering results in the UI or Python instead of SQL** → Rule: access trimming lives
   in `source_access_sql` composed into `repo_search.py` queries; a UI-only filter is a
   security regression even if tests pass.
8. **Hardcoding 384/768 vector dimensions** in tests, fixtures, or registry metadata →
   Rule: derive dimensions from the live DB column; suite must be green on both a fresh
   384-dim DB and the tuned 768-dim dev DB.
9. **Changing retrieval scoring/routing "obviously for the better" without evidence** →
   Rule: no retrieval change ships without before/after eval or focused-test numbers in
   the milestone note, and a way to turn it off.
10. **Treating disabled admin modules as UI-only** → Rule: module gating is server-side
    (403 via `auth/admin_modules.py`); new admin endpoints must be assigned to a module.
11. **Committing local artifacts** (`backend/.env`, `web/.env.local`,
    `tsconfig.tsbuildinfo`, root eval JSON) → Rule: run `make repo-hygiene-check` and
    review `git status` before committing.
12. **Assuming multi-worker is fine** → Rule: single-process is a named constraint
    (AR8); anything relying on cross-request shared state must note it, and never set
    `ALLOW_MULTI_WORKER=true` as a "fix".
13. **Directly activating an embedding profile with a different dimension** → Rule: use
    the AR7 swap lifecycle endpoints + runbook; expect vector search to degrade to
    keyword-only mid-swap (that's by design, traced as `degraded_vector`).
14. **Declaring done on partial checks** → Rule: the DoD's re-run checks are the
    definition of done; report the actual counts/output, including known flakes.

## 11. Quality bar per deliverable type

**Backend API/retrieval change**
- `make test` green (full DB-backed suite; isolated rerun for known flaky modules is
  acceptable if noted); focused new tests for the change.
- Citations + safe not-found behavior demonstrated unchanged (smoke:
  `tests.test_smoke_baseline`).
- ACL: `make scenario-validate` green; if retrieval SQL touched, confirm
  `source_access_sql` still composed on every query path.
- Behavior change traced; reversible via flag/profile; retrieval-quality changes carry
  eval-pack before/after numbers.
- `python -m compileall -q backend/app` clean.

**Frontend/UI change**
- `cd web && npx tsc --noEmit && pnpm run build` green (build currently 12/12 routes).
- Zero new external hosts in the diff; only canonical primitives/classes; tokens
  unchanged or `web/DESIGN.md` updated in the same change.
- `globals.css` additions in the right section; no orphaned selectors.
- Empty/loading/error states present on new data surfaces; keyboard focus visible.

**DB/migration change**
- New migration appended in `app.db.migrate` with a `MIG-P0xx` ledger entry; ledger ==
  plan assertion still passes (suite enforces it).
- `python -m app.db.migrate` idempotent on an already-migrated DB; `make test` green on
  a fresh DB.
- No destructive change without an explicit milestone calling for it.

**Eval/retrieval-quality change**
- Pack JSON validates and runs via `python -m app.eval.pack_eval`; report committed only
  if it is milestone evidence (else `data/reports/`).
- Baseline vs candidate numbers (recall@k / MRR / nDCG / faithfulness) recorded in the
  milestone note; degraded control still fails the gate.
- Feedback-derived cases stay quarantined (`unreviewed`) until human-labeled
  (`docs/runbooks/EVAL_PACK_LABELING.md`).

**Scenario-pack change**
- `scenarios/<name>/` keeps README, `admin_modules.json`, both `*.env.example`, and
  `validation.md` coherent with each other.
- `make scenario-validate` green; module subset doesn't break another enabled panel.

**Docs/manual change**
- `make reader-clarity-check` green; links resolve; no duplicate source of truth
  created; `STATUS.md` updated if posture changed.

## 12. Escalation rules — stop and ask when

- Source-of-truth docs still conflict after applying the hierarchy in §2 (STATUS.md
  first).
- The task seems to require weakening citation enforcement, SQL-level ACL, audit, module
  gating, or any governance behavior — even temporarily.
- Milestone scope/order would change, or a milestone's DoD can't be met as written.
- A new dependency (pip/npm) is needed — the frontend deliberately has 5 runtime deps
  and the backend list is curated.
- Work would touch secrets, auth flows, CSRF/cookie behavior, or security posture beyond
  what the milestone explicitly requests.
- Tests fail for reasons you don't understand after focused debugging (isolated rerun,
  fresh-DB check, migration check) — report the failure output instead of forcing green.
- The change conflicts with a scenario's assumptions (e.g. would require per-document
  ACL in `research_no_auth`, or break the module subset of a shipped scenario).
- You'd need `ALLOW_MULTI_WORKER=true`, a bypass of the embedding-swap lifecycle, or an
  edit to `docs/02_Enterprise_RAG_Project_Plan_Milestones.md`.

## 13. Repo-specific skills

The three highest-leverage skills for this repo. `design-language` already exists at
`.claude/skills/design-language/SKILL.md`; the other two are specified here so any agent
can execute them as procedures (or materialize them as skill files).

### Skill 1: `design-language-ui-change`

- **When to use:** any create/edit of UI under `web/` — components, pages, CSS, copy.
- **Inputs to read:** `web/DESIGN.md`; `.claude/skills/design-language/SKILL.md`;
  `web/app/globals.css` (the section your rules belong in); the canonical primitive
  you'll reuse (`components/ui/*`, `components/icons.tsx`);
  `docs/runbooks/UI_CONSISTENCY_CHECKLIST.md` for admin panels.
- **Workflow:**
  1. Identify the canonical primitive/pattern for the need (button / form / table /
     master-detail / badge / icon / empty-loading-error). If none fits, propose a
     DESIGN.md extension before coding.
  2. Build using only `:root` tokens; no new hex/spacing; place CSS in the correct
     `globals.css` section.
  3. Apply the vocabulary in DESIGN.md §5b (Ask/Search/History/Source/Citation/…); em
     dash for missing values; "coming soon" pattern for unwired controls.
  4. Self-audit the diff: no external hosts, no new `stitch-*` names or Stitch wording,
     no bare tables, no newline-split answer rendering, focus-visible preserved.
- **Outputs:** the UI change; DESIGN.md + skill-mirror update if (and only if) the
  language was deliberately extended.
- **Verification:** `cd web && npx tsc --noEmit && pnpm run build` green;
  `grep -nE "googleapis|gstatic|googleusercontent|cdn\." <changed files>` empty;
  visually confirm empty/loading/error states; admin panels pass the per-panel sign-off
  list in the UI consistency checklist.

### Skill 2: `retrieval-governance-change`

- **When to use:** any change to `backend/app/core_rag/`,
  `backend/app/db/repo_search.py`, access strategies, reranker/router/transform,
  semantic cache, or answer strategy.
- **Inputs to read:** `docs/runbooks/SAFE_EXTENSION_BLUEPRINT.md`; the touched module +
  `repo_search.py`; `auth/access_strategy.py`; `core_rag/answering.py` (citation
  contract); the relevant AR milestone note in `docs/milestones/` (AR3–AR7, AR14 define
  the invariants); `backend/eval_packs/`.
- **Workflow:**
  1. Confirm the change point per the safe-extension order (providers/access/packaging
     before retrieval internals).
  2. Capture a baseline: focused smoke tests + `python -m app.eval.pack_eval` on the AR3
     pack (report → `data/reports/`).
  3. Implement behind a flag/profile field so it is reversible; thread every decision
     into the trace payload; keep ACL SQL composition and citation
     whitelist/strip/not-found untouched (or explicitly tested if touched).
  4. No hardcoded dimensions; sandbox/candidate state only via the `profile_overrides`
     ContextVar; no new cross-request shared state (single-worker constraint).
  5. Re-run the eval pack; compare recall@k/MRR/nDCG deltas; run
     `make scenario-validate` and the full `make test`.
- **Outputs:** scoped diff; new focused tests; milestone/change note with before/after
  eval numbers and the rollback lever.
- **Verification:** full suite green; scenario validation green; eval delta recorded and
  non-regressive (or the regression explicitly accepted in the note); a trace from a
  live local query shows the new decision fields.

### Skill 3: `milestone-release-gate`

- **When to use:** finishing any milestone or coherent feature before declaring done /
  committing / tagging.
- **Inputs to read:** the milestone's Goal/Deliverables/DoD in its plan file;
  `STATUS.md`; `docs/runbooks/SOURCE_CONTROL_WORKFLOW.md`.
- **Workflow:**
  1. Re-read the DoD and tick each deliverable against the actual diff.
  2. Run the gate: `make test` (note the count; isolated rerun for known flaky modules,
     reported honestly), `cd web && npx tsc --noEmit && pnpm run build` if `web/`
     changed, `make scenario-validate` if auth/ACL/modules changed,
     `make reader-clarity-check` if docs changed, `make repo-hygiene-check` always.
  3. Update `STATUS.md`: new "current" entry with verification results; demote the prior
     entry; refresh the verification-debt lines the change affects.
  4. Write `docs/milestones/<ID>_<slug>.md`: what changed, why, exact verification
     commands + results, any deferred items.
  5. Review `git status` for artifact noise; one scoped commit with an imperative
     message; milestone tag (stable lowercase) only when the milestone is truly
     complete.
- **Outputs:** green gate evidence, updated `STATUS.md`, milestone note, clean scoped
  commit (+ tag when applicable).
- **Verification:** every DoD line has evidence; no tracked local artifacts
  (`make repo-hygiene-check` passes); STATUS.md's "current" section describes this
  milestone.
