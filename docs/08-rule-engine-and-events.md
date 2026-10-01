# 08 · Rule Engine & Events

The rule engine runs inside the vision worker, after tracking, on every processed frame. It's pure, deterministic Python with no I/O, so it's fully unit-testable with synthetic tracks and a fake clock.

## Inputs and outputs

```python
class FrameObs:            # one processed frame for one camera
    camera_id: str
    ts: datetime           # wall-clock UTC
    tracks: list[TrackObs] # id, class, conf, box, anchor, zones_now, crossed_lines
    motion: MotionObs      # per-zone motion, settled flags

class EngineOutput:
    candidates: list[Candidate]   # new events to report
    updates: list[EventUpdate]    # open events: still active / closed / count changed
    verify_requests: list[VerifyRequest]
```

The engine keeps per-(rule, camera) state and, for track rules, per-(rule, camera, track) state.

## Evaluation per frame

```
for rule in active_rules(camera):
    if not schedule_active(rule, ts):   close open events; reset state; continue
    matches = [t for t in tracks if class_ok(t) and conf_ok(t) and size_ok(t) and where_ok(t)]
    evaluate condition(rule.condition, matches, state)
    apply hold (debounce) → start candidate
    apply cooldown → suppress repeats
    update or close open events
```

### Conditions

| Type | State kept | Candidate starts when | Event closes when |
|---|---|---|---|
| `presence` | first time `len(matches) ≥ min_count` | that has held for `hold_seconds` | fewer than `min_count` for 5 s |
| `count` | first time comparison true | held for `hold_seconds` | comparison false for 10 s |
| `dwell` | per track: time it entered the zone | a track has stayed `min_seconds` (+ `hold_seconds` ignored) | that track leaves or is lost |
| `absence` | last time any match was seen | no match for `min_seconds` | a match appears for 3 s |
| `crossing` | per track: anchor side history | track crosses in `direction` (instant event) | immediately (duration 0) |
| `scene` | consecutive "yes" answers and their times | yes answers span `hold_seconds` | a "no" answer |

Track-based rules (`dwell`, `crossing`, and `presence`/`count` with `verify: track_crop`) fire **per track**. Two people loitering = two events, grouped in the UI as one incident if they overlap in time on the same rule.

### Schedules

- Evaluated in the site's time zone (`zoneinfo`), including daylight saving changes.
- Overnight windows (22:00–06:00) belong to the day they start.
- Site calendars (`school_hours`, `business_hours`) are weekly templates plus a holiday list; `outside_*` is the complement.
- When a window ends, open events close with reason `schedule_ended`.

### Hold (debounce) and cooldown

- **Hold** stops one-frame glitches: a detector blip, a shadow detected as a person for 0.4 s.
- **Cooldown** stops repeats: after an event closes, the same rule + camera (+ track, for track rules) can't start a new event for `cooldown_seconds`. A new track (a different person) isn't blocked by another track's cooldown, but rule-level alert grouping still collapses alerts that start within 10 s of each other into one notification.
- **Max event length:** an event open longer than `max_event_seconds` is closed with reason `max_length` and a new one opens. The user gets "still happening" reminders instead of silence.

## Verify triggers

Verification is expensive, so the engine asks for it only at good moments:

| Situation | Verify request |
|---|---|
| A new matching track in a rule with `verify: track_crop` | after `hold_seconds`, when the box is at least `min_box_px` and not cut off by the frame edge; best frame of the last 1 s (largest box, highest confidence) |
| Same track, still matching, answer was "no" (not an event) | again after `recheck_seconds` (helmet could come off) |
| Same track, answer "unsure" | once more after 3 s if `on_unsure = retry_once` |
| `frame_strip` rules (fall, fight, climbing) | only when a **motion trigger** fires for the track: aspect ratio goes from > 1.3 (tall) to < 0.9 (wide) within 1.5 s, or the anchor's vertical speed spikes; for "fight", 2+ people in the zone with high motion energy inside their boxes |
| `scene` rules | on `motion_settled` in the zone, and every `check_every_seconds` while a "yes" streak is running |

Each verify request carries a `request_id`. The engine treats the candidate as `verifying` until the core sends back the result over Redis. If no result arrives within 20 s, the candidate is reported as `unverified` (or dismissed, per `on_unsure`).

## Event reporting (worker → core)

```http
POST /internal/events
Authorization: Worker <token>
Idempotency-Key: <worker_id>:<rule_version_id>:<camera_id>:<track_id>:<t_start_ms>
```
```json
{
  "rule_version_id": "rv_7Hk2",
  "camera_id": "cam_backyard",
  "track_id": 418,
  "state": "candidate",
  "needs_verify": false,
  "t_start": "2026-10-30T18:14:07.200Z",
  "objects": [{ "class": "person", "conf": 0.83, "box": [0.41, 0.33, 0.52, 0.71] }],
  "zones": ["zn_back_door"],
  "reason": "person in Back door for 3.1 s",
  "snapshot_jpeg_b64": "…"
}
```
Updates (`PATCH /internal/events/{id}`) carry `still_active`, `count`, `closed` + `close_reason` + `t_end`. Everything goes through the worker's SQLite outbox first, so a core outage loses nothing. The idempotency key makes resends safe.

## Event states (core)

See the state diagram in [03](03-architecture.md#event-lifecycle). The core owns state transitions; the worker only reports facts (candidate, still active, closed) and receives verify results.

| State | Shown in timeline | Actions run |
|---|---|---|
| `candidate` | no (transient) | – |
| `verifying` | no (transient) | – |
| `confirmed` | yes | yes |
| `unverified` | yes, with an "unverified" badge | yes, message says "not verified by AI" |
| `dismissed` | only with the "show dismissed" filter | no |
| `closed` | yes, with duration | – |
| `reviewed` | yes, with Confirmed ✓ / False alarm ✗ | – |

## Feedback and tuning

- Each event can be marked **Confirmed** or **False alarm**, with an optional reason (`wrong object`, `outside the zone`, `too short`, `shadow / reflection`, `AI was wrong`).
- Precision per rule = confirmed ÷ reviewed, over the last 7 days.
- **Suggestions** (deterministic, from reasons and event stats), shown on the rule page after 3 false alarms in a day:
  - many short events → raise `hold_seconds`
  - "outside the zone" → shrink the zone or switch the anchor to `bottom_center`
  - small boxes → raise `min_box_px`
  - "AI was wrong" → raise `verify.min_confidence` or rephrase the question (the compiler can suggest a rewording)
- False-alarm snapshots (with permission) are added to the eval set for that site's next eval run.
