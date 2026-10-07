import pytest

from cammind_vision.geometry import Line, Polygon, anchor_point, side_of

W, H = 1000, 500


def test_anchor_is_where_feet_touch_the_ground() -> None:
    assert anchor_point((100, 50, 200, 450)) == (150, 450)
    assert anchor_point((100, 50, 200, 450), "center") == (150, 250)


def test_polygon_contains_uses_pixels_of_the_stream() -> None:
    door = Polygon("zn_door", [(0.1, 0.5), (0.4, 0.5), (0.4, 1.0), (0.1, 1.0)])
    assert door.contains((250, 400), W, H)
    assert not door.contains((250, 100), W, H)  # head in the zone, feet outside
    assert door.contains((100, 250), W, H)  # on the edge counts
    assert int(door.mask(W, H).sum()) == pytest.approx(300 * 250, rel=0.02)


def test_side_as_seen_on_screen() -> None:
    a, b = (0, 250), (1000, 250)  # drawn left to right
    assert side_of(a, b, (500, 400)) == "right"  # below the line = walker's right hand
    assert side_of(a, b, (500, 100)) == "left"


def walk(line: Line, track: int, ys: list[float]) -> list[str | None]:
    return [line.update(track, (500, y), W, H) for y in ys]


def test_crossing_needs_three_frames_on_the_new_side() -> None:
    gate = Line("ln_gate", (0, 0.5), (1, 0.5), in_side="right")
    events = walk(gate, 1, [100, 200, 300, 320, 340, 360])
    assert events == [None, None, None, None, "in", None]
    assert walk(gate, 1, [200, 150, 100]) == [None, None, "out"]


def test_jitter_on_the_line_is_ignored() -> None:
    gate = Line("ln_gate", (0, 0.5), (1, 0.5))
    assert walk(gate, 7, [240, 260, 240, 260, 240, 260, 240]) == [None] * 7


def test_tracks_are_independent_and_forgettable() -> None:
    gate = Line("ln_gate", (0, 0.5), (1, 0.5))
    walk(gate, 1, [100, 300, 300])
    assert walk(gate, 2, [400, 400]) == [None, None]  # starts on the far side: no crossing
    gate.forget(1)
    assert walk(gate, 1, [300]) == [None]
