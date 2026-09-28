# ADR-0004: Reuse the WatchOnce / InvoiceFlow stack; add a separate vision worker

**Status:** Accepted · 2026-10-30

## Context
WatchOnce and InvoiceFlow already have working, tested patterns:
- Django + DRF with org scoping and an append-only audit log
- Celery queues and beat
- Redis pub/sub to SSE
- a Next.js dashboard with BFF routes
- a pluggable LLM provider (Gemini, Claude, fake) with cost tracking, retries and key rotation
- evals with committed reports, and a demo video pipeline.

What's new is a long-running video loop, which doesn't fit Celery.

## Decision
- Use the same stack for the core and dashboard, and copy (not share) the relevant modules: auth and org scoping, audit, LLM provider wrapper, SSE, video pipeline.
- Build the video path as a separate Python service (`services/vision`) that talks to the core over HTTP with worker tokens, plus Redis pub/sub for config changes.
- Put the rule spec models in a small shared package (`packages/cammind-spec`) used by both services.

## Consequences
- ✅ Faster start; a consistent engineering story across three portfolio projects.
- ✅ Interview talking point: the same control-plane pattern applied to a third domain, plus a real-time data plane.
- ✅ The HTTP boundary makes edge deployment and multi-site possible later.
- ❌ Some duplicated code across repos. Acceptable; extract a shared package only if it keeps growing.
