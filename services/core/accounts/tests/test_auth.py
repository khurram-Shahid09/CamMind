import pytest
from django.conf import settings
from django.core.cache import cache

from accounts.models import Membership, Organization, Site, User
from audit.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db
COOKIE = settings.REFRESH_COOKIE["key"]


def register(
    api, email="sara@acme.test", password=PASSWORD, org_name="Green Valley School", **extra
):
    return api.post(
        "/api/v1/auth/register",
        {"email": email, "password": password, "name": "Sara", "org_name": org_name, **extra},
        format="json",
    )


def test_register_creates_workspace_owned_by_the_user_with_a_first_site(api) -> None:
    response = register(api, email="Sara@Acme.TEST", tier="school", timezone="Asia/Dubai")
    assert response.status_code == 201
    assert response.data["user"]["email"] == "sara@acme.test"
    assert response.data["access_expires_in"] == 15 * 60

    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] and cookie["path"] == "/api/v1/auth/"
    assert "refresh" not in response.data  # refresh token only ever travels in the cookie

    user = User.objects.get(email="sara@acme.test")
    membership = Membership.objects.get(user=user)
    assert membership.role == "owner" and membership.all_sites
    org = membership.org
    assert (org.name, org.tier) == ("Green Valley School", "school")
    site = Site.objects.for_org(org).get()
    assert (site.name, site.timezone) == ("Green Valley School", "Asia/Dubai")
    actions = set(AuditLog.objects.for_org(org).values_list("action", flat=True))
    assert actions == {"org.created", "user.registered", "site.created"}


def test_register_rejects_duplicate_email_weak_password_and_bad_timezone(api) -> None:
    assert register(api).status_code == 201
    dup = register(api, email="SARA@acme.test")
    assert dup.status_code == 400 and "email" in dup.data["error"]["details"]["fields"]

    weak = register(api, email="new@acme.test", password="12345")
    assert weak.status_code == 400
    assert weak.data["error"]["code"] == "validation_error"
    assert "password" in weak.data["error"]["details"]["fields"]

    zone = register(api, email="tz@acme.test", timezone="Mars/Olympus")
    assert "timezone" in zone.data["error"]["details"]["fields"]
    assert Organization.objects.count() == 1  # nothing half-created


def test_login_and_me(make_account) -> None:
    account = make_account("imran@acme.test", role="operator")
    me = account.client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.data["email"] == "imran@acme.test"
    membership = me.data["memberships"][0]
    assert membership["org"] == {"id": account.org.id, "name": account.org.name, "tier": "home"}
    assert (membership["role"], membership["all_sites"], membership["site_ids"]) == (
        "operator",
        True,
        [],
    )


def test_login_wrong_password(api, make_account) -> None:
    make_account("imran@acme.test")
    response = api.post(
        "/api/v1/auth/login", {"email": "imran@acme.test", "password": "nope"}, format="json"
    )
    assert response.status_code == 401
    assert response.data["error"]["code"] == "invalid_credentials"


def test_login_is_throttled_per_account(api, make_account) -> None:
    make_account("imran@acme.test")
    cache.clear()  # the fixture's own login counted as an attempt
    codes = [
        api.post(
            "/api/v1/auth/login", {"email": "imran@acme.test", "password": "guess"}, format="json"
        ).status_code
        for _ in range(6)
    ]
    assert codes == [401] * 5 + [429]


def test_unauthenticated_requests_are_rejected(api) -> None:
    response = api.get("/api/v1/me")
    assert response.status_code == 401
    assert response.data["error"]["code"] == "not_authenticated"


def test_refresh_rotates_and_detects_reuse(api) -> None:
    first = register(api).cookies[COOKIE].value

    rotated = api.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200 and rotated.data["access"]
    second = rotated.cookies[COOKIE].value
    assert second != first

    # An attacker replays the old (already rotated) token: rejected, and the whole family dies.
    api.cookies[COOKIE] = first
    replay = api.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.data["error"]["code"] == "invalid_session"

    api.cookies[COOKIE] = second
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_without_cookie(api) -> None:
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(api) -> None:
    token = register(api).cookies[COOKIE].value
    response = api.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert response.cookies[COOKIE].value == ""

    api.cookies[COOKIE] = token
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_inactive_user_cannot_refresh(api) -> None:
    register(api)
    User.objects.filter(email="sara@acme.test").update(is_active=False)
    assert api.post("/api/v1/auth/refresh").status_code == 401
