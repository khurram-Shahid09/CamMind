"""RTSP intake (docs/07-video-pipeline.md, "1 · Intake").

``StreamReader`` reads a camera's restream from go2rtc (or a file, for evals and the CLI),
keeps one frame per sample tick, and reconnects with backoff when the stream drops.
Frames come out as BGR NumPy arrays with a wall-clock UTC timestamp.
"""

import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import av
import numpy as np

log = logging.getLogger(__name__)
BACKOFF_S = (1, 2, 5, 10, 30, 60)
NO_FRAME_TIMEOUT_S = 10


@dataclass
class Frame:
    camera_id: str
    ts: datetime  # wall clock, UTC
    image: np.ndarray  # BGR, H x W x 3
    index: int  # sampled frame number since the reader started


@dataclass
class Health:
    state: str = "connecting"  # connecting | online | reconnecting | ended
    decoded: int = 0
    sampled: int = 0
    reconnects: int = 0
    last_frame_at: datetime | None = None
    error: str = ""
    started: float = field(default_factory=time.monotonic)

    def fps(self, count: int) -> float:
        elapsed = time.monotonic() - self.started
        return round(count / elapsed, 2) if elapsed > 0 else 0.0


class StreamReader:
    """Iterate sampled frames. Live sources (rtsp://) reconnect forever; files end.

    ``realtime=False`` (files only) reads as fast as decoding allows and stamps frames with
    the file's own clock starting at ``start``, so evals run faster than real time.
    """

    def __init__(
        self,
        camera_id: str,
        source: str,
        sample_fps: float = 5.0,
        *,
        realtime: bool = True,
        start: datetime | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.camera_id = camera_id
        self.source = source
        self.interval = 1.0 / sample_fps
        self.live = source.startswith(("rtsp://", "rtsps://"))
        self.realtime = realtime or self.live
        self.start = start or datetime.now(UTC)
        self.health = Health()
        self._sleep = sleep
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def __iter__(self) -> Iterator[Frame]:
        attempt = 0
        index = 0
        while not self._stop:
            try:
                for frame in self._read(index):
                    attempt = 0
                    index = frame.index + 1
                    yield frame
                    if self._stop:
                        return
                if not self.live:
                    self.health.state = "ended"
                    return
                raise ConnectionError("stream ended")
            except (av.error.FFmpegError, ConnectionError, OSError) as exc:
                if not self.live:
                    self.health.state, self.health.error = "ended", str(exc)
                    log.warning("%s: %s", self.camera_id, exc)
                    return
                wait = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
                attempt += 1
                self.health.state, self.health.error = "reconnecting", str(exc)[:200]
                self.health.reconnects += 1
                log.warning("%s: %s; reconnecting in %ss", self.camera_id, exc, wait)
                self._sleep(wait)

    def _options(self) -> dict[str, str]:
        if not self.live:
            return {}
        # TCP survives Wi-Fi and NAT; the timeout (microseconds) catches silent cameras.
        return {"rtsp_transport": "tcp", "timeout": str(NO_FRAME_TIMEOUT_S * 1_000_000)}

    def _read(self, first_index: int) -> Iterator[Frame]:
        with av.open(self.source, options=self._options(), timeout=NO_FRAME_TIMEOUT_S) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            self.health.state, self.health.error = "online", ""
            connected = datetime.now(UTC)
            next_tick: float | None = None
            index = first_index
            pace_origin = time.monotonic()
            for packet_frame in container.decode(stream):
                self.health.decoded += 1
                pts = (
                    float(packet_frame.pts * stream.time_base)
                    if packet_frame.pts is not None and stream.time_base is not None
                    else self.health.decoded / float(stream.average_rate or 25)
                )
                if next_tick is None:
                    next_tick = pts
                if pts + 1e-6 < next_tick:
                    continue  # between sample ticks: dropped without converting
                next_tick += self.interval
                if self.live:
                    ts = datetime.now(UTC)
                else:
                    base = self.start if not self.realtime else connected
                    ts = base + timedelta(seconds=pts)
                    if self.realtime:  # play a file at its own speed (CLI preview)
                        delay = pts - (time.monotonic() - pace_origin)
                        if delay > 0:
                            self._sleep(delay)
                image = packet_frame.to_ndarray(format="bgr24")
                self.health.sampled += 1
                self.health.last_frame_at = ts
                yield Frame(self.camera_id, ts, image, index)
                index += 1
                if self._stop:
                    return
