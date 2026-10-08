import base64
import logging
from typing import cast

from django.db import models, transaction
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from accounts.models import MANAGERS, Site
from accounts.views_base import OrgScopedViewMixin
from audit.service import record
from common.exceptions import ApiError
from common.storage import StorageError, storage

from . import service
from .go2rtc import Go2rtcError
from .models import Camera, Zone
from .serializers import (
    CameraSerializer,
    CameraTestRequestSerializer,
    CameraTestResultSerializer,
    ZoneSerializer,
)

log = logging.getLogger(__name__)


def _check_or_fail(main: str, sub: str) -> service.CheckResult:
    result = service.check_urls(main, sub)
    if not result.ok:
        raise ApiError(
            "camera_check_failed",
            result.message,
            details={"check": {"error_code": result.error_code, "stream": result.stream}},
        )
    return result


def _try_snapshot(camera: Camera) -> None:
    """Best effort: a camera is saved even when go2rtc can't get a frame right now."""
    try:
        service.refresh_snapshot(camera)
    except (Go2rtcError, StorageError) as exc:
        log.info("snapshot for %s failed: %s", camera.id, exc)


class CameraTestView(OrgScopedViewMixin, APIView):
    """Check a URL before saving it: reachable, password right, H.264/H.265, a frame."""

    method_roles = {"POST": MANAGERS}

    @extend_schema(request=CameraTestRequestSerializer, responses={200: CameraTestResultSerializer})
    def post(self, request: Request) -> Response:
        data = CameraTestRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        url = data.validated_data["rtsp_url"]
        result = service.check_urls(url)
        jpeg = service.preview_snapshot(url) if result.ok else None
        size = service.image_size(jpeg) if jpeg else None
        body = {
            "ok": result.ok,
            "error_code": result.error_code,
            "message": result.message,
            "codec": result.codec,
            "fps": result.fps,
            "width": size[0] if size else None,
            "height": size[1] if size else None,
            "warnings": result.warnings,
            "snapshot_jpeg_base64": base64.b64encode(jpeg).decode() if jpeg else None,
        }
        return Response(CameraTestResultSerializer(body).data)


class _CameraViewMixin(OrgScopedViewMixin):
    site_field = "site"

    def get_serializer_context(self):
        sites = Site.objects.for_org(self.org)
        allowed = self.membership.site_ids()
        if allowed is not None:
            sites = sites.filter(pk__in=allowed)
        return {**super().get_serializer_context(), "sites": sites}  # type: ignore[misc]

    def _ensure_unique_name(self, site: Site, name: str, exclude: str | None = None) -> None:
        clash = Camera.objects.for_org(self.org).filter(site=site, name=name)
        if exclude:
            clash = clash.exclude(pk=exclude)
        if clash.exists():
            raise ApiError(
                "camera_exists", "This site already has a camera with this name.", status_code=409
            )


class CameraListView(_CameraViewMixin, generics.ListCreateAPIView):
    queryset = Camera.objects.select_related("site")
    serializer_class = CameraSerializer
    method_roles = {"POST": MANAGERS}

    def perform_create(self, serializer: BaseSerializer) -> None:
        data = dict(serializer.validated_data)
        main, sub = data.pop("rtsp_main"), data.pop("rtsp_sub", "")
        self._ensure_unique_name(data["site"], data["name"])
        result = _check_or_fail(main, sub)
        with transaction.atomic():
            camera = Camera(**data)
            camera.set_urls(main, sub)
            service.record_check(camera, result)
            camera.save()
            record(
                "camera.created",
                org=self.org,
                request=self.request,
                entity=camera,
                metadata={"name": camera.name, "site_id": camera.site_id},
            )
        serializer.instance = camera
        _try_snapshot(camera)


