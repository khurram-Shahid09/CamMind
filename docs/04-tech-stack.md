# 04 · Tech Stack

Same core as WatchOnce and InvoiceFlow, so patterns and code can be reused ([ADR-0004](adr/0004-reuse-portfolio-stack.md)). The new part is the vision worker.

## Backend (`services/core`)

| Concern | Choice | Notes |
|---|---|---|
| Language / runtime | Python 3.13, managed with **uv** | |
| Web framework | **Django 6 + DRF** | Admin for back-office fixes; SSE via async views |
| Background jobs | **Celery 5**, Redis broker, queues `compile`, `verify`, `media`, `actions`; **celery beat** | `--pool=solo` on Windows for dev |
| Database | **PostgreSQL 16** | JSONB for compiled rule specs; partial indexes on open events |
| File storage | **S3 API**: SeaweedFS locally, Cloudflare R2 for the hosted demo | Snapshots and clips |
| LLM | Pluggable provider: **Gemini Flash** (default, cheap, vision), **Claude** (`claude-sonnet-5-5`) for comparison, **fake** for tests | Structured JSON output; one wrapper for compile and verify |
| Validation | **Pydantic v2** | Rule spec models generate the JSON Schema given to the LLM |
| Encryption | `cryptography` (Fernet) | Camera credentials, channel secrets |
| Telegram | Bot API over `httpx` | No SDK needed |
| Slack | Incoming webhooks (MVP); Bolt later for buttons | |
| Email | Django email → Mailpit (dev), Resend or SMTP (prod) | |
| Lint / types / tests | ruff, mypy, pytest + pytest-django, factory_boy, freezegun | |

## Vision worker (`services/vision`)

| Concern | Choice | Notes |
|---|---|---|
| RTSP restream + browser preview | **go2rtc** (MIT) | One camera connection fans out to the worker, the recorder and WebRTC. Cameras often allow only 2–4 connections |
| Decode | **PyAV** (FFmpeg bindings, wheels include FFmpeg) | Decode the sub stream; drop frames to hit the sample rate |
| Segment recording | **FFmpeg** CLI, `-c copy -f segment -segment_time 2` | No re-encode; near-zero CPU; rolling buffer on local disk |
| Arrays / images | NumPy, OpenCV (`opencv-python-headless`) | Motion, drawing, JPEG encode |
| Detector | **RT-DETRv2** or **D-FINE** (Apache-2.0), exported to **ONNX** | COCO classes; 640 px input; see [ADR-0006](adr/0006-permissive-detector-onnx.md) |
| Inference | **ONNX Runtime**: CPU by default; **DirectML** on Windows GPUs; CUDA on NVIDIA | Same model file everywhere |
| Tracking, zones, lines | **`supervision`** (MIT): ByteTrack, `PolygonZone`, `LineZone` | Well tested; saves writing geometry code |
| Local outbox | SQLite (stdlib `sqlite3`) | Survives restarts |
| Config | Pydantic models shared with core via a small `cammind-spec` package | One source of truth for the rule schema |

## Frontend (`apps/web`)

| Concern | Choice |
|---|---|
| Framework | **Next.js 16** (App Router), TypeScript, React 19 |
| Styling | Tailwind CSS 4, shadcn/ui-style components |
| Live video | go2rtc's WebRTC player (`video-rtc.js`) wrapped in a React component; MSE fallback |
| Zone editor | SVG overlay on a snapshot (polygon and line tools, drag points) |
| Clip player | `<video>` with event markers |
| Data | Server components + BFF route handlers (same as WatchOnce); SSE for live events |
| Charts | Recharts for usage and precision |
| Tests | Vitest + Playwright |

## Infrastructure (local)

`docker compose -f infra/docker-compose.yml up -d`. Ports don't clash with WatchOnce (5433) and InvoiceFlow (5435 / 6380 / 9100 / 8100 / 3100), so all three can run, memory allowing.

| Service | Port | Notes |
|---|---|---|
| PostgreSQL 16 | **5436** | |
| Redis 7 | **6381** | |
| SeaweedFS (S3) | **9200** | |
| Mailpit | **1027** SMTP / **8027** web | Outbound alerts in dev |
| go2rtc | **1984** API + web · **8554** RTSP · **8555** WebRTC | Config generated from the cameras table |
| MediaMTX (test streams) | **8654** RTSP | Profile `test-streams`: loops MP4s from `infra/test-streams/` as fake cameras |

App processes (outside Docker, for fast reload):

| Process | Port |
|---|---|
| Django API (uvicorn) | **8200** |
| Next.js dashboard | **3200** |
| Celery worker(s) + beat | – |
| Vision worker | – (metrics on **9300**) |

## Hardware targets

| Setup | Expected capacity (720p sub stream, detect at 5 fps) |
|---|---|
| Dev laptop CPU (4–8 cores) | 4 cameras |
| Intel N100 mini PC (~$150) | 2–4 cameras |
| Any PC with a mid-range GPU (DirectML/CUDA) | 12–20 cameras |
| NVIDIA Jetson Orin Nano | 8–12 cameras (v0.2: TensorRT) |

To be measured in week 2 and written into [16](16-testing-and-evals.md#performance).

## Why not…

| Option | Reason not chosen |
|---|---|
| Ultralytics YOLO | Excellent, but AGPL-3.0: a commercial or closed deployment would need an enterprise licence. Kept as an optional plug-in for personal use |
| Send every frame to a vision LLM | Dollars per camera-hour, seconds of latency, and all video leaves the site |
| OpenCV `VideoCapture` for RTSP | Weak reconnect and error reporting; PyAV gives timestamps and codec control |
| DeepStream / GStreamer pipelines | Very fast, but NVIDIA-only and hard to debug; overkill for 4–20 cameras |
| Frigate as the base | Great NVR, but its config and model are home-focused; building our own pipeline is the portfolio point. Interop via MQTT/webhooks is a v0.2 idea |
| FastAPI | Fine choice, but reusing the Django patterns (admin, org scoping, audit, SSE) from WatchOnce is faster |
| LangChain / agent frameworks | Compile and verify are single structured calls; a framework adds weight without value |
| Vector DB | Not needed in the MVP. v0.2 search over events may add pgvector |
