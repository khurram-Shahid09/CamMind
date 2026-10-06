import pytest

from accounts.models import Membership, Site, User
from audit.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def school(make_account):
    owner = make_account("principal@gvs.test")
    campus = Site.objects.create(org=owner.org, name="Main campus")
    annex = Site.objects.create(org=owner.org, name="Junior annex")
    User.objects.create_user("guard@gvs.test", PASSWORD)
    return owner, campus, annex


def members_url(account) -> str:
    return f"/api/v1/orgs/{account.org.id}/members"


def test_admin_adds_a_guard_to_one_campus(school, make_account) -> None:
    owner, campus, _ = school
    admin = make_account("it@gvs.test", org=owner.org, role="admin")
    response = admin.client.post(
        members_url(owner),
        {
            "email": "guard@gvs.test",
            "role": "operator",
            "all_sites": False,
            "site_ids": [campus.id],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert (response.data["role"], response.data["site_ids"]) == ("operator", [campus.id])
    entry = AuditLog.objects.for_org(owner.org).get(action="member.added")
    assert entry.metadata["site_ids"] == [campus.id]


def test_limited_access_needs_at_least_one_site(school) -> None:
    owner, _, _ = school
    response = owner.client.post(
        members_url(owner),
        {"email": "guard@gvs.test", "role": "viewer", "all_sites": False},
        format="json",
    )
    assert response.status_code == 400
    assert "site_ids" in response.data["error"]["details"]["fields"]


def test_sites_of_another_org_are_rejected(school, make_account) -> None:
    owner, _, _ = school
    stranger = make_account("x@other.test")
    their_site = Site.objects.create(org=stranger.org, name="Theirs")
    response = owner.client.post(
        members_url(owner),
        {
            "email": "guard@gvs.test",
            "role": "viewer",
            "all_sites": False,
            "site_ids": [their_site.id],
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_only_owners_and_admins_manage_members(school, make_account, role) -> None:
    owner, _, _ = school
    member = make_account(f"{role}@gvs.test", org=owner.org, role=role)
    response = member.client.post(
        members_url(owner), {"email": "guard@gvs.test", "role": "viewer"}, format="json"
    )
    assert response.status_code == 403
    assert response.data["error"]["code"] == "role_required"
    assert member.client.get(members_url(owner)).status_code == 200  # everyone sees the team


def test_admins_cannot_make_or_change_owners(school, make_account) -> None:
    owner, _, _ = school
    admin = make_account("it@gvs.test", org=owner.org, role="admin")
    make_owner = admin.client.post(
        members_url(owner), {"email": "guard@gvs.test", "role": "owner"}, format="json"
    )
    assert make_owner.status_code == 403
    assert make_owner.data["error"]["code"] == "owner_required"
    demote = admin.client.patch(
        f"{members_url(owner)}/{owner.membership.id}", {"role": "viewer"}, format="json"
    )
    assert demote.status_code == 403
    assert admin.client.delete(f"{members_url(owner)}/{owner.membership.id}").status_code == 403


def test_the_last_owner_stays(school) -> None:
    owner, _, _ = school
    url = f"{members_url(owner)}/{owner.membership.id}"
    demote = owner.client.patch(url, {"role": "admin"}, format="json")
    assert demote.status_code == 409 and demote.data["error"]["code"] == "last_owner"
    assert owner.client.delete(url).status_code == 409


def test_owner_hands_over_then_steps_down(school) -> None:
    owner, _, _ = school
    added = owner.client.post(
        members_url(owner), {"email": "guard@gvs.test", "role": "owner"}, format="json"
    )
    assert added.status_code == 201
    url = f"{members_url(owner)}/{owner.membership.id}"
    assert owner.client.patch(url, {"role": "admin"}, format="json").status_code == 200
    assert Membership.objects.get(pk=owner.membership.pk).role == "admin"


def test_update_records_before_and_after(school, make_account) -> None:
    owner, campus, annex = school
    guard = make_account("g2@gvs.test", org=owner.org, role="operator", sites=[campus])
    response = owner.client.patch(
        f"{members_url(owner)}/{guard.membership.id}",
        {"site_ids": [campus.id, annex.id]},
        format="json",
    )
    assert response.status_code == 200
    entry = AuditLog.objects.for_org(owner.org).get(action="member.updated")
    assert entry.metadata["from"]["site_ids"] == [campus.id]
    assert sorted(entry.metadata["to"]["site_ids"]) == sorted([campus.id, annex.id])
