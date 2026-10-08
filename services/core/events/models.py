from django.db import models

from accounts.models import Site
from cameras.models import Camera
from common.ids import PrefixedIdField
from common.models import TimeStampedModel
from common.tenancy import OrgOwnedModel
from rules.models import RuleVersion


class EventState(models.TextChoices):
    """docs/03-architecture.md, "Event lifecycle"."""

    VERIFYING = "verifying"
    CONFIRMED = "confirmed"
    UNVERIFIED = "unverified"
    DISMISSED = "dismissed"


class Event(OrgOwnedModel, TimeStampedModel):
    id = PrefixedIdField(prefix="evt")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="+")
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="events")
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.CASCADE, related_name="events")
    idempotency_key = models.CharField(max_length=200, unique=True)
    track_id = models.IntegerField(null=True, blank=True)
    state = models.CharField(max_length=10, choices=EventState.choices)
    severity = models.CharField(max_length=8, default="warning")
    t_start = models.DateTimeField()
    t_end = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=300)
    detections = models.JSONField(default=list, blank=True)  # boxes at the start
    snapshot_key = models.CharField(max_length=200, blank=True)
    crop_key = models.CharField(max_length=200, blank=True)
    clip_key = models.CharField(max_length=200, blank=True)
    verification = models.JSONField(default=dict, blank=True)  # answer, confidence, reason, model
    feedback = models.CharField(max_length=12, blank=True)  # confirmed | false_alarm

    class Meta:
        db_table = "events"
        ordering = ["-t_start"]
        indexes = [models.Index(fields=["org", "-t_start"], name="events_org_start_idx")]
