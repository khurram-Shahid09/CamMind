"""Draw boxes, track ids and zones on a frame (debug output now, alert snapshots later)."""

from collections.abc import Iterable

import cv2
import numpy as np

from .geometry import Polygon
from .track import Track

BOX = (56, 189, 248)  # BGR of the dashboard accent
ZONE = (36, 191, 251)


def annotate(
    image: np.ndarray, tracks: Iterable[Track], zones: Iterable[Polygon] = ()
) -> np.ndarray:
    out = image.copy()
    height, width = out.shape[:2]
    thickness = max(2, round(width / 640))
    for zone in zones:
        points = zone.pixels(width, height).astype(np.int32)
        overlay = out.copy()
        cv2.fillPoly(overlay, [points], ZONE)
        out = cv2.addWeighted(overlay, 0.18, out, 0.82, 0)
        cv2.polylines(out, [points], True, ZONE, thickness)
    for track in tracks:
        x1, y1, x2, y2 = (int(v) for v in track.box)
        cv2.rectangle(out, (x1, y1), (x2, y2), BOX, thickness)
        label = f"#{track.id} {track.class_name} {track.confidence:.2f}"
        scale = 0.5 * thickness / 2
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        cv2.rectangle(out, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), BOX, -1)
        cv2.putText(
            out,
            label,
            (x1 + 3, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (10, 12, 16),
            1,
            cv2.LINE_AA,
        )
    return out
