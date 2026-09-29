# 03 · Architecture

## Components

```mermaid
flowchart TB
  subgraph Site["On site (PC, mini PC or edge box)"]
    CAM["IP cameras<br/>RTSP"]
    GO2RTC["go2rtc<br/>one connection per camera,<br/>restream + WebRTC"]
    subgraph Vision["services/vision (one process per N cameras)"]
      DEC["Decoder<br/>PyAV, sampled fps"]
      MOT["Motion gate"]
      DET["Detector<br/>ONNX Runtime"]
      TRK["Tracker<br/>ByteTrack"]
      ENG["Rule engine"]
      OUTBOX["Local outbox<br/>(SQLite)"]
    end
    SEG["Segment recorder<br/>FFmpeg, 2 s chunks,<br/>rolling 2 min"]
  end
  subgraph Core["services/core (Django)"]
    API["DRF API + SSE"]
    ADMIN["Django admin"]
  end
  subgraph Workers["Celery workers"]
    CMP["compile queue<br/>NL → rule spec"]
    VER["verify queue<br/>vision LLM"]
    MED["media queue<br/>clip cut, thumbnails"]
    ACT["actions queue<br/>notify, webhook"]
    BEAT["beat<br/>retention, health, budgets"]
  end
  WEB["Next.js dashboard"]
  PG[("PostgreSQL 16")]
  REDIS[("Redis 7<br/>broker, pub/sub,<br/>rule config cache")]
  S3[("S3 storage<br/>snapshots, clips")]
  LLM["LLM provider<br/>Gemini · Claude · fake"]
  CH["Email · Telegram · Slack · Webhooks"]

  CAM --> GO2RTC
  GO2RTC --> DEC --> MOT --> DET --> TRK --> ENG
  GO2RTC --> SEG
  ENG --> OUTBOX --> API
  API --> VER
  API --> MED
  API --> ACT
  WEB --> API
  WEB -. WebRTC live .-> GO2RTC
  CMP --> LLM
  VER --> LLM
  MED --> SEG
  MED --> S3
  ACT --> CH
  Core --> PG
  Core --> REDIS
  Workers --> PG
  Workers --> REDIS
  ENG <-. rule updates (pub/sub) .-> REDIS
```

## Why the vision worker is not a Celery task

Celery is built for short jobs. A camera stream is a long-running loop that holds a decoder, a tracker state and a frame buffer in memory. So:

- **`services/vision`** is a plain Python process (`python -m cammind_vision run --cameras cam_a,cam_b`). It's supervised by Docker (restart policy) or a small supervisor in dev. One process handles several cameras, with one thread per camera for decoding and a shared detector session that batches frames.
- **Celery** handles everything short and retryable: compiling rules, verification calls, cutting clips, sending notifications, retention.

