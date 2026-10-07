from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from cammind_vision.detect import CLASS_NAMES, Detections
from cammind_vision.motion import MotionGate
from cammind_vision.track import Tracker

T0 = datetime(2026, 10, 7, 18, 0, tzinfo=UTC)


def scene(square_at: int | None = None, brightness: int = 60) -> np.ndarray:
    image = np.full((360, 640, 3), brightness, np.uint8)
    image[300:, :] = brightness + 20  # a floor
    if square_at is not None:
        image[100:220, square_at : square_at + 60] = 230
    return image


def test_static_scene_is_quiet_and_moving_object_opens_the_gate() -> None:
    gate = MotionGate()
    assert not gate.update(scene()).moving  # first frame builds the background
    assert not gate.update(scene()).moving
    assert gate.update(scene(square_at=300)).moving


def test_motion_outside_watched_area_is_ignored() -> None:
    mask = np.zeros((360, 640), np.uint8)
    mask[:, :200] = 1  # only the left part is watched
    gate = MotionGate(mask)
    gate.update(scene())
    assert not gate.update(scene(square_at=450)).moving
    assert gate.update(scene(square_at=50)).moving


def test_lights_switching_resets_instead_of_alarming() -> None:
    gate = MotionGate()
    gate.update(scene(brightness=40))
    result = gate.update(scene(brightness=200))
    assert result.reset and not result.moving
    assert not gate.update(scene(brightness=200)).moving


def person(x: float) -> Detections:
    return Detections(
        np.array([[x, 100, x + 60, 300]], np.float32),
        np.array([0.9], np.float32),
        np.array([CLASS_NAMES.index("person")]),
    )


def test_tracker_keeps_one_id_for_a_walking_person_and_drops_lost_tracks() -> None:
    tracker = Tracker(fps=5, lost_after_s=2)
    ids = set()
    for i in range(10):
        tracks = tracker.update(person(100 + i * 8), T0 + timedelta(seconds=i * 0.2))
        ids |= {t.id for t in tracks}
    assert len(ids) == 1
    track = tracker.tracks[ids.pop()]
    assert track.class_name == "person"
    assert track.age_s == 1.8
    assert track.anchors[-1] == (100 + 9 * 8 + 30, 300)
    assert track.aspects[-1] == pytest.approx(200 / 60)

    for i in range(15):  # 3 s with nobody there
        tracker.update(Detections.empty(), T0 + timedelta(seconds=2 + i * 0.2))
    assert tracker.tracks == {}
