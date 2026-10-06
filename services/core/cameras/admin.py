"""Admin for back-office fixes (docs/03): add a camera by URL, check it, see its snapshot."""

from django import forms
from django.contrib import admin, messages
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from common.storage import StorageError

from . import rtsp, service
from .go2rtc import Go2rtcError
from .models import Camera


class CameraAdminForm(forms.ModelForm):
    rtsp_main = forms.CharField(
        label="Main stream URL",
        required=False,
        widget=forms.TextInput(attrs={"size": 80, "autocomplete": "off"}),
        help_text="rtsp://user:password@192.168.1.20:554/... Leave empty to keep the current one.",
    )
    rtsp_sub = forms.CharField(
        label="Sub stream URL",
        required=False,
        widget=forms.TextInput(attrs={"size": 80, "autocomplete": "off"}),
        help_text="Optional, lower resolution: used for detection. Leave empty to keep it.",
    )

    class Meta:
        model = Camera
        fields = ["site", "name", "detect_fps", "cloud_ai_allowed", "enabled"]

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        main, sub = cleaned.get("rtsp_main", "").strip(), cleaned.get("rtsp_sub", "").strip()
        if not main and not self.instance.rtsp_main_enc:
            self.add_error("rtsp_main", "A new camera needs its stream URL.")
            return cleaned
        if main or sub:
            for name, value in (("rtsp_main", main), ("rtsp_sub", sub)):
                if value:
                    try:
                        rtsp.parse(value)
                    except rtsp.CameraUrlError as exc:
                        self.add_error(name, exc.message)
            if self.errors:
                return cleaned
            main = main or self.instance.main_url
            sub = sub or self.instance.sub_url
            result = service.check_urls(main, sub)
            if not result.ok:
                field = "rtsp_sub" if result.stream == "sub" else "rtsp_main"
                self.add_error(field, f"{result.message} ({result.error_code})")
            cleaned["_urls"], cleaned["_check"] = (main, sub), result
        return cleaned


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    form = CameraAdminForm
    list_display = ("name", "site", "org", "enabled", "check_status", "snapshot_at", "thumbnail")
    list_filter = ("enabled", "check_status", "site__org")
    search_fields = ("name", "site__name")
    readonly_fields = (
        "id",
        "org",
        "main_url_masked",
        "sub_url_masked",
        "stream_meta",
        "check_status",
        "check_error",
        "checked_at",
        "snapshot_at",
        "snapshot",
    )
    fieldsets = (
        (None, {"fields": ("id", "org", "site", "name", "enabled")}),
        (
            "Streams",
            {"fields": ("rtsp_main", "main_url_masked", "rtsp_sub", "sub_url_masked")},
        ),
        ("Processing", {"fields": ("detect_fps", "cloud_ai_allowed")}),
        (
            "Status",
            {
                "fields": (
                    "check_status",
                    "check_error",
                    "checked_at",
                    "stream_meta",
                    "snapshot_at",
                    "snapshot",
                )
            },
        ),
    )
    actions = ["check_and_snapshot"]

    def save_model(self, request: HttpRequest, obj: Camera, form, change: bool) -> None:
        urls = form.cleaned_data.get("_urls")
        if urls:
            obj.set_urls(*urls)
            service.record_check(obj, form.cleaned_data["_check"])
            for warning in form.cleaned_data["_check"].warnings:
                messages.warning(request, warning)
        super().save_model(request, obj, form, change)
        if urls:
            self._snapshot(request, obj)

    def _snapshot(self, request: HttpRequest, camera: Camera) -> bool:
        try:
            service.refresh_snapshot(camera)
        except (Go2rtcError, StorageError) as exc:
            messages.warning(request, f"{camera.name}: no snapshot yet ({exc}).")
            return False
        return True

    @admin.action(description="Check connection and refresh snapshot")
    def check_and_snapshot(self, request: HttpRequest, queryset) -> None:
        for camera in queryset.select_related("site"):
            result = service.check_urls(camera.main_url, camera.sub_url)
            service.record_check(camera, result)
            camera.save(update_fields=["check_status", "check_error", "checked_at", "stream_meta"])
            if not result.ok:
                messages.error(request, f"{camera.name}: {result.message}")
            elif self._snapshot(request, camera):
                messages.success(request, f"{camera.name}: OK ({result.codec}).")

    # --- snapshot image, served only to admin users ---

    def get_urls(self):
        view = self.admin_site.admin_view(self.snapshot_view)
        return [
            path("<str:object_id>/snapshot.jpg", view, name="cameras_camera_snapshot"),
            *super().get_urls(),
        ]

    def snapshot_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        camera = self.get_object(request, object_id)
        jpeg = service.stored_snapshot(camera) if camera else None
        if jpeg is None:
            raise Http404("No snapshot yet.")
        response = HttpResponse(jpeg, content_type="image/jpeg")
        response["Cache-Control"] = "private, no-store"
        return response

    def _img(self, camera: Camera, width: int) -> str:
        if not camera.snapshot_key:
            return "–"
        url = reverse("admin:cameras_camera_snapshot", args=[camera.pk])
        stamp = int(camera.snapshot_at.timestamp()) if camera.snapshot_at else 0
        return format_html(
            '<img src="{}?t={}" width="{}" style="border-radius:4px" alt="">', url, stamp, width
        )

    @admin.display(description="Snapshot")
    def snapshot(self, camera: Camera) -> str:
        return self._img(camera, 640)

    @admin.display(description="")
    def thumbnail(self, camera: Camera) -> str:
        return self._img(camera, 120)

    @admin.display(description="Main stream")
    def main_url_masked(self, camera: Camera) -> str:
        return camera.main_url_masked or "–"

    @admin.display(description="Sub stream")
    def sub_url_masked(self, camera: Camera) -> str:
        return camera.sub_url_masked or "–"