The vision worker talks to the core over HTTP (`POST /internal/events`, with a worker token) and listens on Redis for rule and camera changes. That boundary is what later allows an edge box at a school to report to a hosted control plane ([17](17-deployment-ops.md#multi-site-v03-designed-now)).

## Data flow: from frame to alert

```mermaid
sequenceDiagram
  participant C as Camera
  participant G as go2rtc
  participant V as Vision worker
  participant A as Core API
  participant Q as Celery (verify / media / actions)
  participant L as Vision LLM
  participant U as User

  C->>G: RTSP (H.264/H.265)
  G->>V: RTSP restream (sub stream)
  loop every sampled frame (5 fps)
    V->>V: motion gate → detect → track
    V->>V: rule engine updates conditions per track
  end
  V->>A: candidate event (rule, track, boxes, snapshot JPEG, t_start)
  alt rule needs verification
    A->>Q: verify task
    Q->>L: crop(s) + one yes/no question
    L-->>Q: {answer, confidence, reason}
    Q->>A: confirm or dismiss
  end
  A->>Q: media task (cut clip from segments, upload)
  A->>Q: actions task (notify with snapshot)
  Q-->>U: Telegram / Slack / email / webhook
  Q->>A: clip ready → follow-up message with clip
  A-->>U: SSE: new event on dashboard
```

The snapshot alert is sent **before** the clip is ready, so the user is told within seconds. The clip follows a few seconds later, after the post-event part has been recorded.

## Event lifecycle

```mermaid
stateDiagram-v2
  [*] --> candidate: rule conditions held for min time
  candidate --> verifying: rule has a verify step
  candidate --> confirmed: no verify step
  verifying --> confirmed: model answers "yes"
  verifying --> dismissed: model answers "no"
  verifying --> unverified: budget exhausted / model error after retries
  confirmed --> notified: actions sent
  unverified --> notified: actions sent, marked "unverified"
  notified --> closed: condition ended (track gone, count dropped)
  closed --> reviewed: user marks Confirmed / False alarm
  dismissed --> [*]
  reviewed --> [*]
```

- **Dismissed** events are kept (without clips) for tuning and evals, and hidden from the default timeline.
- An event stays **open** while its condition holds, so a person standing at the door for 3 minutes is one event with a duration, not 36 alerts.

## Core modules (`services/core`)

| App | Responsibility |
|---|---|
| `accounts` | Orgs, sites, users, memberships, roles, API tokens |
| `cameras` | Cameras, streams, encrypted credentials, health, go2rtc config sync |
| `zones` | Polygons and lines per camera |
| `rules` | Rule, rule version, compiled spec, validation, test runs |
| `compiler` | NL → spec via the LLM provider; clarifying questions |
| `events` | Event ingest from workers, state machine, feedback, comments |
| `verification` | Verify tasks, prompt templates, caching, budgets |
| `media` | Segment index, clip cutting, thumbnails, S3 upload, retention |
| `actions` | Channels (email, Telegram, Slack, webhook), deliveries, retries |
| `usage` | AI usage ledger and caps |
| `audit` | Append-only audit log (copied pattern from WatchOnce) |
| `common` | Prefixed IDs, org-scoped managers, LLM provider wrapper, SSE helpers |

## Vision worker modules (`services/vision`)

| Module | Responsibility |
|---|---|
| `ingest` | Open RTSP via PyAV, reconnect with backoff, frame sampling, health metrics |
| `motion` | Downscaled frame differencing with a background model; per-zone motion masks |
| `detect` | ONNX Runtime session (CPU / DirectML / CUDA), batching across cameras, class filtering |
| `track` | ByteTrack via `supervision`; stable track IDs, velocity |
| `geometry` | Zone polygons, line crossing with direction, normalised ↔ pixel |
| `engine` | Evaluates compiled rules per frame and per track; debounce, cooldown, schedule |
| `snap` | Draw boxes and zones, encode JPEG, crops for verification |
| `outbox` | SQLite queue of events and heartbeats; retried POSTs to the core |
| `config` | Loads cameras and rules from the core; hot reload on Redis pub/sub |

## Key decisions

| Decision | Record |
|---|---|
| Detectors and rules decide; the LLM answers questions | [ADR-0001](adr/0001-detectors-and-rules-decide.md) |
| Plain English compiles to a typed spec that the user confirms | [ADR-0002](adr/0002-compiled-rules-not-prompts.md) |
| Edge-first processing; cloud AI opt-in, crops only | [ADR-0003](adr/0003-edge-first-privacy.md) |
| Same stack as WatchOnce and InvoiceFlow | [ADR-0004](adr/0004-reuse-portfolio-stack.md) |
| No face recognition | [ADR-0005](adr/0005-no-face-recognition.md) |
| Apache-2.0 detector via ONNX Runtime | [ADR-0006](adr/0006-permissive-detector-onnx.md) |

## Failure handling

| Failure | Behaviour |
|---|---|
| Camera drops | Reconnect with backoff; health → `reconnecting`; after 2 min → system event |
| Core API down | Worker keeps detecting; events go to the SQLite outbox and are sent when it's back (with original timestamps) |
| Redis down | Worker keeps last known rules; config reload resumes when Redis is back |
| LLM timeout / error | Two retries with backoff; then event → `unverified` (alerts still go out, marked) |
| LLM budget reached | Same as above, plus a usage warning to owners |
| Notification channel fails | Retries with backoff for up to 1 hour; delivery marked failed; other channels unaffected |
| Detector too slow (CPU overloaded) | Worker lowers detection fps per camera (5 → 3 → 2) and reports it in health, rather than lagging behind real time |
