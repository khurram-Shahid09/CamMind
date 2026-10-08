from typing import cast

from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import Role
from accounts.views_base import OrgScopedViewMixin
from common.storage import storage

from .models import Event

REVIEWERS = frozenset({Role.OWNER.value, Role.ADMIN.value, Role.OPERATOR.value})


class EventSerializer(serializers.ModelSerializer):
    camera = serializers.CharField(source="camera.name", read_only=True)
    rule = serializers.CharField(source="rule_version.rule.name", read_only=True)
    rule_id = serializers.CharField(source="rule_version.rule_id", read_only=True)
    summary = serializers.CharField(source="rule_version.summary", read_only=True)
    has_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "camera_id", "camera", "site_id", "rule_id", "rule", "summary", "track_id",
            "state", "severity", "t_start", "t_end", "close_reason", "reason", "detections",
            "verification", "feedback", "has_snapshot",
        ]  # fmt: skip
        read_only_fields = fields

    def get_has_snapshot(self, event: Event) -> bool:
        return bool(event.snapshot_key)


class EventListView(OrgScopedViewMixin, generics.ListAPIView):
    queryset = Event.objects.select_related("camera", "rule_version__rule")
    serializer_class = EventSerializer
    site_field = "site"

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-t_start", "-id")
        params = self.request.query_params
        if params.get("camera_id"):
            queryset = queryset.filter(camera_id=params["camera_id"])
        if params.get("rule_id"):
            queryset = queryset.filter(rule_version__rule_id=params["rule_id"])
        if params.get("include_dismissed") not in ("1", "true"):
            queryset = queryset.exclude(state="dismissed")
        return queryset

    def list(self, request: Request, *args, **kwargs) -> Response:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        data = EventSerializer(self.get_queryset()[:limit], many=True).data
        return Response({"results": data})


class EventDetailView(OrgScopedViewMixin, generics.RetrieveUpdateAPIView):
    queryset = Event.objects.select_related("camera", "rule_version__rule")
    serializer_class = EventSerializer
    site_field = "site"
    lookup_url_kwarg = "event_id"
    method_roles = {"PATCH": REVIEWERS}
    http_method_names = ["get", "patch", "head", "options"]

    def patch(self, request: Request, *args, **kwargs) -> Response:
        event = cast(Event, self.get_object())
        verdict = dict(request.data).get("feedback")
        if verdict not in ("confirmed", "false_alarm"):
            raise serializers.ValidationError({"feedback": "confirmed or false_alarm"})
        event.feedback = verdict
        event.save(update_fields=["feedback", "updated_at"])
        return Response(EventSerializer(event).data)


class EventImageView(OrgScopedViewMixin, generics.GenericAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    site_field = "site"
    lookup_url_kwarg = "event_id"

    @extend_schema(responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    def get(self, request: Request, *args, **kwargs) -> HttpResponse:
        event = cast(Event, self.get_object())
        key = event.crop_key if kwargs.get("kind") == "crop" else event.snapshot_key
        jpeg = storage().get(key) if key else None
        if jpeg is None:
            raise Http404
        response = HttpResponse(jpeg, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        return response
