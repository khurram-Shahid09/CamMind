import base64

import pytest
from django.test import Client

from accounts.models import Organization, Site
from cameras.models import Camera, Zone
from events.models import Event
from rules.models import Rule, RuleVersion
from rules.service import SpecError, summarize, validate_spec

pytestmark = pytest.mark.django_db
WORKER = {"Authorization": "Worker test-worker-token"}


@pytest.fixture
def setup():
    org = Organization.objects.create(name="Home")
    site = Site.objects.create(org=org, name="Home", timezone="Asia/Karachi")
    camera = Camera(site=site, name="Back door")
    camera.set_urls("rtsp://10.0.0.5/live")
    camera.save()
    zone = Zone.objects.create(
        camera=camera, name="Back door", kind="polygon", points=[[0, 0.5], [1, 0.5], [1, 1], [0, 1]]
    )
    spec = validate_spec(
        {
            "camera_ids": [camera.id],
            "where": {"type": "zone", "zone_ids": [zone.id]},
            "condition": {"type": "presence"},
        },
        org,
    )
    rule = Rule.objects.create(org=org, site=site, name="Back door", status="active")
    version = RuleVersion.objects.create(
        org=org, rule=rule, version=1, spec=spec.model_dump(mode="json", by_alias=True), summary="x"
    )
    rule.current_version = version
    rule.save()
    return camera, zone, version


def test_config_needs_the_worker_token(setup) -> None:
    assert Client().get("/internal/config").status_code == 401
    body = Client(headers=WORKER).get("/internal/config").json()
    assert [c["name"] for c in body["cameras"]] == ["Back door"]
    assert body["zones"][0]["points"][0] == [0, 0.5]
    assert body["rules"][0]["spec"]["condition"]["type"] == "presence"


def test_events_are_idempotent_and_closed(setup) -> None:
    camera, _, version = setup
    start = {
        "kind": "start", "key": "rv:cam:-:1", "rule_id": version.id, "camera_id": camera.id,
        "ts": "2026-10-07T18:00:00+00:00", "reason": "1 person in Back door",
        "objects": [{"track_id": 1, "class": "person"}],
        "snapshot_jpeg_b64": base64.b64encode(b"\xff\xd8jpeg").decode(),
    }  # fmt: skip
    client = Client(headers=WORKER)
    first = client.post("/internal/events", start, content_type="application/json")
    assert first.status_code == 201 and first.json()["state"] == "confirmed"
    again = client.post("/internal/events", start, content_type="application/json")
    assert again.json()["duplicate"] is True
    end = {
        **start,
        "kind": "end",
        "ts": "2026-10-07T18:00:09+00:00",
        "close_reason": "condition_ended",
    }
    client.post("/internal/events", end, content_type="application/json")
    event = Event.objects.get()
    assert event.t_end is not None and event.close_reason == "condition_ended"
    assert event.snapshot_key.endswith("snapshot.jpg")


def test_validation_rejects_wrong_ids_and_identity_questions(setup) -> None:
    camera, zone, _ = setup
    with pytest.raises(SpecError, match="unknown zone"):
        validate_spec(
            {
                "camera_ids": [camera.id],
                "where": {"type": "zone", "zone_ids": ["zn_x"]},
                "condition": {"type": "presence"},
            },
            camera.org,
        )
    with pytest.raises(SpecError, match="who someone is"):
        validate_spec(
            {
                "camera_ids": [camera.id],
                "condition": {"type": "presence"},
                "verify": {"question": "Whose face is this?", "expect": "yes"},
            },
            camera.org,
        )
    spec = validate_spec(
        {
            "camera_ids": [camera.id],
            "where": {"type": "zone", "zone_ids": [zone.id]},
            "condition": {"type": "dwell", "min_seconds": 120},
        },
        camera.org,
    )
    assert summarize(spec, {zone.id: "Back door"}).startswith(
        "A person stays in Back door for 2 min"
    )
