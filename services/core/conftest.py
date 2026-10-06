from dataclasses import dataclass

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import Membership, Organization, Role, Site, User

PASSWORD = "correct-horse-battery-9"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()  # throttle counters live in the cache
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _local_storage(settings, tmp_path):
    settings.STORAGE_BACKEND = "local"
    settings.MEDIA_ROOT = tmp_path / "media"


@dataclass
class Account:
    user: User
    org: Organization
    membership: Membership
    client: APIClient  # authenticated with a JWT access token


@pytest.fixture
def make_account(db):
    """make_account("sara@acme.test", org=None, role="owner", sites=None) → Account.

    ``sites``: limit the member to these sites (default: every site of the org).
    """

    def _make(
        email: str,
        *,
        org: Organization | None = None,
        role: str = Role.OWNER,
        sites: list[Site] | None = None,
    ) -> Account:
        user = User.objects.create_user(email, PASSWORD, name=email.split("@")[0])
        org = org or Organization.objects.create(name=f"{email} org")
        membership = Membership.objects.create(
            org=org, user=user, role=role, all_sites=sites is None
        )
        if sites:
            membership.sites.set(sites)
        client = APIClient()
        response = client.post(
            "/api/v1/auth/login", {"email": email, "password": PASSWORD}, format="json"
        )
        assert response.status_code == 200, response.content
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return Account(user, org, membership, client)

    return _make


@pytest.fixture
def api() -> APIClient:
    return APIClient()
