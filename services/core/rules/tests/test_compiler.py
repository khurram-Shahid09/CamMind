import json

import pytest

from accounts.models import Site
from cameras.models import Camera, Zone
from common.llm import fake_answers

pytestmark = pytest.mark.django_db


@pytest.fixture
def home(make_account):
    owner = make_account("owner@home.test")
    site = Site.objects.create(org=owner.org, name="Home")
    camera = Camera(site=site, name="Backyard")
    camera.set_urls("rtsp://10.0.0.5/live")
    camera.save()
    zone = Zone.objects.create(
        camera=camera, name="Back door", kind="polygon", points=[[0, 0], [1, 0], [1, 1]]
    )
    yield owner, site, camera, zone
    fake_answers.clear()


def compile_(owner, site, text="Alert me if anyone is near the back door after 10 PM"):
    return owner.client.post(
        "/api/v1/rules/compile", {"text": text, "site_id": site.id}, format="json"
    )


def test_rule_with_assumptions_and_template_summary(home) -> None:
    owner, site, camera, zone = home
    seen = []

    def answer(system, parts):
        seen.append(parts)
        spec = {"camera_ids": [camera.id], "where": {"type": "zone", "zone_ids": [zone.id]},
                "condition": {"type": "presence"}, "when": {"windows": [{"from": "22:00", "to": "06:00"}]}}  # fmt: skip
        return {
            "kind": "rule",
            "spec_json": json.dumps(spec),
            "assumptions": ["'After 10 PM' read as 22:00-06:00"],
        }

    fake_answers.register("compile", answer)
    body = compile_(owner, site).data
    assert body["kind"] == "rule"
    assert body["summary"].startswith("A person in Back door for at least 2 s, 22:00–06:00")
    assert zone.id in seen[0][0] and "<request>" in seen[0][1]  # ids in context, text as data


def test_invented_ids_get_one_repair_then_fail(home) -> None:
    owner, site, camera, _ = home
    fake_answers.register("compile", lambda s, p: {"kind": "rule", "spec_json": json.dumps(
        {"camera_ids": [camera.id], "where": {"type": "zone", "zone_ids": ["zn_made_up"]}, "condition": {"type": "presence"}})})  # fmt: skip
    body = compile_(owner, site).data
    assert body["kind"] == "invalid" and body["calls"] == 2
    assert "unknown zone zn_made_up" in body["errors"]


def test_refusals_and_questions_pass_through(home) -> None:
    owner, site, _, _ = home
    fake_answers.register(
        "compile",
        lambda s, p: {
            "kind": "unsupported",
            "reason": "No face recognition.",
            "suggestion": "Anyone at the gate",
        },
    )
    body = compile_(owner, site, "Tell me when Ali comes home").data
    assert (body["kind"], body["suggestion"]) == ("unsupported", "Anyone at the gate")


def test_viewers_cannot_compile(home, make_account) -> None:
    owner, site, _, _ = home
    viewer = make_account("v@home.test", org=owner.org, role="viewer")
    assert compile_(viewer, site).status_code == 403
