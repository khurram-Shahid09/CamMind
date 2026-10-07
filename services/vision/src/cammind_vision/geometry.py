"""Zones and lines (docs/07-video-pipeline.md, "5 · Geometry").

Shapes are stored normalised (0-1, so they survive resolution changes) and converted to
pixels per stream. A track is "in" a zone when its anchor point is inside the polygon;
the default anchor is the bottom centre of the box, where feet or wheels touch the ground.
A line is crossed when the anchor moves to the other side and stays there for a few frames,
which ignores jitter on the line itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np

Anchor = Literal["bottom_center", "center"]
Side = Literal["left", "right"]
CONFIRM_FRAMES = 3


def anchor_point(box: Sequence[float], anchor: Anchor = "bottom_center") -> tuple[float, float]:
    x1, y1, x2, y2 = box[:4]
    if anchor == "center":
        return (x1 + x2) / 2, (y1 + y2) / 2
    return (x1 + x2) / 2, y2


@dataclass
class Polygon:
    id: str
    points: list[tuple[float, float]]  # normalised

    def pixels(self, width: int, height: int) -> np.ndarray:
        return np.array([(x * width, y * height) for x, y in self.points], np.float32)

    def contains(self, point: tuple[float, float], width: int, height: int) -> bool:
        return cv2.pointPolygonTest(self.pixels(width, height), point, False) >= 0

    def mask(self, width: int, height: int) -> np.ndarray:
        canvas = np.zeros((height, width), np.uint8)
        cv2.fillPoly(canvas, [self.pixels(width, height).astype(np.int32)], 1)
        return canvas


def side_of(a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]) -> Side:
    """Which side of the line a->b the point is on, as seen on screen (y grows downwards):
    walking from a to b, "right" is on your right hand."""
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return "right" if cross > 0 else "left"


@dataclass
class Line:
    id: str
    a: tuple[float, float]  # normalised
    b: tuple[float, float]
    in_side: Side = "right"  # crossing towards this side is "in"
    _state: dict[int, tuple[Side, Side | None, int]] = field(default_factory=dict, repr=False)

    def update(
        self, track_id: int, point: tuple[float, float], width: int, height: int
    ) -> Literal["in", "out"] | None:
        """Feed a track's anchor each frame; returns the direction once a crossing is confirmed.

        Note: this checks the side of the infinite line; zones should keep lines where people
        actually pass (a gate, a doorway).
        """
        a = (self.a[0] * width, self.a[1] * height)
        b = (self.b[0] * width, self.b[1] * height)
        now = side_of(a, b, point)
        confirmed, pending, count = self._state.get(track_id, (now, None, 0))
        if now == confirmed:
            self._state[track_id] = (confirmed, None, 0)
            return None
        count = count + 1 if pending == now else 1
        if count < CONFIRM_FRAMES:
            self._state[track_id] = (confirmed, now, count)
            return None
        self._state[track_id] = (now, None, 0)
        return "in" if now == self.in_side else "out"

    def forget(self, track_id: int) -> None:
        self._state.pop(track_id, None)