class CameraDetailView(_CameraViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Camera.objects.select_related("site")
    serializer_class = CameraSerializer
    lookup_url_kwarg = "camera_id"
    method_roles = {"PATCH": MANAGERS, "DELETE": MANAGERS}
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_update(self, serializer: BaseSerializer) -> None:
        camera = cast(Camera, serializer.instance)
        data = dict(serializer.validated_data)
        site, name = data.get("site", camera.site), data.get("name", camera.name)
        self._ensure_unique_name(site, name, exclude=camera.pk)
        urls_changed = "rtsp_main" in data or "rtsp_sub" in data
        main = data.pop("rtsp_main", None) or camera.main_url
        sub = data.pop("rtsp_sub") if "rtsp_sub" in data else camera.sub_url
        changes = {key: str(getattr(value, "pk", value)) for key, value in data.items()}
        with transaction.atomic():
            for key, value in data.items():
                setattr(camera, key, value)
            if urls_changed:
                service.record_check(camera, _check_or_fail(main, sub))
                camera.set_urls(main, sub)
            camera.save()
            record(
                "camera.updated",
                org=self.org,
                request=self.request,
                entity=camera,
                metadata={**changes, "stream_urls_changed": urls_changed},
            )
        if urls_changed:
            _try_snapshot(camera)

    def perform_destroy(self, instance: Camera) -> None:
        with transaction.atomic():
            record(
                "camera.deleted",
                org=self.org,
                request=self.request,
                entity=instance,
                metadata={"name": instance.name, "site_id": instance.site_id},
            )
            key = instance.snapshot_key
            instance.delete()
        if key:
            try:
                storage().delete(key)
            except StorageError:
                log.warning("could not delete snapshot %s", key)


class CameraSnapshotView(_CameraViewMixin, generics.GenericAPIView):
    queryset = Camera.objects.select_related("site")
    serializer_class = CameraSerializer
    lookup_url_kwarg = "camera_id"

    @extend_schema(
        parameters=[
            OpenApiParameter("fresh", bool, description="Grab a new frame instead of the last one")
        ],
        responses={(200, "image/jpeg"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, *args, **kwargs) -> HttpResponse:
        camera = cast(Camera, self.get_object())
        fresh = request.query_params.get("fresh") in ("1", "true")
        try:
            jpeg = None if fresh else service.stored_snapshot(camera)
            if jpeg is None:
                jpeg = service.refresh_snapshot(camera)
        except Go2rtcError as exc:
            raise ApiError(
                "camera_unavailable",
                "Couldn't get a picture from this camera right now.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc
        except StorageError as exc:
            raise ApiError(
                "storage_unavailable", "Snapshot storage is unavailable.", status_code=503
            ) from exc
        response = HttpResponse(jpeg, content_type="image/jpeg")
        response["Cache-Control"] = "private, no-store"
        return response


class ZoneListView(OrgScopedViewMixin, generics.ListCreateAPIView):
    queryset = Zone.objects.select_related("camera")
    site_field = "camera__site"
    method_roles = {"POST": MANAGERS}
    pagination_class = None

    serializer_class = ZoneSerializer

    def get_queryset(self):
        return super().get_queryset().filter(camera_id=self.kwargs["camera_id"])

    def perform_create(self, serializer: BaseSerializer) -> None:
        camera = Camera.objects.for_org(self.org).filter(pk=self.kwargs["camera_id"]).first()
        if camera is None or not self.membership.can_access_site(camera.site_id):
            raise ApiError("camera_not_found", "No such camera.", status_code=404)
        if camera.zones.filter(name=serializer.validated_data["name"]).exists():
            raise ApiError(
                "zone_exists", "This camera already has a zone with this name.", status_code=409
            )
        zone = serializer.save(camera=camera)
        record(
            "zone.created",
            org=self.org,
            request=self.request,
            entity=zone,
            metadata={"name": zone.name},
        )


class ZoneDetailView(OrgScopedViewMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Zone.objects.select_related("camera")
    site_field = "camera__site"
    lookup_url_kwarg = "zone_id"
    method_roles = {"PATCH": MANAGERS, "DELETE": MANAGERS}
    http_method_names = ["get", "patch", "delete", "head", "options"]

    serializer_class = ZoneSerializer

    def perform_destroy(self, instance) -> None:
        from rules.models import RuleVersion

        using = RuleVersion.objects.for_org(self.org).filter(
            rule__current_version_id=models.F("id"), spec__icontains=instance.id
        )
        names = list(using.values_list("rule__name", flat=True))
        if names:
            raise ApiError(
                "zone_in_use", "Rules use this zone.", status_code=409, details={"rules": names}
            )
        record(
            "zone.deleted",
            org=self.org,
            request=self.request,
            entity=instance,
            metadata={"name": instance.name},
        )
        instance.delete()
