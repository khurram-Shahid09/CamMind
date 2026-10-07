from collections import deque
from datetime import UTC, datetime, timedelta

import pytest
from cammind_spec import RuleSpec

from cammind_vision.engine import CompiledRule, Engine
from cammind_vision.geometry import Line, Polygon
from cammind_vision.track import Track

W, H = 1000, 500
T0 = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)  # 23:00 in Karachi
DOOR = Polygon("zn_door", [(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)])  # bottom-left


def person(tid: int, x: float, y: float = 480, ts: datetime = T0, cls: str = "person") -> Track:
    """Box whose bottom centre is at (x, y)."""
    return Track(tid, cls, ts, ts, (x - 30, y - 200, x + 30, y), 0.9, deque(), deque())


def rule(condition: dict, where: dict | None = None, **extra) -> CompiledRule:
    spec = RuleSpec.model_validate(
        {
            "camera_ids": ["cam_1"],
            "where": where or {"type": "zone", "zone_ids": ["zn_door"]},
            "condition": condition,
            **extra,
        }
    )
    return CompiledRule(
        "rv_1",
        spec,
        zones={"zn_door": DOOR},
        names={"zn_door": "Back door"},
        timezone="Asia/Karachi",
    )


def run(engine: Engine, frames: list[tuple[float, list[Track]]]) -> list[tuple[float, str, str]]:
    out = []
    for seconds, tracks in frames:
        ts = T0 + timedelta(seconds=seconds)
        for t in tracks:
            t.last_seen = ts
        for e in engine.update("cam_1", ts, tracks, W, H):
            out.append((seconds, e.kind, e.reason or e.close_reason))
    return out


def every(start: float, end: float, step: float, tracks_at) -> list[tuple[float, list[Track]]]:
    n = round((end - start) / step)
    return [(start + i * step, tracks_at(start + i * step)) for i in range(n + 1)]


def test_presence_needs_the_hold_and_closes_after_the_person_leaves() -> None:
    engine = Engine([rule({"type": "presence"}, timing={"hold_seconds": 3})])
    inside = person(1, 200)
    frames = every(0, 4, 0.5, lambda s: [inside]) + every(4.5, 12, 0.5, lambda s: [])
    events = run(engine, frames)
    assert events == [(3.0, "start", "1 person in Back door"), (9.5, "end", "condition_ended")]


def test_a_blip_shorter_than_the_hold_is_ignored() -> None:
    engine = Engine([rule({"type": "presence"}, timing={"hold_seconds": 2})])
    blip = person(1, 200)
    assert run(engine, [(0, [blip]), (0.5, [blip]), (1.0, []), (1.5, [])]) == []


def test_head_in_zone_but_feet_outside_does_not_count() -> None:
    engine = Engine([rule({"type": "presence"}, timing={"hold_seconds": 0})])
    assert run(engine, [(0, [person(1, 200, y=240)])]) == []  # feet above the zone


def test_cooldown_blocks_a_repeat() -> None:
    engine = Engine(
        [rule({"type": "presence"}, timing={"hold_seconds": 0, "cooldown_seconds": 60})]
    )
    p = person(1, 200)
    events = run(engine, [(0, [p]), (1, []), (7, []), (10, [p]), (70, [p])])
    assert [e[1] for e in events] == ["start", "end", "start"]
    assert events[2][0] == 70


def test_count_rule() -> None:
    crowd = rule(
        {"type": "count", "op": ">", "value": 2},
        where={"type": "frame"},
        timing={"hold_seconds": 1},
    )
    engine = Engine([crowd])
    three = [person(i, 100 + i * 200) for i in range(3)]
    events = run(engine, [(0, three[:2]), (1, three[:2]), (2, three), (3, three)])
    assert events == [(3, "start", "3 persons in view (> 2)")]


def test_absence_after_min_seconds() -> None:
    engine = Engine([rule({"type": "absence", "min_seconds": 300})])
    guard = person(1, 200)
    events = run(
        engine, [(0, [guard]), (100, []), (299, []), (301, []), (400, [guard]), (404, [guard])]
    )
    assert events[0][:2] == (301, "start") and "nobody in Back door" in events[0][2]
    assert events[1][:2] == (404, "end")


def test_dwell_is_per_person() -> None:
    engine = Engine([rule({"type": "dwell", "min_seconds": 10})])
    a, b = person(1, 100), person(2, 300)
    frames = every(0, 12, 1, lambda s: [a, b] if s >= 5 else [a])
    events = run(engine, frames)
    assert [(e[0], e[1]) for e in events] == [(10, "start")]
    assert "person #1 stayed in Back door" in events[0][2]
    events = run(engine, every(13, 16, 1, lambda s: [b]))
    assert [(e[0], e[1]) for e in events] == [(13, "end"), (15, "start")]


def test_crossing_only_in_the_wanted_direction() -> None:
    gate = Line("ln_gate", (0, 0.5), (1, 0.5), in_side="right")  # "in" = downwards on screen
    r = rule({"type": "crossing"}, where={"type": "line", "line_id": "ln_gate", "direction": "in"})
    r.lines, r.names = {"ln_gate": gate}, {"ln_gate": "Gate line"}
    engine = Engine([r])
    walker = person(5, 500, y=100)
    frames = []
    for i, y in enumerate([100, 200, 300, 350, 400, 400]):
        frames.append((i, [person(5, 500, y=y)]))
    events = run(engine, frames)
    assert [e[1] for e in events] == ["start", "end"]
    assert events[0][2] == "person crossed Gate line (in)"
    back = run(
        engine, [(10 + i, [person(5, 500, y=y)]) for i, y in enumerate([200, 150, 100, 100])]
    )
    assert back == []  # "out" isn't wanted
    assert walker.id == 5


def test_schedule_window_in_site_time() -> None:
    night = rule(
        {"type": "presence"},
        timing={"hold_seconds": 0},
        when={"windows": [{"from": "22:00", "to": "06:00"}]},
    )
    day = rule(
        {"type": "presence"},
        timing={"hold_seconds": 0},
        when={"windows": [{"from": "09:00", "to": "17:00"}]},
    )
    day.id = "rv_day"
    events = Engine([night, day]).update("cam_1", T0, [person(1, 200)], W, H)
    assert [e.rule_id for e in events] == ["rv_1"]  # 23:00 Karachi


def test_other_classes_and_cameras_are_ignored() -> None:
    engine = Engine([rule({"type": "presence"}, timing={"hold_seconds": 0})])
    assert run(engine, [(0, [person(1, 200, cls="dog")])]) == []
    assert engine.update("cam_other", T0, [person(1, 200)], W, H) == []


def test_verify_rules_ask_for_verification_per_track() -> None:
    helmet = rule(
        {"type": "presence"},
        timing={"hold_seconds": 1},
        verify={"question": "Is this person wearing a hard hat?", "expect": "no"},
    )
    events = Engine([helmet]).update("cam_1", T0, [person(1, 200), person(2, 300)], W, H)
    assert events == []
    engine = Engine([helmet])
    out = run(engine, [(0, [person(1, 200)]), (1, [person(1, 200)])])
    assert out == [(1, "start", "person #1 in Back door")]


@pytest.mark.parametrize("seconds", [601])
def test_long_events_are_split(seconds: int) -> None:
    engine = Engine(
        [rule({"type": "presence"}, timing={"hold_seconds": 0, "max_event_seconds": 600})]
    )
    p = person(1, 200)
    events = run(engine, [(0, [p]), (seconds, [p]), (seconds + 1, [p])])
    assert [e[1] for e in events] == ["start", "end", "start"]
    assert events[1][2] == "max_length"
