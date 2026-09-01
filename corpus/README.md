# Public demo corpus

Every document in this directory is **synthetic**. It describes a fictional company,
"Northwind Logistics", and was written for this repository. No real company, person,
policy, or document is represented, and nothing here is confidential.

This exists because the system is useless to a stranger without documents to ask
questions about, and the corpus it was developed against cannot be published: it
contains third-party copyrighted material.

## Why the documents look the way they do

The demo is built around internal HR and company-policy documents for one reason: it is
the clearest setting in which to show what this system is actually for. The interesting
question in enterprise RAG is not "can it find the answer" but "should this person see
this answer, and can you prove where it came from". Policy documents have natural
access boundaries — everyone may read the travel policy, only HR may read the
compensation bands — so the ACL layer is demonstrable rather than theoretical.

Documents carry a classification that drives the seeded ACL:

| Classification | Who can retrieve it | Demonstrates |
|---|---|---|
| `public` | everyone | ordinary grounded answers with citations |
| `internal` | authenticated employees | authentication actually gating retrieval |
| `restricted` | named groups only | SQL-level ACL trimming, not UI filtering |

The `restricted` documents are what make red-team scenario RT-06 meaningful: the agent
layer cannot reach them, because ACL enforcement lives in the backend's retrieval SQL.

## Generating

    python corpus/generate_corpus.py --out ~/.rag-enterprise/uploads

Documents are deterministic: the same seed produces the same corpus, so eval numbers
are reproducible.

## Ingesting

The corpus is loaded as a seed pack, reusing the mechanism in `app/seed/` so that
sources, ACL grants and chunks are created through the same code path the application
uses. See the quickstart for the command.

## What this corpus is not

It is not a benchmark. The documents were written to exercise the system's governance
behaviour, not to measure retrieval quality against a published standard. Evaluation
numbers produced against it say something about this system's behaviour on this corpus
and nothing about how it would perform on yours.
