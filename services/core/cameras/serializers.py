from rest_framework import serializers

from accounts.models import Site

from . import rtsp
from .models import Camera


def _url(value: str) -> str:
    try:
        rtsp.parse(value)
    except rtsp.CameraUrlError as exc:
        raise serializers.ValidationError(exc.message) from exc
    return value.strip()


class CameraSerializer(serializers.ModelSerializer):
    site_id = serializers.PrimaryKeyRelatedField(source="site", queryset=Site.objects.none())
    rtsp_main = serializers.CharField(write_only=True, max_length=1000)
    rtsp_sub = serializers.CharField(
        write_only=True, max_length=1000, required=False, allow_blank=True
    )
    rtsp_main_masked = serializers.CharField(source="main_url_masked", read_only=True)
    rtsp_sub_masked = serializers.CharField(source="sub_url_masked", read_only=True)

    class Meta:
        model = Camera
        fields = [
            "id",
            "site_id",
            "name",
            "rtsp_main",
            "rtsp_sub",
            "rtsp_main_masked",
            "rtsp_sub_masked",
            "detect_fps",
            "cloud_ai_allowed",
            "enabled",
            "stream_meta",
            "check_status",
            "check_error",
            "checked_at",
            "snapshot_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "stream_meta",
            "check_status",
            "check_error",
            "checked_at",
            "snapshot_at",
            "created_at",
        ]
        validators: list = []  # the (site, name) uniqueness check is done in the view

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        sites = self.context.get("sites")
        if sites is not None:
            self.fields["site_id"].queryset = sites  # type: ignore[attr-defined]

    def validate_rtsp_main(self, value: str) -> str:
        return _url(value)

    def validate_rtsp_sub(self, value: str) -> str:
        return _url(value) if value.strip() else ""


class CameraTestRequestSerializer(serializers.Serializer):
    rtsp_url = serializers.CharField(max_length=1000)


class CameraTestResultSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    error_code = serializers.CharField(allow_blank=True)
    message = serializers.CharField(allow_blank=True)
    codec = serializers.CharField(allow_blank=True)
    fps = serializers.FloatField(allow_null=True)
    width = serializers.IntegerField(allow_null=True)
    height = serializers.IntegerField(allow_null=True)
    warnings = serializers.ListField(child=serializers.CharField())
    snapshot_jpeg_base64 = serializers.CharField(allow_null=True)
