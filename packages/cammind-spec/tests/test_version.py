from datetime import time

import pytest
from pydantic import ValidationError

import cammind_spec
from cammind_spec import RuleSpec, Window

DOOR_AT_NIGHT = {
    "camera_ids": ["cam_backyard"],
    "target": {"classes": ["person"]},
    "where": {"type": "zone", "zone_ids": ["zn_back_door"]},
    "condition": {"type": "presence"},
    "when": {"windows": [{"from": "22:00", "to": "06:00"}]},
    "timing": {"hold_seconds": 3},
    "actions": [{"type": "notify", "roles": ["owner"], "include": ["snapshot", "clip"]}],
}


def test_spec_version_starts_at_one() -> None:
    assert cammind_spec.SPEC_VERSION == 1


def test_docs_example_parses_with_defaults() -> None:
    spec = RuleSpec.model_validate(DOOR_AT_NIGHT)
    assert spec.where.type == "zone" and spec.timing.cooldown_seconds == 120
    assert not spec.per_track
    assert "camera_ids" in RuleSpec.model_json_schema()["properties"]


@pytest.mark.parametrize(
    "change",
    [
        {"condition": {"type": "crossing"}},  # crossing without a line
        {"where": {"type": "line", "line_id": "ln_gate"}},  # line without crossing
        {"camera_ids": []},
        {"condition": {"type": "dwell", "min_seconds": 0}},
        {"surprise": True},
    ],
)
def test_invalid_specs_are_rejected(change) -> None:
    with pytest.raises(ValidationError):
        RuleSpec.model_validate({**DOOR_AT_NIGHT, **change})


def test_overnight_window_belongs_to_the_day_it_starts() -> None:
    window = Window.model_validate({"days": ["fri"], "from": "22:00", "to": "06:00"})
    assert window.covers("fri", time(23, 0), "thu")
    assert window.covers("sat", time(5, 59), "fri")
    assert not window.covers("sat", time(23, 0), "fri")
    assert not window.covers("fri", time(12, 0), "thu")
