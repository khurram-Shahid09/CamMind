import pytest

from common.storage import StorageError, storage


@pytest.fixture(autouse=True)
def _local(settings, tmp_path):
    settings.STORAGE_BACKEND = "local"
    settings.MEDIA_ROOT = tmp_path


def test_put_get_delete() -> None:
    store = storage()
    store.put("org_a/cameras/cam_1/snapshot.jpg", b"jpeg", "image/jpeg")
    assert store.get("org_a/cameras/cam_1/snapshot.jpg") == b"jpeg"
    store.delete("org_a/cameras/cam_1/snapshot.jpg")
    assert store.get("org_a/cameras/cam_1/snapshot.jpg") is None
    store.delete("org_a/cameras/cam_1/snapshot.jpg")  # deleting twice is fine


@pytest.mark.parametrize("key", ["", "/etc/passwd", "org_a/../../secrets"])
def test_keys_cannot_escape_the_root(key: str) -> None:
    with pytest.raises(StorageError):
        storage().put(key, b"x", "text/plain")
