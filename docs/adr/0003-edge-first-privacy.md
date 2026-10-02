# ADR-0003: Edge-first processing; cloud AI is opt-in and sees crops only

**Status:** Accepted · 2026-10-30

## Context
Camera footage of homes, schoolchildren and workers is highly sensitive. Streaming it to a cloud service creates legal risk (GDPR, school policies, employee monitoring rules), costs bandwidth and adds latency. Schools and enterprises often forbid it outright.

## Decision
- Decoding, motion detection, object detection, tracking, the rule engine and clip recording run on a machine on the cameras' network.
- The only data that can leave the site by default: event metadata and snapshots to the core (which also runs on site in the standard deployment), and outbound notifications chosen by the user.
- Cloud vision AI is **off by default per camera** (`cloud_ai_allowed`). When on, only crops, zone crops or small frame strips selected by a `verify` rule are sent, and every one is recorded in the event's verification history.
- The provider interface has a `local` slot so verification can run on site later with an open vision-language model.

## Consequences
- ✅ A strong, true privacy story for every tier; easier approval in schools and companies.
- ✅ Low bandwidth: a few KB per verification instead of Mbps per camera.
- ✅ Keeps working (minus verification) when the internet is down.
- ❌ Users need a machine on site. Acceptable: most people with cameras already have an NVR or a PC; an N100 mini PC costs about $150.
- ❌ Hosted multi-site needs edge workers that report out ([17](../17-deployment-ops.md#multi-site-v03-designed-now)). The HTTP worker boundary is built in from day 1 for this.
