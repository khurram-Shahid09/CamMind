"""The rule spec (docs/05-rule-spec.md): the contract between the plain-English sentence and
the rule engine. The compiler produces it, the user confirms it, the engine runs it.
The JSON Schema given to the LLM is generated from these models.
"""

from datetime import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SPEC_VERSION = 1
Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ALL_DAYS: list[Day] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Target(_Model):
    classes: list[str] = Field(default_factory=lambda: ["person"], min_length=1)
    min_confidence: float = Field(0.5, ge=0, le=1)
    min_box_px: int = Field(24, ge=0)


class WhereFrame(_Model):
    type: Literal["frame"] = "frame"


class WhereZone(_Model):
    type: Literal["zone"] = "zone"
    zone_ids: list[str] = Field(min_length=1)
    anchor: Literal["bottom_center", "center"] = "bottom_center"


class WhereLine(_Model):
    type: Literal["line"] = "line"
    line_id: str
    direction: Literal["in", "out", "any"] = "in"


Where = Annotated[WhereFrame | WhereZone | WhereLine, Field(discriminator="type")]


class Presence(_Model):
    type: Literal["presence"] = "presence"
    min_count: int = Field(1, ge=1)


class Count(_Model):
    type: Literal["count"] = "count"
    op: Literal[">", ">=", "<", "<="]
    value: int = Field(ge=0)


class Dwell(_Model):
    type: Literal["dwell"] = "dwell"
    min_seconds: float = Field(ge=1, le=86_400)


class Absence(_Model):
    type: Literal["absence"] = "absence"
    min_seconds: float = Field(ge=1, le=86_400)


class Crossing(_Model):
    type: Literal["crossing"] = "crossing"


Condition = Annotated[Presence | Count | Dwell | Absence | Crossing, Field(discriminator="type")]


class Verify(_Model):
    question: str = Field(min_length=5, max_length=160)
    expect: Literal["yes", "no"]
    scope: Literal["track_crop", "zone_crop", "frame"] = "track_crop"
    recheck_seconds: float = Field(30, ge=1)
    min_confidence: float = Field(0.7, ge=0, le=1)
    on_unsure: Literal["retry_once", "dismiss", "alert_unverified"] = "retry_once"


class Window(_Model):
    days: list[Day] = Field(default_factory=lambda: list(ALL_DAYS), min_length=1)
    start: time = Field(alias="from")
    end: time = Field(alias="to")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def covers(self, day: Day, at: time, previous_day: Day) -> bool:
        if self.start <= self.end:
            return day in self.days and self.start <= at < self.end
        # Overnight (22:00-06:00) belongs to the day it starts.
        return (day in self.days and at >= self.start) or (
            previous_day in self.days and at < self.end
        )


class When(_Model):
    windows: list[Window] = Field(default_factory=list)


class Timing(_Model):
    hold_seconds: float = Field(2, ge=0, le=3600)
    cooldown_seconds: float = Field(120, ge=0, le=86_400)
    max_event_seconds: float = Field(600, ge=10, le=86_400)


Role = Literal["owner", "admin", "operator"]
Media = Literal["snapshot", "clip"]


def _owner() -> list[Role]:
    return ["owner"]


def _snapshot() -> list[Media]:
    return ["snapshot"]


class Notify(_Model):
    type: Literal["notify"] = "notify"
    roles: list[Role] = Field(default_factory=_owner)
    channel_ids: list[str] = Field(default_factory=list)
    include: list[Media] = Field(default_factory=_snapshot)


class Webhook(_Model):
    type: Literal["webhook"] = "webhook"
    webhook_id: str


Action = Annotated[Notify | Webhook, Field(discriminator="type")]


def _notify_owner() -> list[Action]:
    return [Notify()]


class RuleSpec(_Model):
    spec_version: int = SPEC_VERSION
    camera_ids: list[str] = Field(min_length=1)
    target: Target = Field(default_factory=Target)
    where: Where = Field(default_factory=WhereFrame)
    condition: Condition
    verify: Verify | None = None
    when: When = Field(default_factory=When)
    timing: Timing = Field(default_factory=Timing)
    severity: Literal["info", "warning", "critical"] = "warning"
    actions: list[Action] = Field(default_factory=_notify_owner)

    @model_validator(mode="after")
    def _consistent(self) -> "RuleSpec":
        if isinstance(self.condition, Crossing) != isinstance(self.where, WhereLine):
            raise ValueError("a crossing rule needs a line, and a line needs a crossing rule")
        return self

    @property
    def per_track(self) -> bool:
        return isinstance(self.condition, Dwell | Crossing) or (
            self.verify is not None and self.verify.scope == "track_crop"
        )


__all__ = [
    "SPEC_VERSION",
    "Absence",
    "Count",
    "Crossing",
    "Dwell",
    "Notify",
    "Presence",
    "RuleSpec",
    "Target",
    "Timing",
    "Verify",
    "When",
    "WhereFrame",
    "WhereLine",
    "WhereZone",
    "Window",
]
