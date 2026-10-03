# 19 · Open Questions & Owner Inputs

## Needed from Khurram

| # | Item | Needed by | Notes |
|---|---|---|---|
| N1 | **Name** | Day 1 | ✅ **CamMind** (repo `CamMind`). Check the name and domains before a public launch. Code uses `cammind` internally |
| N2 | **GitHub repo** | Day 1 | ✅ `github.com/khurram-Shahid09/CamMind`. Public from day 1 (build in public). Commits use the verified email so they count as contributions. CI won't run until the **GitHub billing lock is fixed** (same as WatchOnce and InvoiceFlow) |
| N3 | **Docker Desktop running** with ≥ 4 GB memory for containers | Day 1 | Stop WatchOnce and InvoiceFlow containers while working on this |
| N4 | **FFmpeg CLI installed** | Day 1 | `winget install Gyan.FFmpeg` |
| N5 | **A real camera** (any one) | Day 3 | An RTSP IP camera on the same network (Tapo, Hikvision, Dahua, EZVIZ, Reolink, CP Plus…) with its RTSP URL, **or** an Android phone with an RTSP camera app. Test streams cover everything else |
| N6 | **Test footage** | Day 12 | Self-recorded clips with permission from everyone in them: your doorstep at night, a gate, someone with and without a helmet (a bike helmet is fine), boxes in front of a door. Plus Pexels/Pixabay clips. About 25 clips total |
| N7 | **Telegram** | Day 9 | A Telegram account to create a bot with @BotFather (free, 2 minutes) |
| N8 | **AI budget decision** | Day 11 | Gemini free tier is enough to build (fake/recorded provider for most tests). For evals and the demo, about **$5** of paid Gemini or Claude credit. Real customer cameras must not use the free tier ([14](14-security-privacy.md#privacy-by-design)) |
| N9 | **GPU?** | Day 3 | Does the laptop have a dedicated GPU? If yes, DirectML can raise capacity a lot. Not required |
| N10 | **VPS** (optional) | Day 15 | Only for the hosted read-only demo core (about $6/mo), or use Fly.io's free allowance |

## Decisions

| # | Question | Decision / default | Alternatives |
|---|---|---|---|
| D1 | Project | ✅ **Plain-English rules for RTSP cameras** | AI workflow builder, support triage |
| D2 | Stack | **Same as WatchOnce/InvoiceFlow** + a separate vision worker ([ADR-0004](adr/0004-reuse-portfolio-stack.md)) | FastAPI |
| D3 | AI role | **Compile rules; answer yes/no questions. Never decide** ([ADR-0001](adr/0001-detectors-and-rules-decide.md)) | – |
| D4 | Detector | **Apache-2.0 model via ONNX Runtime**; final pick after the day-3 benchmark ([ADR-0006](adr/0006-permissive-detector-onnx.md)) | Ultralytics YOLO as an optional plug-in (AGPL) |
| D5 | Default model | **Gemini Flash**; Claude Sonnet for comparison and "high accuracy" rules | – |
| D6 | Face recognition | **No** ([ADR-0005](adr/0005-no-face-recognition.md)) | – |
| D7 | First notification channel | **Telegram** (free, rich media, easy) | WhatsApp (needs a Meta business account and templates: v0.2) |
| D8 | Public demo | **Read-only demo mode on recorded streams** ([17](17-deployment-ops.md#3--hosted-read-only-demo-portfolio)) | – |
| D9 | Licence | **Open question:** MIT (max reach for the portfolio) or AGPL / source-available (protects a future paid product) | Decide before the first public commit |
| D10 | Timeline | 15 working days, demo-able at day 10 | 8-day cut ([15](15-roadmap-build-plan.md#faster-cut-8-days)) |

## Open product questions (decide during the build)

| # | Question | Current thinking |
|---|---|---|
| Q1 | Sum counts across cameras that overlap? | No in the MVP; say so in the assumptions. v0.2 could use per-site "count zones" with de-duplication |
| Q2 | Should operators be able to create rules? | Yes, for their sites; admins can lock rules |
| Q3 | Pricing tiers for a future product | Home free (≤ 2 cameras, own AI key); school / business per camera per month; enterprise self-hosted licence |
| Q4 | Urdu UI | English first; rules already accept Roman Urdu input |
| Q5 | Night-time accuracy targets | Report separately; may need lower confidence thresholds or IR-specific question wording |
