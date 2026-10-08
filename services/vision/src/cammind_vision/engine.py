"""Rule engine (docs/08-rule-engine-and-events.md).

Pure and deterministic: tracks and a timestamp in, event starts and ends out. No I/O, so
every condition, schedule, hold and cooldown is unit-tested with synthetic tracks.

- Aggregate rules (presence, count, absence) keep one event per rule and camera.
- Per-track rules (dwell, crossing, and anything verified on a track crop) keep one event
  per track, so two people loitering are two events.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from cammind_spec import (
    Absence,
    Count,
    Crossing,
    Dwell,
    Presence,
    RuleSpec,
    WhereLine,
    WhereZone,
)

from .geometry import Line, Polygon, anchor_point
from .track import Track

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SEEN_WITHIN_S = 1.0  # a track missed by the detector for a moment is still "there"
CLOSE_AFTER_S = {"presence": 5.0, "count": 10.0, "absence": 3.0}


@dataclass
class CompiledRule:
    id: str  # rule version id
    spec: RuleSpec
    zones: dict[str, Polygon] = field(default_factory=dict)
    lines: dict[str, Line] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)  # zone/line id -> name
    timezone: str = "UTC"


@dataclass
class EngineEvent:
    kind: str  # "start" | "end"
    key: str  # stable per event: rule, camera, track and start time
    rule_id: str
    camera_id: str
    ts: datetime
    track_id: int | None = None
    reason: str = ""
    objects: list[dict] = field(default_factory=list)
    needs_verify: bool = False
    close_reason: str = ""


@dataclass
class _State:
    true_since: datetime | None = None
    false_since: datetime | None = None
    open_key: str | None = None
    opened_at: datetime | None = None
    cooldown_until: datetime | None = None
    entered_at: datetime | None = None  # dwell
    last_match: datetime | None = None  # absence


def _objects(tracks: list[Track]) -> list[dict]:
    return [
        {
            "track_id": t.id,
            "class": t.class_name,
            "conf": round(float(t.confidence), 3),
            "box": [round(float(v), 1) for v in t.box],
        }
        for t in tracks
    ]


class Engine:
    def __init__(self, rules: list[CompiledRule]) -> None:
        self.rules = rules
        self._state: dict[tuple, _State] = {}
        self._started: dict[str, datetime] = {}  # rule id -> first frame seen

    # --- helpers ---

    def _active(self, rule: CompiledRule, ts: datetime) -> bool:
        windows = rule.spec.when.windows
        if not windows:
            return True
        local = ts.astimezone(ZoneInfo(rule.timezone))
        day = DAYS[local.weekday()]
        previous = DAYS[(local.weekday() - 1) % 7]
        return any(w.covers(day, local.time(), previous) for w in windows)  # type: ignore[arg-type]

    def _place(self, rule: CompiledRule) -> str:
        where = rule.spec.where
        if isinstance(where, WhereZone):
            return " / ".join(rule.names.get(z, z) for z in where.zone_ids)
        if isinstance(where, WhereLine):
            return rule.names.get(where.line_id, where.line_id)
        return "view"

    def _matches(
        self, rule: CompiledRule, tracks: list[Track], ts: datetime, w: int, h: int
    ) -> list[Track]:
        target, where = rule.spec.target, rule.spec.where
        out = []
        for t in tracks:
            if (ts - t.last_seen).total_seconds() > SEEN_WITHIN_S:
                continue
            x1, y1, x2, y2 = t.box
            if t.class_name not in target.classes or t.confidence < target.min_confidence:
                continue
            if min(x2 - x1, y2 - y1) < target.min_box_px:
                continue
            if isinstance(where, WhereZone):
                point = anchor_point(t.box, where.anchor)
                if not any(
                    rule.zones[z].contains(point, w, h) for z in where.zone_ids if z in rule.zones
                ):
                    continue
            out.append(t)
        return out

    def _start(self, rule, camera_id, state, ts, track_id, reason, objects) -> EngineEvent:
        key = f"{rule.id}:{camera_id}:{track_id if track_id is not None else '-'}:{int(ts.timestamp() * 1000)}"
        state.open_key, state.opened_at = key, ts
        return EngineEvent(
            "start",
            key,
            rule.id,
            camera_id,
            ts,
            track_id,
            reason,
            objects,
            needs_verify=rule.spec.verify is not None,
        )

    def _end(self, rule, camera_id, state, ts, track_id, close_reason) -> EngineEvent:
        key = state.open_key or ""
        state.open_key, state.opened_at, state.true_since = None, None, None
        if close_reason != "max_length":
            state.cooldown_until = ts + timedelta(seconds=rule.spec.timing.cooldown_seconds)
        return EngineEvent("end", key, rule.id, camera_id, ts, track_id, close_reason=close_reason)

    # --- main entry ---

    def update(
        self, camera_id: str, ts: datetime, tracks: list[Track], width: int, height: int
    ) -> list[EngineEvent]:
        events: list[EngineEvent] = []
        for rule in self.rules:
            if camera_id not in rule.spec.camera_ids:
                continue
            self._started.setdefault(rule.id + camera_id, ts)
            if not self._active(rule, ts):
                for key, state in list(self._state.items()):
                    if key[0] == rule.id and key[1] == camera_id:
                        if state.open_key:
                            events.append(
                                self._end(rule, camera_id, state, ts, key[2], "schedule_ended")
                            )
                        del self._state[key]
                continue
            matches = self._matches(rule, tracks, ts, width, height)
            if rule.spec.per_track:
                events += self._per_track(rule, camera_id, ts, tracks, matches, width, height)
            else:
                events += self._aggregate(rule, camera_id, ts, matches)
        return events

    def _aggregate(
        self, rule: CompiledRule, camera_id: str, ts: datetime, matches: list[Track]
    ) -> list[EngineEvent]:
        spec, cond = rule.spec, rule.spec.condition
        state = self._state.setdefault((rule.id, camera_id, None), _State())
        n = len(matches)
        place = self._place(rule)
        if isinstance(cond, Presence):
            true = n >= cond.min_count
            reason = f"{n} {spec.target.classes[0]}{'s' if n != 1 else ''} in {place}"
        elif isinstance(cond, Count):
            true = {
                ">": n > cond.value,
                ">=": n >= cond.value,
                "<": n < cond.value,
                "<=": n <= cond.value,
            }[cond.op]
            reason = f"{n} {spec.target.classes[0]}s in {place} ({cond.op} {cond.value})"
        elif isinstance(cond, Absence):
            if matches or state.last_match is None:
                state.last_match = (
                    ts if matches else state.last_match or self._started[rule.id + camera_id]
                )
            empty_s = (ts - state.last_match).total_seconds()
            true = not matches and empty_s >= cond.min_seconds
            reason = f"nobody in {place} for {empty_s:.0f} s"
        else:
            return []

        events = []
        if true:
            state.false_since = None
            state.true_since = state.true_since or ts
            held = (ts - state.true_since).total_seconds()
            hold = 0 if isinstance(cond, Absence) else spec.timing.hold_seconds
            cooling = state.cooldown_until is not None and ts < state.cooldown_until
            if state.open_key is None and held >= hold and not cooling:
                events.append(
                    self._start(rule, camera_id, state, ts, None, reason, _objects(matches))
                )
            elif (
                state.open_key
                and state.opened_at
                and (ts - state.opened_at).total_seconds() >= spec.timing.max_event_seconds
            ):
                events.append(self._end(rule, camera_id, state, ts, None, "max_length"))
        else:
            state.true_since = None
            state.false_since = state.false_since or ts
            if (
                state.open_key
                and (ts - state.false_since).total_seconds() >= CLOSE_AFTER_S[cond.type]
            ):
                events.append(self._end(rule, camera_id, state, ts, None, "condition_ended"))
        return events

    def _per_track(self, rule, camera_id, ts, tracks, matches, width, height) -> list[EngineEvent]:
        spec, cond = rule.spec, rule.spec.condition
        place = self._place(rule)
        events = []
        matched = {t.id for t in matches}
        if isinstance(cond, Crossing):
            line = rule.lines.get(spec.where.line_id)  # type: ignore[union-attr]
            if line is None:
                return []
            for t in matches:
                direction = line.update(t.id, anchor_point(t.box), width, height)
                wanted = spec.where.direction  # type: ignore[union-attr]
                if direction and (wanted == "any" or wanted == direction):
                    state = self._state.setdefault((rule.id, camera_id, t.id), _State())
                    if state.cooldown_until and ts < state.cooldown_until:
                        continue
                    events.append(
                        self._start(
                            rule,
                            camera_id,
                            state,
                            ts,
                            t.id,
                            f"{t.class_name} crossed {place} ({direction})",
                            _objects([t]),
                        )
                    )
                    events.append(self._end(rule, camera_id, state, ts, t.id, "instant"))
            return events

        for t in matches:
            state = self._state.setdefault((rule.id, camera_id, t.id), _State())
            state.entered_at = state.entered_at or ts
            state.false_since = None
            inside = (ts - state.entered_at).total_seconds()
            need = cond.min_seconds if isinstance(cond, Dwell) else spec.timing.hold_seconds
            cooling = state.cooldown_until is not None and ts < state.cooldown_until
            if state.open_key is None and inside >= need and not cooling:
                verb = (
                    f"stayed in {place} for {inside:.0f} s"
                    if isinstance(cond, Dwell)
                    else f"in {place}"
                )
                events.append(
                    self._start(
                        rule,
                        camera_id,
                        state,
                        ts,
                        t.id,
                        f"{t.class_name} #{t.id} {verb}",
                        _objects([t]),
                    )
                )
        for key, state in list(self._state.items()):
            if key[0] != rule.id or key[1] != camera_id or key[2] is None or key[2] in matched:
                continue
            state.entered_at = None
            if state.open_key:
                events.append(self._end(rule, camera_id, state, ts, key[2], "left"))
            elif state.cooldown_until is None or ts >= state.cooldown_until:
                del self._state[key]
        return events
