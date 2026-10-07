"""One camera's per-frame path: motion gate -> detector -> tracker (docs/07, "Stages").

The detector only runs when something moves in a watched area, or while tracks are alive
(plus a short grace period), so a person standing still keeps being tracked.
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from .detect import Detections, Detector
from .ingest import Frame
from .motion import MotionGate, MotionResult
from .track import Track, Tracker

GRACE_S = 2.0


@dataclass
class Step:
    frame: Frame
    motion: MotionResult
    detected: bool
    detections: Detections
    tracks: list[Track] = field(default_factory=list)


@dataclass
class Stats:
    frames: int = 0
    detected: int = 0
    detector_ms: list[float] = field(default_factory=list)

    @property
    def gate_pass_rate(self) -> float:
        return self.detected / self.frames if self.frames else 0.0

    def detector_ms_p(self, q: float) -> float:
        return float(np.percentile(self.detector_ms, q)) if self.detector_ms else 0.0


class CameraPipeline:
    def __init__(
        self,
        detector: Detector,
        fps: float = 5.0,
        watched_mask: np.ndarray | None = None,
        *,
        always_detect: bool = False,
    ) -> None:
        self.detector = detector
        self.gate = MotionGate(watched_mask)
        self.tracker = Tracker(fps)
        self.always_detect = always_detect
        self.stats = Stats()
        self._open_until: datetime | None = None

    def _gate_open(self, motion: MotionResult, ts: datetime) -> bool:
        if self.always_detect or motion.moving or self.tracker.tracks:
            return True
        return self._open_until is not None and ts <= self._open_until

    def process(self, frame: Frame) -> Step:
        self.stats.frames += 1
        motion = self.gate.update(frame.image)
        if not self._gate_open(motion, frame.ts):
            # Nothing moving and nothing tracked: still age out old tracks.
            tracks = (
                self.tracker.update(Detections.empty(), frame.ts) if self.tracker.tracks else []
            )
            return Step(frame, motion, False, Detections.empty(), tracks)
        detections = self.detector.detect([frame.image])[0]
        self.stats.detected += 1
        self.stats.detector_ms.append(self.detector.last_ms)
        tracks = self.tracker.update(detections, frame.ts)
        if tracks:
            from datetime import timedelta

            self._open_until = frame.ts + timedelta(seconds=GRACE_S)
        return Step(frame, motion, True, detections, tracks)
