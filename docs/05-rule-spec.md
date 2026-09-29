# 05 · Rule Spec

The rule spec is the contract between the plain-English sentence and the rule engine. The compiler ([06](06-rule-compiler.md)) produces it, the user confirms it, and the engine ([08](08-rule-engine-and-events.md)) runs it. It's defined once as Pydantic models in the shared `cammind-spec` package; the JSON Schema sent to the LLM is generated from those models.

## Shape

```
Rule
├── target       what to look at       (object classes, confidence)
├── where        where in the image    (whole frame, zones, a line)
├── condition    what must be true     (presence, count, dwell, absence, crossing, scene)
├── verify       optional AI question  (yes/no on a crop or frame strip)
├── when         schedule              (time windows, site calendars)
├── timing       debounce + cooldown
├── severity     info / warning / critical
└── actions      what to do            (notify, webhook, media)
```

## Fields

### `target`
| Field | Type | Default | Notes |
|---|---|---|---|
| `classes` | list of class names | `["person"]` | From the detector's class list (below). Not used by `scene` conditions |
| `min_confidence` | 0–1 | `0.5` | Per-detection threshold |
| `min_box_px` | int | `24` | Ignores tiny far-away boxes that cause false alarms |

**Detector classes in the MVP** (COCO subset): `person`, `bicycle`, `car`, `motorcycle`, `bus`, `truck`, `dog`, `cat`, `bird`, `backpack`, `handbag`, `suitcase`, `umbrella`, `bottle`, `chair`, `couch`, `cell phone`, `laptop`. Anything else ("package", "helmet", "smoke", "spill") is handled through `verify` or a `scene` condition.

### `where`
| Variant | Fields | Meaning |
|---|---|---|
| `frame` | – | Anywhere in the image |
| `zone` | `zone_ids`, `anchor` (`bottom_center` default, `center`, `any_overlap`) | Object's anchor point is inside any of the zones. `bottom_center` = where feet or wheels touch the ground, which avoids people "in" a zone because their head overlaps it |
| `line` | `line_id`, `direction` (`in`, `out`, `any`) | Track crosses the line |

### `condition` (one per rule)
| Type | Fields | Fires when | Example |
|---|---|---|---|
| `presence` | `min_count` (1) | At least *n* matching objects are present | Someone at the door |
| `count` | `op` (`>`, `>=`, `<`, `<=`), `value` | Number of matching objects meets the comparison | More than 15 students in the parking lot |
| `dwell` | `min_seconds` | One track stays in the zone at least this long | Loitering 2 minutes |
| `absence` | `min_seconds` | No matching object for at least this long (during the schedule) | Guard post empty 5 minutes |
| `crossing` | – (uses `where.line`) | A track crosses the line in the given direction | Someone enters the campus |
| `scene` | `check_every_seconds` (60), `on_motion_settled` (true) | The verify question about the zone (not a track) is answered with the expected answer | Package at the door, fire exit blocked, smoke |

### `verify` (optional; required for `scene`)
| Field | Type | Default | Notes |
|---|---|---|---|
| `question` | string ≤ 160 chars | – | A yes/no question about the image: *"Is this person wearing a hard hat?"* |
| `expect` | `yes` / `no` | – | The answer that confirms the event. For "no helmet", the question asks about the helmet and `expect` is `no` |
| `scope` | `track_crop`, `zone_crop`, `frame`, `frame_strip` | `track_crop` | What the model sees. `frame_strip` = 3–4 frames over ~1.5 s for actions (fall, fight, climbing) |
| `recheck_seconds` | int | `30` | How often the same track can be checked again |
| `min_confidence` | 0–1 | `0.7` | Model's self-reported confidence needed to count |
| `on_unsure` | `retry_once`, `dismiss`, `alert_unverified` | `retry_once` | |

