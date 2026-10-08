"""Rule validation against real ids (docs/05, "Validation") and the plain-English summary,
generated from the spec by a template so it always matches what will run (docs/06)."""

from cammind_spec import (
    Absence,
    Count,
    Crossing,
    Dwell,
    Presence,
    RuleSpec,
    WhereLine,
    WhereZone,
)
from pydantic import ValidationError

from accounts.models import Organization
from cameras.models import Camera, Zone

DETECTOR_CLASSES = {
    "person", "bicycle", "car", "motorcycle", "bus", "truck", "dog", "cat", "bird",
    "backpack", "handbag", "suitcase", "umbrella", "bottle", "chair", "couch",
    "cell phone", "laptop",
}  # fmt: skip
BANNED_WORDS = ("face", "who is", "identify", "gender", "ethnic", "religio", "age of", "race")


class SpecError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_spec(data: dict, org: Organization) -> RuleSpec:
    try:
        spec = RuleSpec.model_validate(data)
    except ValidationError as exc:
        raise SpecError(
            [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        ) from exc
    errors = []
    cameras = {c.id: c for c in Camera.objects.for_org(org).filter(id__in=spec.camera_ids)}
    errors += [f"unknown camera {c}" for c in spec.camera_ids if c not in cameras]
    zone_ids = []
    if isinstance(spec.where, WhereZone):
        zone_ids = spec.where.zone_ids
    elif isinstance(spec.where, WhereLine):
        zone_ids = [spec.where.line_id]
    zones = {z.id: z for z in Zone.objects.for_org(org).filter(id__in=zone_ids)}
    for zid in zone_ids:
        zone = zones.get(zid)
        if zone is None:
            errors.append(f"unknown zone {zid}")
        elif zone.camera_id not in cameras:
            errors.append(f"zone {zone.name} isn't on the rule's cameras")
        elif isinstance(spec.where, WhereLine) != (zone.kind == "line"):
            errors.append(f"{zone.name} is {'a line' if zone.kind == 'line' else 'an area'}")
    errors += [
        f"the detector can't see {c!r}" for c in spec.target.classes if c not in DETECTOR_CLASSES
    ]
    if spec.verify and any(w in spec.verify.question.lower() for w in BANNED_WORDS):
        errors.append("questions can't be about who someone is or protected traits")
    if errors:
        raise SpecError(errors)
    return spec


def _seconds(value: float) -> str:
    return f"{value / 60:g} min" if value >= 120 else f"{value:g} s"


def summarize(spec: RuleSpec, names: dict[str, str]) -> str:
    what = " or ".join(spec.target.classes)
    where = spec.where
    if isinstance(where, WhereZone):
        place = f"in {' / '.join(names.get(z, z) for z in where.zone_ids)}"
    elif isinstance(where, WhereLine):
        place = f"crosses {names.get(where.line_id, where.line_id)} ({where.direction})"
    else:
        place = "in view"
    cond = spec.condition
    if isinstance(cond, Presence):
        text = f"{'A' if cond.min_count == 1 else cond.min_count} {what} {place}"
        if spec.timing.hold_seconds:
            text += f" for at least {_seconds(spec.timing.hold_seconds)}"
    elif isinstance(cond, Count):
        text = f"Number of {what}s {place} {cond.op} {cond.value}"
    elif isinstance(cond, Dwell):
        text = f"A {what} stays {place} for {_seconds(cond.min_seconds)}"
    elif isinstance(cond, Absence):
        text = f"No {what} {place} for {_seconds(cond.min_seconds)}"
    elif isinstance(cond, Crossing):
        text = f"A {what} {place}"
    if spec.verify:
        text += f", and AI answers {spec.verify.expect.upper()} to “{spec.verify.question}”"
    if spec.when.windows:
        spans = ", ".join(f"{w.start:%H:%M}–{w.end:%H:%M}" for w in spec.when.windows)
        text += f", {spans}"
    return (
        f"{text} → alert ({spec.severity}), not again for {_seconds(spec.timing.cooldown_seconds)}"
    )
