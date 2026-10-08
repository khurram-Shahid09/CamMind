"""The long-running worker (docs/03-architecture.md, "Vision worker modules").

- Loads cameras, zones and active rules from the core (``/internal/config``), and reloads
  them every 30 s, so a rule activated in the dashboard starts within half a minute.
- One thread per camera: restream -> motion -> detection -> tracking -> rule engine.
- Events go into a SQLite outbox first and are sent by a separate thread, so a core outage
  loses nothing; the idempotency key makes resends safe.
"""

import base64
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

import cv2
import httpx
import numpy as np
from cammind_spec import RuleSpec, WhereZone

from .annotate import annotate
from .detect import Detector
from .engine import CompiledRule, Engine, EngineEvent
from .geometry import Line, Polygon
from .ingest import StreamReader
from .pipeline import CameraPipeline

log = logging.getLogger(__name__)
RELOAD_S = 30


class CoreClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.http = httpx.Client(
            base_url=base_url, timeout=15, headers={"Authorization": f"Worker {token}"}
        )

    def config(self) -> dict:
        response = self.http.get("/internal/config")
        response.raise_for_status()
        return response.json()

    def send(self, payload: dict) -> None:
        response = self.http.post("/internal/events", json=payload)
        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code >= 400:
            log.warning("core refused event %s: %s", payload.get("key"), response.text[:200])


class Outbox:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS outbox (id INTEGER PRIMARY KEY, body TEXT)")
        self.lock = threading.Lock()

    def put(self, payload: dict) -> None:
        with self.lock:
            self.db.execute("INSERT INTO outbox (body) VALUES (?)", (json.dumps(payload),))
            self.db.commit()

    def pending(self, limit: int = 20) -> list[tuple[int, dict]]:
        with self.lock:
            rows = self.db.execute("SELECT id, body FROM outbox ORDER BY id LIMIT ?", (limit,))
            return [(row[0], json.loads(row[1])) for row in rows.fetchall()]

    def done(self, row_id: int) -> None:
        with self.lock:
            self.db.execute("DELETE FROM outbox WHERE id = ?", (row_id,))
            self.db.commit()

    def drain_forever(self, client: CoreClient, stop: threading.Event) -> None:
        delay = 1.0
        while not stop.is_set():
            rows = self.pending()
            try:
                for row_id, payload in rows:
                    client.send(payload)
                    self.done(row_id)
                delay = 1.0
            except httpx.HTTPError as exc:
                log.warning(
                    "core unreachable (%s); %d events waiting", exc.__class__.__name__, len(rows)
                )
                delay = min(delay * 2, 30)
            stop.wait(delay if rows else 0.5)


def compile_rules(config: dict, camera_id: str) -> list[CompiledRule]:
    zones = {z["id"]: z for z in config["zones"] if z["camera_id"] == camera_id}
    rules = []
    for raw in config["rules"]:
        spec = RuleSpec.model_validate(raw["spec"])
        if camera_id not in spec.camera_ids:
            continue
        polygons = {
            zid: Polygon(zid, [tuple(p) for p in z["points"]])
            for zid, z in zones.items()
            if z["kind"] == "polygon"
        }
        lines = {
            zid: Line(zid, tuple(z["points"][0]), tuple(z["points"][1]), z.get("in_side", "right"))
            for zid, z in zones.items()
            if z["kind"] == "line"
        }
        names = {zid: z["name"] for zid, z in zones.items()}
        rules.append(CompiledRule(raw["id"], spec, polygons, lines, names, raw["timezone"]))
    return rules


def crop(image: np.ndarray, box: list[float], pad: float = 0.2) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = max(0, int(x1 - dx)), max(0, int(y1 - dy))
    x2, y2 = min(width, int(x2 + dx)), min(height, int(y2 + dy))
    return image[y1:y2, x1:x2]


def jpeg_b64(image: np.ndarray, longest: int = 1280) -> str:
    height, width = image.shape[:2]
    scale = min(1.0, longest / max(height, width))
    if scale < 1:
        image = cv2.resize(image, (round(width * scale), round(height * scale)))
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return base64.b64encode(buffer.tobytes()).decode() if ok else ""


