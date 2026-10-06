import pytest
from django.core.management import CommandError, call_command

from accounts.models import Membership, Organization, Site
from cameras.models import Camera

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_sites_users_and_cameras_and_is_repeatable(settings, api) -> None:
    settings.DEMO_PASSWORD = "demo-password-123"
    call_command("seed_demo", "--no-video", stdout=None)
    call_command("seed_demo", "--no-video", stdout=None)  # second run updates, never duplicates

    org = Organization.objects.get(name="CamMind Demo")
    assert set(Site.objects.for_org(org).values_list("name", flat=True)) == {
        "Home",
        "Green Valley School",
        "Workshop",
    }
    access = {
        m.user.email: (m.role, sorted(s.name for s in m.sites.all()))
        for m in Membership.objects.for_org(org).select_related("user").prefetch_related("sites")
    }
    assert access == {
        "owner@cammind.test": ("owner", []),
        "admin@cammind.test": ("admin", []),
        "guard@cammind.test": ("operator", ["Green Valley School"]),
        "viewer@cammind.test": ("viewer", ["Home"]),
    }
    cameras = Camera.objects.for_org(org)
    assert cameras.count() == 5
    gate = cameras.get(name="Main gate")
    assert gate.main_url == "rtsp://mediamtx:8554/school_gate"
    assert "school_gate" not in gate.rtsp_main_enc  # stored encrypted

    login = api.post(
        "/api/v1/auth/login",
        {"email": "guard@cammind.test", "password": "demo-password-123"},
        format="json",
    )
    assert login.status_code == 200


def test_seed_demo_needs_a_password(settings) -> None:
    settings.DEMO_PASSWORD = ""
    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed_demo")
