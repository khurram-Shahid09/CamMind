from django.db import models

from accounts.models import Site
from common.ids import PrefixedIdField
from common.models import TimeStampedModel
from common.tenancy import OrgOwnedModel


class RuleStatus(models.TextChoices):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class Rule(OrgOwnedModel, TimeStampedModel):
    id = PrefixedIdField(prefix="rul")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=8, choices=RuleStatus.choices, default=RuleStatus.DRAFT)
    current_version = models.ForeignKey(
        "RuleVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "rules"

    def __str__(self) -> str:
        return self.name


class RuleVersion(OrgOwnedModel):
    """Every edit is a new version; events point at the version that created them."""

    id = PrefixedIdField(prefix="rv")
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    source_text = models.TextField(blank=True)
    spec = models.JSONField()  # a validated cammind_spec.RuleSpec
    summary = models.TextField()
    assumptions = models.JSONField(default=list, blank=True)
    created_by = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rule_versions"
        constraints = [
            models.UniqueConstraint(fields=["rule", "version"], name="rule_versions_unique")
        ]
