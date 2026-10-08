"""Vision worker <-> core (docs/12-api-spec.md, "Internal"; docs/08, "Event reporting").

The worker authenticates with ``Authorization: Worker <WORKER_TOKEN>``. It only reports
facts (an event started, an event ended); the core owns states and runs the actions.
"""

import base64
import binascii
import hmac
import json
import logging
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpRequest, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from cameras.models import Camera, Zone
from common.storage import StorageError, storage
from rules.models import RuleStatus, RuleVersion

from .models import Event, EventState
from .tasks import run_actions

log = logging.getLogger(__name__)


def _authorized(request: HttpRequest) -> bool:
    expected = settings.WORKER_TOKEN
    given = request.headers.get("Authorization", "")
    return bool(expected) and hmac.compare_digest(given, f"Worker {expected}")


def _deny() -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "not_authenticated", "message": "Worker token required."}}, status=401
    )


@require_http_methods(["GET"])
def config(request: HttpRequest) -> JsonResponse:
    """Enabled cameras, their zones, and the current version of every active rule."""
    if not _authorized(request):
        return _deny()
    cameras = list(Camera.objects.filter(enabled=True).select_related("site"))
    zones = Zone.objects.filter(camera__in=cameras)
    versions = RuleVersion.objects.filter(
        rule__status=RuleStatus.ACTIVE, rule__current_version_id=F("id")
    ).select_related("rule__site")
    payload = {
        "cameras": [
            {
                "id": c.id,
                "name": c.name,
                "site_id": c.site_id,
                "timezone": c.site.timezone,
                "detect_fps": c.detect_fps,
            }
            for c in cameras
        ],
        "zones": [
            {
                "id": z.id,
                "camera_id": z.camera_id,
                "name": z.name,
                "kind": z.kind,
                "points": z.points,
                "in_side": z.in_side,
            }
            for z in zones
        ],
        "rules": [
            {
                "id": v.id,
                "rule_id": v.rule_id,
                "name": v.rule.name,
                "timezone": v.rule.site.timezone,
                "spec": v.spec,
            }
            for v in versions
        ],
    }
    return JsonResponse(payload)


def _when(value: str) -> datetime:
    parsed = parse_datetime(value or "")
    if parsed is None:
        raise ValueError("bad timestamp")
    return parsed


@csrf_exempt
@require_http_methods(["POST"])
def report(request: HttpRequest) -> JsonResponse:
    """``{"kind": "start" | "end", "key", "rule_id", "camera_id", "ts", ...}``; idempotent by key."""
    if not _authorized(request):
        return _deny()
    try:
        data = json.loads(request.body)
        kind, key, ts = data["kind"], str(data["key"])[:200], _when(data["ts"])
    except (ValueError, KeyError, TypeError):
        return JsonResponse(
            {"error": {"code": "bad_request", "message": "Malformed event."}}, status=400
        )

    if kind == "end":
        updated = Event.objects.filter(idempotency_key=key, t_end__isnull=True).update(
            t_end=ts, close_reason=str(data.get("close_reason", ""))[:20]
        )
        return JsonResponse({"ok": True, "updated": updated})

    existing = Event.objects.filter(idempotency_key=key).first()
    if existing:
        return JsonResponse({"ok": True, "id": existing.id, "duplicate": True})
    version = RuleVersion.objects.filter(pk=data.get("rule_id")).select_related("rule").first()
    camera = Camera.objects.filter(pk=data.get("camera_id")).first()
    if version is None or camera is None or version.org_id != camera.org_id:
        return JsonResponse(
            {"error": {"code": "unknown_rule_or_camera", "message": "Unknown rule or camera."}},
            status=404,
        )

    needs_verify = bool(version.spec.get("verify"))
    event = Event(
        org_id=camera.org_id,
        site_id=camera.site_id,
        camera=camera,
        rule_version=version,
        idempotency_key=key,
        track_id=data.get("track_id"),
        state=EventState.VERIFYING if needs_verify else EventState.CONFIRMED,
        severity=version.spec.get("severity", "warning"),
        t_start=ts,
        reason=str(data.get("reason", ""))[:300],
        detections=data.get("objects", [])[:20],
    )
    for field, name in (("snapshot_jpeg_b64", "snapshot"), ("crop_jpeg_b64", "crop")):
        if data.get(field):
            try:
                jpeg = base64.b64decode(data[field], validate=True)
                media_key = f"{camera.org_id}/events/{event.id}/{name}.jpg"
                storage().put(media_key, jpeg, "image/jpeg")
                setattr(event, f"{name}_key", media_key)
            except (binascii.Error, StorageError) as exc:
                log.warning("event %s: %s not stored: %s", event.id, name, exc)
    try:
        with transaction.atomic():
            event.save()
    except IntegrityError:  # the same key raced in from a resend
        return JsonResponse({"ok": True, "duplicate": True})
    transaction.on_commit(lambda: run_actions.delay(event.id))
    return JsonResponse({"ok": True, "id": event.id, "state": event.state}, status=201)
