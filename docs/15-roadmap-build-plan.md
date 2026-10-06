# 15 · Roadmap & Build Plan

## Status (6 Oct 2026)

Days 1–2 done. Next: day 3, the vision worker's intake, motion gate and detector benchmark.

| Built | Where |
|---|---|
| Local stack: Postgres, Redis, SeaweedFS, Mailpit, go2rtc; five looping MediaMTX test cameras | `infra/` |
| Django skeleton: settings per environment, health checks, error envelope, Celery queues | `services/core/config`, `common` |
| Orgs, sites, 4 roles with per-site access, JWT + API tokens, append-only audit log | `accounts`, `audit` |
| Cameras: encrypted URLs, RTSP check with clear error codes, go2rtc sync, snapshots in S3, admin with preview | `cameras` |
| Shared LLM wrapper (Gemini + fake), storage, field encryption | `common` |
| Skeletons: vision worker CLI, rule spec package, Next.js dashboard, CI workflow | `services/vision`, `packages/cammind-spec`, `apps/web`, `.github` |

Changes from the plan: the three Python projects are separate `uv` projects (the core and the vision worker get their own lock files and, later, their own images) and the shared spec package is a path dependency. Test clips aren't downloaded yet: cameras without a clip show a moving test pattern, which is enough until detection (day 3).

## Phases

| Phase | Goal | Duration (est.) | Exit criteria |
|---|---|---|---|
| **MVP (v0.1)** | Camera → plain-English rule → detection → verification → alert with clip, with evals | **15 working days** (~3 weeks) | Demo video, evals at target, portfolio case study |
| **v0.2** | Daily use | 2–3 weeks | Sequences ("package left, then taken"), unattended objects, privacy masks + face blur in clips, WhatsApp (Cloud API), Slack buttons, local vision model, ONVIF discovery |
| **v0.3** | Multi-site and search | 3–4 weeks | Edge nodes reporting to a hosted control plane, search over events ("red car yesterday" with image embeddings + pgvector), daily reports and heatmaps, Home Assistant / MQTT integration, mobile push (PWA) |
| **Pilot** | 1–3 real users | 4–6 weeks | One home, one school or office, one workshop or warehouse; measured false alarms per day, missed events, cost per camera-day |

## Daily rhythm while building

Same as the earlier projects: earning comes first. Each day:
- **2–3 h selling:** proposals, messages, follow-ups.
- **5–6 h building:** this plan.
- Every few days, a short clip of progress on LinkedIn (live boxes over a camera feed look great in a feed).

## MVP day-by-day

A **demo-able cut lands at day 10**. Days 11–15 harden it, run evals and launch.

### Week 1: video in, detections out

| Day | Build | Done when |
|---|---|---|
| 1 | Repo, `uv` projects (`services/core`, `services/vision`, `packages/cammind-spec`), Next.js app, `infra/docker-compose.yml` (Postgres, Redis, SeaweedFS, Mailpit, go2rtc, MediaMTX test streams), CI skeleton. Download 5 test clips; write `SOURCES.md` | `docker compose up` shows 5 looping test cameras in go2rtc's web UI |
| 2 | Core: orgs, sites, cameras (encrypted URLs), camera test endpoint, go2rtc config sync, snapshots. Copy the auth, org scoping, audit and LLM wrapper modules from InvoiceFlow | Add a camera by URL in the admin and see its snapshot |
| 3 | Vision: intake (PyAV, reconnect, sampling, health), motion gate, detector benchmark (RT-DETRv2-S vs D-FINE-S on CPU; pick one), ONNX session | Worker logs detections for 4 test streams at 5 fps on the laptop CPU; numbers written into [04](04-tech-stack.md#hardware-targets) |
| 4 | Tracking (ByteTrack), geometry (zones, lines), annotated debug view (MJPEG on the worker's metrics port) | Debug view shows stable track IDs and zone hits |
| 5 | `cammind-spec` Pydantic models + validation; rule engine for presence, count, dwell, absence, crossing with schedule, hold and cooldown; unit tests with synthetic tracks and a fake clock | ~60 engine tests green; hand-written spec fires on the "front door at night" clip |

### Week 2: rules, events, alerts

| Day | Build | Done when |
|---|---|---|
| 6 | Worker ↔ core: config load + Redis hot reload, SQLite outbox, `/internal/events`, event state machine, snapshots to S3 | Events appear in the admin with snapshots; killing the core and restarting loses nothing |
| 7 | Segment recorder, clip cutting (`media` queue), retention task | Each event gets a 15 s MP4 that starts 5 s before the trigger |
| 8 | Rule compiler: context builder, prompt v1, structured output, validation + repair, questions, refusals; first 30 compiler eval sentences | `POST /rules/compile` returns correct specs for the 5 docs examples |
| 9 | Actions: in-app SSE, Telegram (link flow, photo then clip reply), email, webhook with signatures, retries, rate limit, grouping | A test-stream event reaches a phone on Telegram in < 3 s, then the clip |
| 10 | Dashboard: onboarding, Live grid (WebRTC), camera detail, zone editor, New rule flow with summary card, Events timeline + detail | **Demo-able:** add camera → draw zone → type rule → activate → alert on phone |

### Week 3: verification, evals, launch

| Day | Build | Done when |
|---|---|---|
| 11 | Verification: verify requests, crops and strips, provider calls, cache, decision, budgets and usage ledger; `scene` condition; fall/fight triggers | Helmet, fall and blocked-exit rules work on their clips |
| 12 | Evals: labelled clip set (≥ 25 clips, ~150 labelled events), clip runner with a fake clock, compiler set to 80 sentences, verify crop set, injection scenes; reports in `evals/reports/` | `uv run cammind-evals all` prints the metrics table |
| 13 | Tuning from evals (thresholds, questions, triggers); feedback + suggestions; rule test on buffer; usage page | Metrics at MVP target ([01](01-product-vision.md#success-metrics)) |
| 14 | Hardening: permissions tests, cross-tenant tests, SSRF guards, health alerts, error states; Playwright happy path; README results table | CI green; security checklist in [14](14-security-privacy.md) ticked |
| 15 | Demo: record scenes ([18](18-demo-script.md)), voice-over, captions, cover image; case study page on the portfolio; LinkedIn post | Video published, README links live |

## Faster cut (8 days)

If time is short: skip Slack, email and webhooks (Telegram only), skip `scene` and `frame_strip` (helmet only for verification), skip rule test runs and the usage page, 10 eval clips. Keep the compiler, the engine, clips and evals. Those are the story.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| CPU too slow for 4 cameras | Demo lag | Lower detect fps; smaller model (S/N variant); run the demo with 2–3 cameras; DirectML on the laptop GPU if present |
| Detector misses small or far people | Low recall | `min_box_px`, 960 px input for far cameras (per-camera setting), pick test clips at sensible distances, report honestly |
| Vision model wrong on helmets in low light | False alarms | `unsure` handling, rechecks, Claude comparison; daytime clips for the demo, a night clip shown honestly in evals |
| go2rtc / WebRTC issues on Windows | No live view | MSE fallback; snapshot refresh fallback |
| Free-tier AI quota limits during evals | Slow evals | Fake provider for most tests; ~$5 paid credit for final eval runs (see [19](19-open-questions.md)) |
| Finding good test footage with clear licences | Weak demo | Self-record with a phone (doorstep, a friend's shop with permission, a workshop); Pexels/Pixabay clips |
