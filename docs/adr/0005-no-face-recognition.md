# ADR-0005: No face recognition or person identification

**Status:** Accepted · 2026-10-30

## Context
"Tell me when my son gets home" or "alert if a stranger (not staff) enters" are natural requests. Supporting them needs face recognition or person re-identification. That is:
- **biometric processing**, regulated by GDPR (special category data), Illinois BIPA and similar laws, and restricted by the EU AI Act
- especially sensitive for **children** in schools and for **employees** at work
- error-prone in CCTV conditions (angles, low light, low resolution), with documented unequal error rates across groups.

## Decision
- No face recognition, face matching, person re-identification across cameras, or person profiles.
- Track IDs are local to one camera and one worker run, and are never presented as identities.
- The compiler refuses identity and protected-attribute rules and offers a behaviour-based alternative ([06](../06-rule-compiler.md#refusals)).
- Verification questions can't ask about identity, age, gender, ethnicity, religion or health beyond the visible event.
- Face *detection* may be added only for **blurring** faces in stored clips (v0.2), never for recognition.

## Consequences
- ✅ Much lower legal and ethical risk for schools and workplaces; simpler approvals.
- ✅ A clear, honest product line that's easy to explain.
- ❌ "Known vs unknown person" use cases aren't supported. Workarounds: schedules (anyone after hours), zones (anyone in the staff-only area), and webhooks to an access-control system that already knows who badged in.
