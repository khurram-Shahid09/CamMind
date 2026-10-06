import pytest

from audit.models import AuditLog
from audit.service import record

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_managers_read_audit_newest_first(make_account, role) -> None:
    account = make_account(f"{role}@gvs.test", role=role)
    record("first", org=account.org, actor="system")
    record("second", org=account.org, actor="system")
    record("third", org=account.org, actor="system")
    response = account.client.get("/api/v1/audit?limit=2")
    assert response.status_code == 200
    page = response.data["results"]
    assert len(page) == 2 and response.data["next"]  # cursor pagination
    keys = [(r["created_at"], r["id"]) for r in page]
    assert keys == sorted(keys, reverse=True)
    rest = account.client.get(response.data["next"]).data["results"]
    assert {r["action"] for r in page + rest} >= {"first", "second", "third"}


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_operators_and_viewers_cannot_read_audit(make_account, role) -> None:
    owner = make_account("owner@gvs.test")
    member = make_account(f"{role}@gvs.test", org=owner.org, role=role)
    response = member.client.get("/api/v1/audit")
    assert response.status_code == 403
    assert response.data["error"]["code"] == "role_required"


def test_record_captures_request_context(make_account) -> None:
    account = make_account("owner@gvs.test")
    account.client.post(
        "/api/v1/tokens",
        {"name": "home-assistant"},
        format="json",
        HTTP_USER_AGENT="pytest-agent",
        HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.1",
    )
    entry = AuditLog.objects.for_org(account.org).get(action="token.created")
    assert entry.actor == f"user:{account.user.pk}"
    assert entry.ip == "203.0.113.7"
    assert entry.user_agent == "pytest-agent"
