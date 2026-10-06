import pytest
from django.core.exceptions import ImproperlyConfigured

from common.crypto import DecryptionError, decrypt, encrypt

URL = "rtsp://admin:S3cret!@192.168.1.20:554/Streaming/Channels/101"


def test_round_trip_and_random_nonce() -> None:
    first = encrypt(URL, org_id="org_a")
    second = encrypt(URL, org_id="org_a")
    assert first.startswith("v1:") and first != second
    assert "S3cret" not in first
    assert decrypt(first, org_id="org_a") == URL


def test_value_is_bound_to_its_org() -> None:
    token = encrypt(URL, org_id="org_a")
    with pytest.raises(DecryptionError):
        decrypt(token, org_id="org_b")


@pytest.mark.parametrize("token", ["v2:abc", "v1:not-base64!", "v1:" + "A" * 40])
def test_tampered_or_unknown_values_are_rejected(token: str) -> None:
    with pytest.raises(DecryptionError):
        decrypt(token, org_id="org_a")


@pytest.mark.parametrize("key", ["", "not base64", "c2hvcnQ="])
def test_bad_key_is_a_configuration_error(settings, key: str) -> None:
    settings.FIELD_ENCRYPTION_KEY = key
    with pytest.raises(ImproperlyConfigured):
        encrypt(URL, org_id="org_a")
