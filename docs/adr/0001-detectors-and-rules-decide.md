# ADR-0001: Detectors and rules decide; the AI answers questions

**Status:** Accepted · 2026-10-30

## Context
Alerts wake people up, call guards and may trigger a gate or a siren through webhooks. A vision-language model that watches the scene and "decides" when to alert would be:
- **unpredictable:** the same scene can get different answers, and it's hard to explain why it fired
- **exploitable:** text in the scene (a sign, a phone screen, a printed note) can steer it
- **expensive and slow** if it sees every frame.

## Decision
- Whether an event exists is decided by deterministic stages: motion → object detector → tracker → rule engine with explicit thresholds, zones, schedules, hold and cooldown.
- The vision model is called only when a rule has a `verify` step, on a crop or a small frame strip the engine selected, with one fixed yes/no question. Its output is `{answer: yes|no|unsure, confidence, reason, visibility}`.
- Mapping the answer to confirmed / dismissed / unverified is a deterministic function of the rule's `expect`, `min_confidence` and `on_unsure`.
- The model has no tools and doesn't choose actions, recipients or rules.

## Consequences
- ✅ Every alert is explainable: "person in Back door for 3.1 s" or "AI answered *no* to 'wearing a helmet?' at 0.91".
- ✅ Injection can at most flip a single yes/no for a single image, and rechecks plus evals limit that ([09](../09-ai-verification.md#why-its-injection-safe)).
- ✅ Most rules (presence, count, dwell, crossing, absence) cost nothing in AI.
- ❌ Open-ended requests ("anything unusual") can't be expressed. Acceptable: they're also the requests most likely to produce noise. A future "anomaly" rule type would still go through the same structure.
