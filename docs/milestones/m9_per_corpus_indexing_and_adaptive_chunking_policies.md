## M9 — Per-Corpus Indexing And Adaptive Chunking Policies

- Added an explicit corpus-policy registry for `legal`, `transcripts`, `db_rows`, `email_casework`, and the default baseline.
- Source-scoped retrieval now respects corpus policy defaults, so legal corpora can route lexical-first while transcript corpora can route semantic-first without changing global retrieval settings.
- Chunking now uses policy-driven target sizes and overlaps, and transcript-oriented policies emit speaker/time metadata directly into chunk locators.
- Added generic structured metadata filters for row-shaped corpora and a corpus-policy eval matrix fixture covering legal, transcript, and structured-row behaviors.
