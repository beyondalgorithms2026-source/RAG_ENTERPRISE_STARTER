# Northline Analytics corpus (Western, synthetic)

Every document in this directory is **synthetic**. It describes a fictional UK-registered
company, "Northline Analytics Ltd", with offices in Manchester, Austin and Amsterdam.
No real company, person, customer, contract or policy is represented, nothing here is
confidential, and none of it is legal or HR advice. The documents were produced outside
this repository for the public demo and are committed deliberately, as the Northwind
corpus is, so that every answer and evaluation question can be checked against its source.

This corpus contains no Indian tax, payroll or GST material. The seeder rejects any
document or manifest row that matches that guard.

## Files

- `NL-*.md`: policy, SOP, playbook, appendix and changelog documents.
- `NL-TEST-POISON-DOC.md`: a **test fixture**, not policy. It contains one deliberately
  unsafe planted sentence and is used to test indirect prompt injection.
- The manifest and the evaluation set live in `eval/western/`. `CORPUS_NOTES.md` there is
  a consistency reference and is not ingested.

## Access classification

The manifest's `Internal` documents are published to anonymous demo visitors.
`NL-OPS-SOP-INCIDENT` (Confidential) is restricted to the `operations` group, so the
demo can show an access-controlled refusal. `NL-SEC-DATA-RETENTION-2026` (Confidential in
the manifest) is published by owner decision so that it can be used in the demo.

## Ingesting

    cd backend
    python -m app.seed.western_corpus --dry-run     # validate, chunk, estimate cost
    python -m app.seed.western_corpus --apply
    python -m app.seed.western_corpus --wipe --confirm western_northline

On the hosted demo, `WESTERN_CORPUS_AUTOSEED=true` runs the same `--apply` path at startup.
Re-runs are content-hash idempotent. Sources are tagged `corpus=western_northline`, and a
request can be limited to them with `filters.corpus`.