def payload(event: EngineEvent, image: np.ndarray, rule: CompiledRule, tracks) -> dict:
    body = {
        "kind": event.kind,
        "key": event.key,
        "rule_id": event.rule_id,
        "camera_id": event.camera_id,
        "ts": event.ts.isoformat(),
        "track_id": event.track_id,
        "reason": event.reason,
        "objects": event.objects,
        "close_reason": event.close_reason,
    }
    if event.kind == "start":
        zones = []
        if isinstance(rule.spec.where, WhereZone):
            zones = [rule.zones[z] for z in rule.spec.where.zone_ids if z in rule.zones]
        involved = [t for t in tracks if t.id in {o["track_id"] for o in event.objects}]
        body["snapshot_jpeg_b64"] = jpeg_b64(annotate(image, involved or tracks, zones))
        if event.objects:
            body["crop_jpeg_b64"] = jpeg_b64(crop(image, event.objects[0]["box"]), 768)
    return body


class Worker:
    def __init__(
        self, client: CoreClient, restream: str, outbox: Outbox, sources: dict[str, str]
    ) -> None:
        self.client, self.restream, self.outbox, self.sources = client, restream, outbox, sources
        self.detector = Detector()
        self.detector_lock = threading.Lock()
        self.config: dict = {"cameras": [], "zones": [], "rules": []}
        self.stop = threading.Event()
        self.threads: dict[str, threading.Thread] = {}

    def camera_loop(self, camera: dict) -> None:
        camera_id = camera["id"]
        fps = float(camera.get("detect_fps", 5))
        source = self.sources.get(camera_id, f"{self.restream}/{camera_id}")
        reader = StreamReader(camera_id, source, fps, realtime=True)
        pipeline = CameraPipeline(_LockedDetector(self.detector, self.detector_lock), fps)  # type: ignore[arg-type]
        version = None
        engine = Engine([])
        rules: dict[str, CompiledRule] = {}
        for frame in reader:
            if self.stop.is_set():
                reader.stop()
                break
            if version is not self.config:  # reloaded
                version = self.config
                rules = {r.id: r for r in compile_rules(self.config, camera_id)}
                engine = Engine(list(rules.values()))
                log.info("%s: %d rules", camera["name"], len(rules))
            step = pipeline.process(frame)
            height, width = frame.image.shape[:2]
            alive = list(pipeline.tracker.tracks.values())
            for event in engine.update(camera_id, frame.ts, alive, width, height):
                log.info(
                    "%s %s: %s", camera["name"], event.kind, event.reason or event.close_reason
                )
                self.outbox.put(payload(event, frame.image, rules[event.rule_id], step.tracks))

    def run(self) -> None:
        threading.Thread(
            target=self.outbox.drain_forever, args=(self.client, self.stop), daemon=True
        ).start()
        while not self.stop.is_set():
            try:
                self.config = self.client.config()
            except httpx.HTTPError as exc:
                log.warning("config not loaded: %s", exc)
            watched = {c for r in self.config["rules"] for c in r["spec"]["camera_ids"]}
            for camera in self.config["cameras"]:
                if camera["id"] not in watched:
                    continue  # no active rule: don't spend CPU on it
                thread = self.threads.get(camera["id"])
                if thread is None or not thread.is_alive():
                    thread = threading.Thread(target=self.camera_loop, args=(camera,), daemon=True)
                    self.threads[camera["id"]] = thread
                    thread.start()
            self.stop.wait(RELOAD_S)


class _LockedDetector:
    """Cameras share one ONNX session; ONNX Runtime runs one batch at a time anyway."""

    def __init__(self, detector: Detector, lock: threading.Lock) -> None:
        self._detector, self._lock = detector, lock

    @property
    def last_ms(self) -> float:
        return self._detector.last_ms

    def detect(self, images):
        with self._lock:
            return self._detector.detect(images)


def run_forever(
    core: str, token: str, restream: str, sources: dict[str, str], data_dir: Path
) -> int:
    worker = Worker(CoreClient(core, token), restream, Outbox(data_dir / "outbox.sqlite"), sources)
    try:
        worker.run()
    except KeyboardInterrupt:
        worker.stop.set()
        time.sleep(0.5)
    return 0
