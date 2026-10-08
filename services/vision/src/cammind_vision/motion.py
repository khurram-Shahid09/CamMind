"""Motion gate (docs/07-video-pipeline.md, "2 · Motion gate").

Cheap enough to run on every sampled frame (~1 ms): a downscaled, blurred greyscale frame
compared with a running-average background. Only motion inside the watched areas counts,
so a swaying tree outside every zone can't wake the detector.
"""

from dataclasses import dataclass

import cv2
import numpy as np

WIDTH = 160
LIGHT_CHANGE_FRACTION = 0.6  # more of the frame than this changed at once: lights or IR switch


@dataclass
class MotionResult:
    moving: bool
    fraction: float  # of the watched area that changed
    reset: bool = False  # background reset after a global light change


class MotionGate:
    """``mask``: watched area as a float32/uint8 image of any size (non-zero = watched);
    ``None`` watches the whole frame."""

    def __init__(
        self,
        mask: np.ndarray | None = None,
        *,
        threshold: int = 25,
        min_fraction: float = 0.002,
        alpha: float = 0.05,
    ) -> None:
        self.threshold = threshold
        self.min_fraction = min_fraction
        self.alpha = alpha
        self._mask_src = mask
        self._mask: np.ndarray | None = None
        self._background: np.ndarray | None = None

    def _small(self, image: np.ndarray) -> np.ndarray:
        height = max(1, round(image.shape[0] * WIDTH / image.shape[1]))
        grey = cv2.cvtColor(cv2.resize(image, (WIDTH, height)), cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(grey, (5, 5), 0).astype(np.float32)

    def update(self, image: np.ndarray) -> MotionResult:
        small = self._small(image)
        if self._mask is None or self._mask.shape != small.shape:
            if self._mask_src is None:
                self._mask = np.ones(small.shape, dtype=bool)
            else:
                resized = cv2.resize(
                    self._mask_src.astype(np.uint8),
                    (small.shape[1], small.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
                self._mask = resized > 0
        if self._background is None:
            self._background = small
            return MotionResult(False, 0.0)

        diff = cv2.absdiff(small, self._background)
        raw = (diff > self.threshold).astype(np.uint8)
        changed = cv2.morphologyEx(raw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
        whole = float(changed.mean())
        if whole > LIGHT_CHANGE_FRACTION:
            self._background = small
            return MotionResult(False, whole, reset=True)
        cv2.accumulateWeighted(small, self._background, self.alpha)
        watched = int(self._mask.sum())
        fraction = float((changed & self._mask).sum()) / watched if watched else 0.0
        return MotionResult(fraction >= self.min_fraction, fraction)
