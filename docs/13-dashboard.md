# 13 · Dashboard

Next.js 16 app in `apps/web`. Dark-first UI (security screens are often viewed in dim rooms) with a light theme. Mobile-friendly for the event timeline and live view; zone drawing is desktop-first but works on a tablet.

## Navigation

```
┌──────────────┬─────────────────────────────────────────────┐
│ CAMMIND        │  Site: Main campus ▾                🔔 3  👤 │
│              ├─────────────────────────────────────────────┤
│ ◉ Live       │                                             │
│ ⚡ Events    │                 (page)                      │
│ 📜 Rules     │                                             │
│ 📷 Cameras   │                                             │
│ 🔔 Channels  │                                             │
│ 📊 Usage     │                                             │
│ ⚙ Settings  │                                             │
└──────────────┴─────────────────────────────────────────────┘
```

## Screens

### 1 · Onboarding (first run)
Three steps with progress:
1. **Name your place** (home / school / business → sets the tier, default calendar and suggested rules).
2. **Add a camera:** paste an RTSP URL, or pick "Use a demo camera" (test stream) or "Use your phone" (instructions for an RTSP camera app). Live test result with a snapshot.
3. **Write your first rule:** suggested sentences for the tier, one click to compile.

### 2 · Live
- Grid of camera tiles (1 / 4 / 9), WebRTC via go2rtc, fallback to refreshing snapshots.
- Each tile: name, health dot, detect fps, count of active rules, and a red outline while an event is open on it.
- **Overlay toggle:** boxes, track IDs and zones drawn live. Detections come over SSE at 2 Hz per camera while the tile is visible (debug mode only, to save bandwidth).
- Click a tile → camera detail.

### 3 · Camera detail
- Large live view, health chart (last 24 h), stream info.
- **Zone editor** (below).
- Rules on this camera with status toggles; recent events strip.

### 4 · Zone editor
```
┌───────────────────────────────────────────────────┐
│ [▭ Area] [╱ Line] [✋ Select]   [↻ New snapshot]   │
│ ┌───────────────────────────────────────────────┐ │
│ │     (snapshot)                                │ │
│ │        ●───────●                              │ │
│ │        │ Back  │      ════►═══  Gate line     │ │
│ │        │ door  │        (in →)                │ │
│ │        ●───────●                              │ │
│ └───────────────────────────────────────────────┘ │
│ Zones: ■ Back door (2 rules)   ■ Gate line (1)    │
└───────────────────────────────────────────────────┘
```
- SVG over the snapshot; click to add points, double-click to close a polygon; drag points; Delete key removes a point.
- Lines: two clicks, then an arrow toggle for the "in" direction.
- Stored normalised; a hint warns when a zone is very small (< 1% of frame) or covers almost everything (> 90%).
- "Show recent detections" draws the last hour of anchor points as dots, so the user can see where people actually walk before drawing.

### 5 · Rules
- List: name, sentence, cameras, status, events (7 d), precision, AI cost (7 d).
- **New rule** (the core screen, see the mock in [06](06-rule-compiler.md#what-the-user-sees)):
  - big text box, tier-based example chips ("Someone at the door at night", "Crowd in parking during class", "No helmet in…")
  - compile → summary card with editable fields, assumptions, cost estimate ("about 120 AI checks a day, ≈ $0.02"), JSON toggle
  - if the compiler asks a question: inline choice buttons; if a zone is missing: "Draw zone now" opens the zone editor in a drawer and comes back
  - **Test:** run on the last 5 minutes of buffer or an uploaded clip; results as a timeline with thumbnails
  - **Activate**
- Rule detail: versions with diffs, stats, tuning suggestions, events.

### 6 · Events
- Timeline grouped by day; filters (camera, rule, severity, state, reviewed); live insertions over SSE.
- Each row: thumbnail, severity, rule name, camera, time, duration, verification badge (✓ AI-verified / ⚠ unverified), review state.
- Keyboard: `j`/`k` move, `c` confirm, `f` false alarm, `Enter` open.
- **Event detail:**
  - clip player with the trigger marked; snapshot with boxes and zones
  - "Why this fired": the rule summary + engine reason + verification answer, confidence and reason
  - deliveries (which channels, when, status)
  - Confirm / False alarm with reason chips; comments

### 7 · Channels
- Cards per channel with test button and delivery health.
- Telegram linking flow with a QR code for the bot link.
- Webhook page shows the secret once, recent deliveries with response codes, and the signature-check snippet.

### 8 · Usage
- Cost per day (bar chart), per camera and per rule (tables), budget bars with caps editable by owners.
- "Frames → detections → verifications" funnel per camera, showing how much the cheap stages filtered. A good portfolio screenshot.

### 9 · Settings
- Org: name, tier, members and site access, API tokens.
- Sites: time zone, calendars, holidays, retention.
- Privacy: cloud AI default per site, camera notice text (for schools and workplaces), data export and delete.
- Audit log viewer.

## Components

| Component | Notes |
|---|---|
| `<LivePlayer cameraId>` | go2rtc WebRTC client; reconnects; pauses when off-screen (IntersectionObserver) |
| `<ZoneCanvas>` | SVG editor; pure, controlled; unit-tested geometry helpers |
| `<RuleCard spec onChange>` | Renders the spec as an editable sentence; validates through `/rules/validate` (debounced) |
| `<EventRow>`, `<EventDetail>` | Shared by timeline and camera pages |
| `<ClipPlayer markers>` | Native video with marker overlay |
| `useEventStream()` | SSE hook with reconnect and backfill since last event id |

## Empty and error states

- No cameras: onboarding prompt with the demo camera option.
- Camera offline: tile shows last snapshot greyed out, "offline since 14:02", and a "Troubleshoot" link (common causes: camera rebooted, IP changed, wrong sub-stream path).
- Compile failed: the form editor with what was understood; never a dead end.
- Budget exhausted: banner on Rules and Events with a link to Usage.
