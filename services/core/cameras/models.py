from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.models import Site
from common.crypto import decrypt, encrypt
from common.ids import PrefixedIdField
from common.models import TimeStampedModel
from common.tenancy import OrgOwnedModel

from . import rtsp


class CheckStatus(models.TextChoices):
    UNKNOWN = "unknown"
    OK = "ok"
    FAILED = "failed"


class Camera(OrgOwnedModel, TimeStampedModel):
    """An RTSP camera on a site (docs/11-data-model.md, "Sites and cameras").

    Stream URLs carry the camera's password, so they're stored encrypted and only ever
    shown masked (``rtsp://admin:•••@192.168.1.20/...``). The sub stream, when there is one,
    feeds detection; the main stream feeds clips and verification crops.
    """

    id = PrefixedIdField(prefix="cam")
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="cameras")
    name = models.CharField(max_length=120)
    rtsp_main_enc = models.TextField()
    rtsp_sub_enc = models.TextField(blank=True)
    # codec, fps, width, height: from the last connection check and snapshot.
    stream_meta = models.JSONField(default=dict, blank=True)
    detect_fps = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(15)]
    )
    # Off by default: no image of this camera leaves the site (docs/14, ADR-0003).
    cloud_ai_allowed = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    check_status = models.CharField(
        max_length=10, choices=CheckStatus.choices, default=CheckStatus.UNKNOWN
    )
    check_error = models.CharField(max_length=32, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    snapshot_key = models.CharField(max_length=200, blank=True)
    snapshot_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "cameras"
        constraints = [
            models.UniqueConstraint(fields=["site", "name"], name="cameras_site_name_unique")
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.org_id = self.site.org_id  # a camera always belongs to its site's org
        super().save(*args, **kwargs)

    # --- stream URLs ---

    def set_urls(self, main: str, sub: str = "") -> None:
        if not self.site_id:
            raise ValueError("set the site before the stream URLs")
        org_id = self.site.org_id
        self.rtsp_main_enc = encrypt(main, org_id=org_id)
        self.rtsp_sub_enc = encrypt(sub, org_id=org_id) if sub else ""

    @property
    def main_url(self) -> str:
        return decrypt(self.rtsp_main_enc, org_id=self.org_id) if self.rtsp_main_enc else ""

    @property
    def sub_url(self) -> str:
        return decrypt(self.rtsp_sub_enc, org_id=self.org_id) if self.rtsp_sub_enc else ""

    @property
    def main_url_masked(self) -> str:
        return rtsp.mask(self.main_url) if self.rtsp_main_enc else ""

    @property
    def sub_url_masked(self) -> str:
        return rtsp.mask(self.sub_url) if self.rtsp_sub_enc else ""


class Zone(OrgOwnedModel, TimeStampedModel):
    """An area (polygon) or a line drawn on a camera; points are normalised 0-1."""

    id = PrefixedIdField(prefix="zn")
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=8, choices=[("polygon", "Area"), ("line", "Line")])
    points = models.JSONField()  # [[x, y], ...]
    in_side = models.CharField(max_length=5, default="right")  # lines: "left" | "right"

    class Meta:
        db_table = "zones"
        constraints = [
            models.UniqueConstraint(fields=["camera", "name"], name="zones_camera_name_unique")
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.org_id = self.camera.org_id
        super().save(*args, **kwargs)
