# UX0 — Establish The Design Language

**Date:** 2026-06-17 · **Plan:** `docs/05_Enterprise_RAG_UIUX_Audit_Remediation_Milestones.md` · **Gate:** UX0 (one written source of truth)

## Provenance

First milestone of the UX-series, driven by the 2026-06-17 UI/UX audit. The audit's root-cause finding: there is no shared design language, so screens drifted (two button systems, two token vocabularies, orphaned classes behind Search, external font/icon/image deps). UX0 writes the grammar so UX1–UX10 compose against one source of truth instead of inventing.

## Deliverables (docs/decisions only — no render changes)

- **`web/DESIGN.md`** — canonical design language: principles; tokens documented from the real `app/globals.css :root` vars (surfaces, ink, brand/semantic colors, spacing scale 4/8/12/16/24/32/48, radii, Inter type scale, shadows); the **palette decision** (keep current palette; status = semantic tokens only; lime is accent not status; neutral re-skin out of scope; verify muted-on-tan contrast in UX8); canonical components table; patterns (data-table, master/detail, answer+citation, form, states); explicit **"do not"** list.
- **`.claude/skills/design-language/SKILL.md`** — agent-facing mirror so any agent loads the rules before UI work.
- **"Winners" recorded:** `.stitch-button*` = canonical Button (**not renamed**; only Stitch *wording* is scrubbed later in UX2); `.admin-table-scroll`>`.admin-data-table` = canonical Table; `components/ui/*` (`.ui-control`/`.ui-field`) = canonical form controls; `--surface-*` = canonical tokens (the unused `--color-*`/`--border-radius-*` aliases are slated for deletion in UX2).
- **Linked** from `README.md` (Start Here #8–9, Current Status, Engineer reader path) and `STATUS.md`.

## DoD check

- `web/DESIGN.md` exists and names exactly one canonical choice per component/token category ✓
- Skill mirror exists and is referenced by the execution prompts (`CLAUDE.md §3a`, `AGENTS.md §2a`) ✓
- No code/render changes; `tsc --noEmit` unaffected ✓ (see Re-run checks)
- `docs/02_…Milestones.md` untouched ✓

## Re-run checks

- `tsc --noEmit` — clean (no source changes).
- `make reader-clarity-check` — doc-hygiene suite passes with the new links.

## Honest limits

- UX0 is decisions + documentation only; it does not change any pixels. The drift it prevents is only prevented once UX1–UX2 (de-dep, de-Stitch-wording, CSS sectioning) and the per-surface fixes (UX3+) are executed against it.
- The palette decision is "keep + constrain," not a re-skin; contrast risk on tan surfaces is deferred to UX8 (acknowledged, not yet fixed).

**Next:** UX1 — remove all Google/external UI dependencies (self-host Inter, inline-SVG icons, local avatars) so the UI renders fully network-blocked.
