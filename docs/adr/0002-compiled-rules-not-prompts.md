# ADR-0002: Plain English compiles to a typed rule that the user confirms

**Status:** Accepted · 2026-10-30

## Context
The product's promise is "write rules in plain English". The simplest build would store the sentence and give it to a model at run time ("Here's a frame. Does this match: *alert me if…*?"). That means the meaning of a rule can drift between calls, nobody can see exactly what will run, and every frame needs a model call.

## Decision
- An LLM compiles the sentence once into a `RuleSpec` (Pydantic, JSON Schema enforced), using only the site's real camera, zone, channel and calendar IDs.
- The spec is validated in code; invalid output gets one repair attempt, then falls back to the form editor.
- The user sees a deterministic, template-generated summary plus the model's listed assumptions, can edit any field, and must click **Activate**.
- Run time uses only the spec. The source sentence is stored for history and evals, never executed.

## Consequences
- ✅ What runs is exactly what the user saw and approved.
- ✅ Rules are versioned, diffable and testable on recorded clips.
- ✅ Compiling costs one or two LLM calls per rule edit, not per frame.
- ✅ The compiler is measurable with a fixed eval set.
- ❌ The rule language limits what can be expressed. Mitigated by the `scene` + `verify` escape hatch for objects and states the detector doesn't know, and by clear `unsupported` answers.