Questions are always about **what is visible**, never about identity ("Is this John?") or protected attributes. The compiler refuses those ([06](06-rule-compiler.md#refusals)).

### `when`
| Field | Type | Notes |
|---|---|---|
| `windows` | list of `{days: [mon…sun], from: "HH:MM", to: "HH:MM"}` | `to < from` means overnight (22:00–06:00) |
| `calendar` | `school_hours`, `business_hours`, `outside_school_hours`, `outside_business_hours`, `null` | Defined per site; handles holidays |
| `timezone` | IANA name | Taken from the site; never guessed by the LLM |

Empty `when` = always on.

### `timing`
| Field | Default | Notes |
|---|---|---|
| `hold_seconds` | `2` | Condition must hold this long before an event starts (debounce). Ignored by `crossing` |
| `cooldown_seconds` | `120` | After an event closes, the same rule + camera (+ same track, for track rules) can't fire again for this long |
| `max_event_seconds` | `600` | Long events are closed and reopened, so a 2-hour truck dwell sends a reminder, not silence |

### `actions`
| Type | Fields |
|---|---|
| `notify` | `channel_ids` and/or `roles` (`owner`, `admin`, `operator`), `include` (`snapshot`, `clip`) |
| `webhook` | `webhook_id` (payload in [10](10-actions-and-notifications.md#webhook-payload)) |
| `media` | `clip_pre_seconds` (5), `clip_post_seconds` (10), `save_snapshot` (true) |

Every rule saves a snapshot. Actions run only for `confirmed` and `unverified` events.

## Examples

### Home: someone at the back door at night
> *"Alert me if anyone is near the back door after 10 PM"*
```json
{
  "spec_version": 1,
  "camera_ids": ["cam_backyard"],
  "target": { "classes": ["person"], "min_confidence": 0.5 },
  "where": { "type": "zone", "zone_ids": ["zn_back_door"], "anchor": "bottom_center" },
  "condition": { "type": "presence", "min_count": 1 },
  "when": { "windows": [{ "days": ["mon","tue","wed","thu","fri","sat","sun"], "from": "22:00", "to": "06:00" }] },
  "timing": { "hold_seconds": 3, "cooldown_seconds": 120 },
  "severity": "warning",
  "actions": [
    { "type": "notify", "roles": ["owner"], "include": ["snapshot", "clip"] },
    { "type": "media", "clip_pre_seconds": 5, "clip_post_seconds": 10 }
  ]
}
```
Assumptions shown to the user: *"'After 10 PM' read as 22:00–06:00 every day. 'Near' read as inside the zone **Back door**."*

### School: crowd in the parking lot during class
> *"Tell the principal if more than 15 students are in the parking lot during class hours"*
```json
{
  "camera_ids": ["cam_parking_1", "cam_parking_2"],
  "target": { "classes": ["person"] },
  "where": { "type": "zone", "zone_ids": ["zn_parking_1", "zn_parking_2"] },
  "condition": { "type": "count", "op": ">", "value": 15 },
  "when": { "calendar": "school_hours" },
  "timing": { "hold_seconds": 20, "cooldown_seconds": 900 },
  "severity": "warning",
  "actions": [{ "type": "notify", "channel_ids": ["ch_principal_telegram"], "include": ["snapshot"] }]
}
```
Assumption: *"The detector sees people, not students. Any person counts."* Counts are per camera; across two cameras they're **not** summed in the MVP (people could appear in both). The compiler says so.

### Factory: no helmet in the press area
> *"Flag any worker in the press area without a helmet"*
```json
{
  "camera_ids": ["cam_press"],
  "target": { "classes": ["person"], "min_box_px": 60 },
  "where": { "type": "zone", "zone_ids": ["zn_press_area"] },
  "condition": { "type": "presence", "min_count": 1 },
  "verify": {
    "question": "Is this person wearing a hard hat or safety helmet on their head?",
    "expect": "no",
    "scope": "track_crop",
    "recheck_seconds": 30,
    "min_confidence": 0.75,
    "on_unsure": "retry_once"
  },
  "timing": { "hold_seconds": 2, "cooldown_seconds": 300 },
  "severity": "critical",
  "actions": [{ "type": "notify", "roles": ["operator"], "include": ["snapshot", "clip"] }]
}
```

### Office: reception left empty
> *"Let me know if the reception desk is empty for more than 5 minutes during office hours"*
```json
{
  "camera_ids": ["cam_reception"],
  "target": { "classes": ["person"] },
  "where": { "type": "zone", "zone_ids": ["zn_behind_desk"] },
  "condition": { "type": "absence", "min_seconds": 300 },
  "when": { "calendar": "business_hours" },
  "timing": { "cooldown_seconds": 1800 },
  "severity": "info",
  "actions": [{ "type": "notify", "roles": ["admin"], "include": ["snapshot"] }]
}
```

### Warehouse: fire exit blocked
> *"Alert if the fire exit is blocked for more than 10 minutes"*
```json
{
  "camera_ids": ["cam_aisle_4"],
  "where": { "type": "zone", "zone_ids": ["zn_fire_exit"] },
  "condition": { "type": "scene", "check_every_seconds": 120, "on_motion_settled": true },
  "verify": {
    "question": "Is anything (boxes, pallets, trolleys, furniture) placed in front of or blocking this door?",
    "expect": "yes",
    "scope": "zone_crop",
    "min_confidence": 0.75
  },
  "timing": { "hold_seconds": 600, "cooldown_seconds": 3600 },
  "severity": "critical",
  "actions": [{ "type": "notify", "roles": ["operator", "admin"], "include": ["snapshot"] }]
}
```
For `scene` rules, `hold_seconds` means "consecutive *yes* answers spanning this long". Here that's 5+ checks over 10 minutes.

### Home: someone fell
> *"Tell me if someone falls in the living room"*
```json
{
  "camera_ids": ["cam_living"],
  "target": { "classes": ["person"] },
  "where": { "type": "frame" },
  "condition": { "type": "presence", "min_count": 1 },
  "verify": {
    "question": "Across these frames, has this person fallen and is now lying on the floor (not sitting or lying on furniture)?",
    "expect": "yes",
    "scope": "frame_strip",
    "recheck_seconds": 10
  },
  "timing": { "hold_seconds": 0, "cooldown_seconds": 300 },
  "severity": "critical",
  "actions": [{ "type": "notify", "roles": ["owner"], "include": ["snapshot", "clip"] }]
}
```
To keep cost down, the engine only sends a fall check when a **trigger** fires: the track's box aspect ratio flips from tall to wide, or its centre drops fast. See [08](08-rule-engine-and-events.md#verify-triggers).

## Validation (after the LLM, before saving)

The spec is rejected, with a message for the user, if:

1. A camera, zone, line or channel ID doesn't exist or isn't in the user's site access.
2. A zone isn't on one of the rule's cameras.
3. `crossing` without `where.type = line`, or `scene` without `verify`.
4. A class isn't in the detector's class list.
5. `count` with `value` < 0; `dwell`/`absence` with `min_seconds` < 1 or > 86,400.
6. Time windows are malformed or empty.
7. `verify.question` asks about identity, faces, age, gender, ethnicity, religion or health beyond the visible event (checked by a deny list + the compiler's own classification).
8. The rule would cost more than the camera's remaining AI budget at its expected check rate (warning, not error; see [09](09-ai-verification.md#budgets)).

## Versioning

- `spec_version` is the schema version (starts at 1). The engine supports the current and previous version.
- Each edit to a rule creates a new **rule version** row. Events point to the rule version that created them, so history stays explainable after edits.
