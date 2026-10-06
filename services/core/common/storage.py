"""Object storage for snapshots and clips (docs/04-tech-stack.md).

``s3``: any S3 API (SeaweedFS locally, Cloudflare R2 for the hosted demo).
``local``: files under MEDIA_ROOT, for tests and setups without object storage.
Keys look like ``<org_id>/cameras/<camera_id>/snapshot.jpg``; they never come from user input.
"""

from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from django.conf import settings


class StorageError(Exception):
    pass


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def delete(self, key: str) -> None: ...


def _safe(key: str) -> str:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise StorageError(f"invalid storage key {key!r}")
    return str(path)


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / _safe(key)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class S3Storage:
    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = settings.S3_BUCKET
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT or None,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=_safe(key), Body=data, ContentType=content_type
            )
        except Exception as exc:  # noqa: BLE001 - botocore raises many types
            raise StorageError(f"could not store {key}") from exc

    def get(self, key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=_safe(key))
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"could not read {key}") from exc
        return response["Body"].read()

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=_safe(key))
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"could not delete {key}") from exc


@cache
def _storage(backend: str, root: str) -> Storage:
    if backend == "s3":
        return S3Storage()
    if backend == "local":
        return LocalStorage(Path(root))
    raise StorageError(f"unknown STORAGE_BACKEND {backend!r}")


def storage() -> Storage:
    return _storage(settings.STORAGE_BACKEND, str(settings.MEDIA_ROOT))
