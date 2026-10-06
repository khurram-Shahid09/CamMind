"""Camera operations shared by the API, the admin and commands."""

import contextlib
import io
import logging
import secrets
from dataclasses import dataclass, field

from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from common.storage import storage

from . import rtsp
from .go2rtc import Go2rtc, Go2rtcError
from .models import Camera, CheckStatus

log = logging.getLogger(__name__)
MANAGED_PREFIX = "cam_"  # go2rtc streams the core owns; anything else is left alone
PREVIEW_PREFIX = "preview_"


# --- go2rtc streams ---


def stream_sources(camera: Camera) -> dict[str, str]:
    """``<id>`` feeds detection (sub stream when there is one); ``<id>_hd`` feeds clips."""
    main = camera.main_url
    return {camera.id: camera.sub_url or main, f"{camera.id}_hd": main}


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


def sync_go2rtc(client: Go2rtc | None = None) -> SyncReport:
    """Make go2rtc's streams match the enabled cameras. Safe to run any time."""
    client = client or Go2rtc()
    wanted: dict[str, str] = {}
    for camera in Camera.objects.filter(enabled=True).select_related("site"):
        wanted.update(stream_sources(camera))
    current = client.streams()
    report = SyncReport()
    for name, src in wanted.items():
        if name not in current:
            client.put_stream(name, src)
            report.added.append(name)
        elif current[name] != [src]:
            client.put_stream(name, src)
            report.updated.append(name)
    for name in current:
        stale_camera = name.startswith(MANAGED_PREFIX) and name not in wanted
        if stale_camera or name.startswith(PREVIEW_PREFIX):
            client.delete_stream(name)
            report.removed.append(name)
    return report


# --- connection checks ---


@dataclass
class CheckResult:
    ok: bool
    error_code: str = ""
    message: str = ""
    codec: str = ""
    fps: float | None = None
    warnings: list[str] = field(default_factory=list)
    stream: str = "main"  # which URL failed


def check_urls(main: str, sub: str = "") -> CheckResult:
    """Probe the main stream and, when given, the sub stream (docs/02, US-1)."""
    result = rtsp.probe(main)
    if not result.ok:
        return CheckResult(False, result.error_code, result.message, warnings=result.warnings)
    warnings = list(result.warnings)
    if sub:
        sub_result = rtsp.probe(sub)
        if not sub_result.ok:
            return CheckResult(
                False,
                sub_result.error_code,
                f"Sub stream: {sub_result.message}",
                warnings=warnings,
                stream="sub",
            )
        warnings += [w for w in sub_result.warnings if w not in warnings]
    return CheckResult(True, codec=result.codec, fps=result.fps, warnings=warnings)


def record_check(camera: Camera, result: CheckResult) -> None:
    camera.check_status = CheckStatus.OK if result.ok else CheckStatus.FAILED
    camera.check_error = result.error_code
    camera.checked_at = timezone.now()
    if result.ok:
        camera.stream_meta = {
            **camera.stream_meta,
            "codec": result.codec,
            "fps": result.fps,
        }


# --- snapshots ---


def image_size(jpeg: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(io.BytesIO(jpeg)) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None


def snapshot_key(camera: Camera) -> str:
    return f"{camera.org_id}/cameras/{camera.id}/snapshot.jpg"


def refresh_snapshot(camera: Camera, client: Go2rtc | None = None) -> bytes:
    """A fresh frame from go2rtc, stored as the camera's snapshot. Raises Go2rtcError."""
    client = client or Go2rtc()
    for name, src in stream_sources(camera).items():
        client.put_stream(name, src)  # idempotent; the camera may be new to go2rtc
    jpeg = client.frame_jpeg(f"{camera.id}_hd")
    key = snapshot_key(camera)
    storage().put(key, jpeg, "image/jpeg")
    size = image_size(jpeg)
    camera.snapshot_key = key
    camera.snapshot_at = timezone.now()
    if size:
        camera.stream_meta = {**camera.stream_meta, "width": size[0], "height": size[1]}
    camera.save(update_fields=["snapshot_key", "snapshot_at", "stream_meta", "updated_at"])
    return jpeg


def stored_snapshot(camera: Camera) -> bytes | None:
    return storage().get(camera.snapshot_key) if camera.snapshot_key else None


def preview_snapshot(url: str, client: Go2rtc | None = None) -> bytes | None:
    """A frame from a camera that isn't saved yet, through a short-lived go2rtc stream."""
    client = client or Go2rtc()
    name = f"{PREVIEW_PREFIX}{secrets.token_hex(6)}"
    try:
        client.put_stream(name, url)
        return client.frame_jpeg(name)
    except Go2rtcError as exc:
        log.info("preview snapshot failed: %s", exc)
        return None
    finally:
        with contextlib.suppress(Go2rtcError):  # else the next sync removes it
            client.delete_stream(name)
