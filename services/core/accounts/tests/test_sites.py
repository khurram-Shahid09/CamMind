import pytest

from accounts.models import Site
from audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_owner_creates_and_renames_a_site(make_account) -> None:
    owner = make_account("owner@home.test")
    created = owner.client.post(
        "/api/v1/sites", {"name": "Home", "timezone": "Asia/Karachi"}, format="json"
    )
    assert created.status_code == 201
    assert created.data["retention_days_media"] == 14
    url = f"/api/v1/sites/{created.data['id']}"
    renamed = owner.client.patch(url, {"name": "Lahore house"}, format="json")
    assert renamed.status_code == 200 and renamed.data["name"] == "Lahore house"
    actions = list(AuditLog.objects.for_org(owner.org).values_list("action", flat=True))
    assert {"site.created", "site.updated"} <= set(actions)


def test_site_validation(make_account) -> None:
    owner = make_account("owner@home.test")
    Site.objects.create(org=owner.org, name="Home")
    dup = owner.client.post("/api/v1/sites", {"name": "Home"}, format="json")
    assert dup.status_code == 409 and dup.data["error"]["code"] == "site_exists"
    zone = owner.client.post(
        "/api/v1/sites", {"name": "B", "timezone": "Nowhere/Zone"}, format="json"
    )
    assert zone.status_code == 400
    keep = owner.client.post(
        "/api/v1/sites", {"name": "C", "retention_days_media": 0}, format="json"
    )
    assert keep.status_code == 400


def test_members_only_see_their_sites(make_account) -> None:
    owner = make_account("principal@gvs.test")
    campus = Site.objects.create(org=owner.org, name="Main campus")
    annex = Site.objects.create(org=owner.org, name="Junior annex")
    guard = make_account("guard@gvs.test", org=owner.org, role="operator", sites=[campus])
    listed = [s["id"] for s in guard.client.get("/api/v1/sites").data["results"]]
    assert listed == [campus.id]
    assert guard.client.get(f"/api/v1/sites/{annex.id}").status_code == 404
    assert len(owner.client.get("/api/v1/sites").data["results"]) == 2


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_only_managers_change_sites(make_account, role) -> None:
    owner = make_account("owner@home.test")
    site = Site.objects.create(org=owner.org, name="Home")
    member = make_account(f"{role}@home.test", org=owner.org, role=role)
    assert member.client.post("/api/v1/sites", {"name": "X"}, format="json").status_code == 403
    assert (
        member.client.patch(f"/api/v1/sites/{site.id}", {"name": "Y"}, format="json").status_code
        == 403
    )
    assert member.client.delete(f"/api/v1/sites/{site.id}").status_code == 403


def test_empty_site_can_be_deleted(make_account) -> None:
    owner = make_account("owner@home.test")
    site = Site.objects.create(org=owner.org, name="Old flat")
    assert owner.client.delete(f"/api/v1/sites/{site.id}").status_code == 204
    assert not Site.objects.filter(pk=site.pk).exists()
