# 02 · PRD: MVP (v0.1)

## Goal

A working system that connects to real RTSP cameras, turns plain-English rules into confirmed, typed rules, detects matching events in real time on a normal PC, verifies hard cases with a vision model, and sends alerts with a snapshot and clip. It's proven by an eval suite and a 2-minute demo.

## Scope

### In scope
- **Cameras:** add by RTSP URL (main + optional sub stream), test the connection, snapshot, live preview in the browser (WebRTC via go2rtc), health status (online, offline, fps).
- **Test streams:** loop MP4 files as RTSP streams so everything works without hardware; a phone camera app (for example *IP Webcam* on Android) as a real camera.
- **Sites:** organisation → sites → cameras. Each site has a time zone and a "school / business hours" calendar.
- **Zones:** draw polygons (areas) and lines (with a direction) on a snapshot; name them ("Back door", "Gate line").
- **Rules:** type a sentence → compiled rule shown as a plain-English summary + editable fields + JSON → confirm → active. Pause, edit, delete, version history.
- **Rule types:** presence, count, dwell, absence, line crossing, verified state ("no helmet", "fall", "fight", "blocked exit", "smoke"), schedules, cooldowns.
- **Video pipeline:** decode at a sampled rate, motion gate, object detection (people, vehicles, animals, common objects), tracking, rolling clip buffer.
- **Verification:** vision LLM yes/no checks on crops or short frame strips, cached per track, with per-camera budgets.
- **Actions:** email, Telegram, Slack, signed webhook, in-app (live toast). Snapshot + 10–15 s clip (pre- and post-event).
- **Events:** timeline per site and camera, filters, event detail with clip player and evidence, "Confirm / False alarm" feedback, comments.
- **Organisations, users, roles** (Owner, Admin, Operator, Viewer); per-site access; append-only audit log.
- **Usage:** AI calls, tokens and cost per camera, rule and day; budget caps.
- **Evals:** compiler prompt set, labelled clips, verification crop set, injection scenes; results in CI.

### Out of scope (later)
- Sequences across rules or cameras ("package present, then gone"), tailgating, unattended objects.
- Natural-language search over past footage ("every red car yesterday").
- WhatsApp, SMS, phone calls, mobile app with push.
- ONVIF discovery, PTZ control, two-way audio.
- Multiple edge nodes reporting to one hosted control plane (designed for, see [17](17-deployment-ops.md)).
- Local vision LLM (designed for: the provider interface has a slot for it).
- Face blurring in stored clips (v0.2), heatmaps and analytics reports.

## User stories and acceptance criteria

### Cameras
**US-1. As an admin, I add a camera by pasting its RTSP URL and see a live preview within 10 seconds.**
- The URL is tested before saving: CamMind reports *reachable*, *wrong credentials*, *wrong path* or *unsupported codec* in plain words.
- Credentials are stored encrypted and never returned by the API (URLs are shown masked: `rtsp://admin:•••@192.168.1.20/...`).
- If the camera has a sub stream, CamMind uses it for detection and the main stream for clips.

**US-2. As an admin, I can see whether every camera is healthy.**
- Each camera shows: online / offline / reconnecting, decode fps, detection fps, last frame time.
- A camera offline for more than 2 minutes creates a system event and (optionally) an alert.
- The worker reconnects with backoff (1 s → 60 s) without restarting.

### Zones
**US-3. As an admin, I draw zones and lines on the camera image and name them.**
- Polygons with 3–20 points; lines with a direction arrow ("in" side).
- Coordinates are stored normalised (0–1), so they survive resolution changes.
- Zones can be reused by many rules; deleting a zone in use is blocked with a list of rules that use it.

### Rules
**US-4. As a user, I type a rule in plain English and see exactly what CamMind understood before it runs.**
- The compiled rule appears as a sentence ("**Person** in **Back door** for at least **5 s**, every day **22:00–06:00**, then **Telegram to Owner + 15 s clip**"), with each part editable.
- Assumptions are listed ("'Night' was read as 22:00–06:00").
- If the sentence is ambiguous or needs something that doesn't exist (a zone called "back door" on two cameras, or no such zone), CamMind asks one clear question or offers to create the zone.
- If part of the request isn't supported ("recognise my brother"), CamMind says which part and why, and never silently drops it.
- The rule doesn't run until the user clicks **Activate**.

**US-5. As a user, I can test a rule before activating it.**
- "Test on clip" runs the rule over an uploaded clip or the last 5 minutes of the buffer and shows which moments would have fired.

**US-6. As a user, I can edit a rule; old events stay linked to the rule version that created them.**

### Detection and events
**US-7. As a home owner, when someone stands at my door at 23:14, I get a Telegram message within 3 seconds with a snapshot, then a clip.**
- The snapshot has the detection box and zone drawn on it.
- The clip covers about 5 s before and 10 s after the trigger.
- One incident → one alert. The same person staying there doesn't trigger again until the cooldown ends (default 2 minutes).

**US-8. As a safety officer, a "no helmet" rule only alerts when the vision model confirms there's no helmet.**
- Each tracked person in the zone is checked at most once per 30 s, not every frame.
- If the model answers "unsure" (occlusion, blur), CamMind checks one more frame later; it never alerts on "unsure" alone.
- If the camera's AI budget runs out, the rule falls back to "person in zone, not verified" and marks events *unverified*. It doesn't stop silently.

**US-9. As an operator, I see every event in a timeline and mark it Confirmed or False alarm.**
- Feedback is stored with the event and shown per rule as a precision figure.
- After 3 false alarms on the same rule in a day, CamMind suggests a fix ("Raise minimum time from 2 s to 5 s?", "Shrink zone?").

### Actions
**US-10. As an admin, I connect Telegram, Slack, email or a webhook once and choose channels per rule.**
- Telegram: link by sending a code to the CamMind bot.
- Webhooks are signed (HMAC-SHA256) and retried with backoff; delivery history is visible.
- Failed deliveries never block other actions or other events.

### Tenancy and audit
**US-11. As a school admin, I give a guard Operator access to the main campus only.**
- Users see only sites they're members of; API queries are scoped by org and site.
- Every change to cameras, zones, rules, channels and members is in the audit log (who, what, when, before → after).

### Usage
**US-12. As an owner, I can see what the AI costs and cap it.**
- Usage per camera, rule and day: calls, tokens, cost.
- Monthly and daily caps per org and per camera; at 80% CamMind warns; at 100% verification pauses (see US-8).

## Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | 4 cameras on a 4-core CPU without a GPU (720p sub stream, detection at 5 fps); GPU optional |
| Latency | See [01 · metrics](01-product-vision.md#success-metrics) |
| Reliability | Worker survives camera drops, network blips and LLM timeouts; no event lost if the API is briefly down (local outbox) |
| Privacy | No video leaves the machine unless a rule uses cloud verification; then only crops/frame strips |
| Retention | Clips and snapshots auto-deleted after a per-site period (default 14 days); events kept 90 days |
| Accessibility | Dashboard usable by keyboard; alerts don't rely on colour alone |
| Localisation | English UI; times shown in the site's time zone; rules understand Urdu/Roman Urdu input as a stretch goal (LLM handles it, evals include a few) |

## Release criteria

- All ✅ use cases in [01](01-product-vision.md#use-cases) work on the eval clips.
- Metrics at MVP target in [16 · Testing & evals](16-testing-and-evals.md).
- Demo video recorded ([18](18-demo-script.md)); README results table filled in.
