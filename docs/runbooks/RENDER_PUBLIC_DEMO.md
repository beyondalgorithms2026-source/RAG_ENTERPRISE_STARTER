# Render public-demo deployment

This runbook deploys the FastAPI data layer against the synthetic Northwind corpus.
It is a portfolio demo posture, not a production or client deployment.

## What the blueprint fixes in source

- Render Free web service in Singapore, one instance and one worker
- automatic deployment only after GitHub checks pass
- anonymous research access with SQL-level document ACLs
- uploads, admin-expensive operations, connectors, and enrichment disabled
- three answer requests and ten search requests per IP per minute
- OpenAI `text-embedding-3-small` at 384 dimensions
- versioned `gpt-4o-mini-2024-07-18`, capped at 600 output tokens per call
- a USD 0.01 per-request cost alert

The OpenAI project-level USD 1 monthly hard limit is the final spend boundary. The
application rate limit and output-token bound reduce how quickly it can be reached;
the existing client test also proves that a simulated provider limit response fails
closed without returning generated content.

## The only three private values

Render prompts for these because `render.yaml` marks them `sync: false`. Paste them
into Render's form, not into GitHub, this repository, a chat, or a committed `.env`:

1. `DATABASE_URL` — the Supabase **Session Pooler** URI saved during D8.
2. `EMBEDDING_API_KEY` — the private OpenAI key authorized for embeddings.
3. `LLM_API_KEY` — the private OpenAI generation key authorized for the GPT-4o Mini snapshot.

The two OpenAI variables may contain the same project key only if that key is authorized
for both models. They remain two variables so the permissions can be separated later.
The default LLM profile keeps its database `api_key` field blank and resolves the Render
environment value only in process memory; startup does not copy this key into Supabase.

## Owner steps in Render

1. Open the Render dashboard and choose **New → Blueprint**.
2. Select `beyondalgorithms2026-source/RAG_ENTERPRISE_STARTER` and branch `main`.
3. Keep the Blueprint path as `render.yaml`.
4. At the environment-variable prompt, paste each of the three values above into its
   matching field. Render masks them after saving.
5. Confirm the proposed service says **Free**, **Singapore**, and one instance. Do not
   add a Render database; this deployment uses the existing Supabase project.
6. Apply the Blueprint and wait for the deploy to finish.
7. Copy only the public `https://...onrender.com` service URL and share that URL with the
   implementation thread. Do not copy logs or any environment-variable screen.

The initial boot runs the repository's idempotent migrations and coherence checks. It
does not seed or upload documents; D8 already loaded the synthetic corpus. Render Free
spins down after inactivity, so the first request after an idle period can take about a
minute. Its local filesystem is ephemeral; the persistent corpus remains in Supabase.

## Verification gate

After the owner supplies the public URL, verify all of the following before changing any
public deployment claim:

- `/health` returns successfully after a cold start
- anonymous hybrid search returns only an allowed synthetic source
- an answerable preset returns a cited result
- an unsupported question refuses safely
- `/upload` is rejected
- the fourth rapid `/ask` request from one address receives HTTP 429
- a simulated OpenAI hard-limit response remains covered by the offline test

Record measured status codes, latency, and test output in the B004 build log. Do not
publish the URL or replace the README's “Not deployed anywhere” statement until the
owner reviews and approves those measurements.
