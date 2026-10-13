# 20 · Demo Sprint (this week) and Pending Work (next week)

**Goal this week:** a demo-ready CamMind for the portfolio: a 2-minute video, screenshots, a cover image and a README with real results. Built in small steps, one per working session, so each step fits the week's usage budget and leaves the repo green.

This is the [faster cut](15-roadmap-build-plan.md#faster-cut-8-days), shaped around the [demo script](18-demo-script.md). Anything the video doesn't need moves to [Pending](#pending-next-week).

## Steps

Each step ends with tests passing, commits pushed, and this table updated.

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | **Vision intake:** PyAV reader with reconnects, motion gate, ONNX detector (auto-download, CPU/DirectML), ByteTrack, zone and line geometry; `cammind-vision detect` prints tracks for a stream | Tracks stable on a test stream; detector speed measured on this laptop | ✅ D-FINE-S picked: 150 ms/frame on CPU (D-FINE-N 68 ms, RT-DETRv2-S 240–380 ms and more false positives) |
| 2 | **Rule spec + engine:** Pydantic models in `cammind-spec`; engine for presence, count, dwell, absence, crossing with schedule, hold and cooldown; unit tests with synthetic tracks | ~50 engine tests green | ✅ spec models + engine for all five conditions, schedules, hold, cooldown, long-event split |
| 3 | **Worker ↔ core:** zones model and API, `/internal/config`, `/internal/events` with idempotency, worker outbox, event model and states, snapshots with boxes | A person walking into a zone on a clip creates one event with a snapshot | ✅ zones, rules with versions, internal API, worker loop with SQLite outbox; real events with snapshot + crop |
| 4 | **Alerts and clips:** segment recorder, clip cutting, Telegram (photo, then clip) and in-app SSE | Event → Telegram photo in < 3 s, clip follows | ✅ Slack instead of Telegram (webhook); clips moved to pending |
| 5 | **Rule compiler:** prompt, structured output, validation + one repair, questions and refusals; `POST /rules/compile`, rules API with versions | The 5 rules in the demo script compile correctly (Gemini and the offline fake) | ✅ night window, gate crossing, helmet check and a refusal all compile on Gemini |
| 6 | **Verification (helmet only):** crops, yes/no check, recheck, budgets, "unverified" fallback, injection-safe decision | Helmet clip: no-helmet person confirmed, helmeted person dismissed, paper-sign scene unchanged | ✅ on the workshop clip Gemini sees the hard hats (0.95–0.98), so no false alarms; a no-helmet clip and the paper-sign scene are pending |
| 7 | **Dashboard:** login, live grid, camera page with zone editor, new-rule flow with the summary card, events timeline and event detail | Full flow in the browser: camera → zone → rule → event | ✅ login, live grid, rules with the "what CamMind understood" card, events and event detail with the AI check (zones are seeded; the zone editor is pending) |
| 8 | **Demo:** real clips in place, scripted demo data, Playwright capture, voice-over, captions, cover image, screenshots, README results table, short eval run | `demo/out/cammind-demo.mp4` and images ready for the portfolio | ✅ 85 s video with voice-over, cover, 8 screenshots, README results |

**Order of cuts if the budget runs short:** step 6 shrinks to a recorded (fake-provider) answer set; step 7 drops the zone editor (zones seeded instead); step 4 drops clips (snapshot only). Steps 1–3, 5 and 8 are the story and stay.

## What's needed from Khurram

| # | Item | Needed by | Notes |
|---|---|---|---|
| 1 | **Weekly usage check** before each step | Every step | Run `/usage` and share the remaining percentage; each step is sized at roughly a tenth of a week |
| 2 | **Real clips** for the five test cameras | Step 3 (one clip), step 8 (all five) | Self-recorded with consent, or Pexels/Pixabay. See [SOURCES.md](../infra/test-streams/SOURCES.md). A phone video of someone walking to a door is enough for step 3 |
| 3 | **Telegram bot token** | Step 4 | 2 minutes with @BotFather; add `TELEGRAM_BOT_TOKEN` to `.env` |
| 4 | **Gemini API key** | Step 5 | Free tier is fine for test clips; add `GEMINI_API_KEYS` to `.env`. Without it, the offline fake answers |
| 5 | **Approval of the video** | Step 8 | Watch the draft; one round of changes |

## Portfolio kit (step 8 output)

| Asset | File | Use |
|---|---|---|
| Demo video (~2 min, captions, voice-over) | `demo/out/cammind-demo.mp4` | YouTube, README, portfolio page |
| Short clip (30 s, vertical) | `demo/out/cammind-short.mp4` | LinkedIn |
| Cover image | `demo/out/cover.png` | README hero, portfolio card |
| Screenshots: rule card, live view with boxes, event detail, Telegram alert, cost funnel | `demo/out/screens/*.png` | Case study page |
| README results table | `README.md` | Measured numbers: detector speed, event precision and recall on the clips, alert latency, AI calls per camera-hour |

## Pending (next week)

Built after the demo, in this order. Each item links to the doc that specifies it.

| Item | Spec |
|---|---|
| Email and WhatsApp alerts with a short clip | [10](10-actions-and-notifications.md) |
| Zone editor in the dashboard, WebRTC live view, LinkedIn short (30 s vertical) | [13](13-dashboard.md) |
| A no-helmet clip and the paper-sign injection scene for the helmet demo | [18](18-demo-script.md) |
| Event clips (segment recorder + clip cutting) and Telegram | [07](07-video-pipeline.md#6--clips-seg-recorder--media), [10](10-actions-and-notifications.md) |
| Full eval suite: ~80 compiler sentences, ≥ 25 labelled clips, verification crop sets, injection scenes, reports in CI | [16](16-testing-and-evals.md) |
| `scene` rules (package, blocked exit, spill) and `frame_strip` rules (fall, fight, climbing) with motion triggers | [05](05-rule-spec.md), [08](08-rule-engine-and-events.md#verify-triggers) |
| Email, Slack and signed webhooks; delivery retries, rate limits, grouping, quiet hours | [10](10-actions-and-notifications.md) |
| Feedback (Confirm / False alarm), precision per rule, tuning suggestions | [08](08-rule-engine-and-events.md#feedback-and-tuning) |
| Rule test runs on the buffer or an uploaded clip | [06](06-rule-compiler.md), [12](12-api-spec.md#rules) |
| Usage page with the frames → detections → AI funnel, budget caps and warnings | [09](09-ai-verification.md#budgets), [13](13-dashboard.md) |
| Site calendars (school and business hours, holidays) | [05](05-rule-spec.md#when) |
| Camera health history, offline alerts, worker heartbeats on the dashboard | [03](03-architecture.md#failure-handling) |
| Retention jobs (clips, snapshots, dismissed events) | [11](11-data-model.md#retention-celery-beat-hourly) |
| Onboarding flow, channels page, settings and audit viewer in the dashboard | [13](13-dashboard.md) |
| Production compose (Caddy, GPU override), hosted read-only demo mode | [17](17-deployment-ops.md) |
| Performance report: cameras per machine, CPU vs DirectML | [16](16-testing-and-evals.md#performance) |
| Licence decision (MIT or AGPL) before the public launch | [19](19-open-questions.md) |
