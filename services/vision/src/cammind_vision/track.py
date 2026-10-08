"""Tracking (docs/07-video-pipeline.md, "4 · Tracking").

ByteTrack (from ``supervision``), one tracker per camera, tuned for ~5 fps. Each track keeps
what the rule engine needs: when it was first and last seen, its box, recent anchor points
and box shapes. Track ids are local to one camera and one worker run: they're never
identities and never linked across cameras (ADR-0005).
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import supervision as sv

from .detect import CLASS_NAMES, Detections
from .geometry import anchor_point

HISTORY = 15  # ~3 s at 5 fps


@dataclass
class Track:
    id: int
    class_name: str
    first_seen: datetime
    last_seen: datetime
    box: tuple[float, float, float, float]
    confidence: float
    anchors: deque = field(default_factory=lambda: deque(maxlen=HISTORY))
    aspects: deque = field(default_factory=lambda: deque(maxlen=HISTORY))  # height / width

    @property
    def age_s(self) -> float:
        return (self.last_seen - self.first_seen).total_seconds()


class Tracker:
    def __init__(self, fps: float = 5.0, lost_after_s: float = 5.0) -> None:
        self._byte = sv.ByteTrack(
            track_activation_threshold=0.4,
            lost_track_buffer=max(1, round(lost_after_s * fps)),
            minimum_matching_threshold=0.8,
            frame_rate=max(1, round(fps)),
        )
        self.lost_after_s = lost_after_s
        self.tracks: dict[int, Track] = {}

    def update(self, detections: Detections, ts: datetime) -> list[Track]:
        """Tracks seen in this frame. Tracks unseen for ``lost_after_s`` are dropped."""
        tracked = self._byte.update_with_detections(
            sv.Detections(
                xyxy=detections.boxes.astype(np.float32),
                confidence=detections.scores.astype(np.float32),
                class_id=detections.class_ids.astype(int),
            )
        )
        seen = []
        for box, confidence, class_id, track_id in zip(
            tracked.xyxy,
            tracked.confidence,  # type: ignore[arg-type]  # set: we passed confidences
            tracked.class_id,  # type: ignore[arg-type]
            tracked.tracker_id,  # type: ignore[arg-type]
            strict=True,
        ):
            tid = int(track_id)
            track = self.tracks.get(tid)
            if track is None:
                track = Track(
                    tid, CLASS_NAMES[int(class_id)], ts, ts, tuple(box), float(confidence)
                )
                self.tracks[tid] = track
            track.last_seen, track.box, track.confidence = ts, tuple(box), float(confidence)
            track.anchors.append(anchor_point(box))
            width, height = box[2] - box[0], box[3] - box[1]
            track.aspects.append(float(height / width) if width > 0 else 0.0)
            seen.append(track)
        for tid in [
            t
            for t, tr in self.tracks.items()
            if (ts - tr.last_seen).total_seconds() > self.lost_after_s
        ]:
            del self.tracks[tid]
        return seen
