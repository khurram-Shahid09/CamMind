"""Field encryption for camera URLs (they carry passwords) and channel secrets
(docs/14-security-privacy.md).

``encrypt`` / ``decrypt``: AES-256-GCM with a random nonce; the stored text is
``v1:<base64(nonce + ciphertext)>``. The org id is bound as associated data, so a value
copied into another tenant's row fails to decrypt.

The key is FIELD_ENCRYPTION_KEY (base64, 32 bytes). The encryption key is derived from it,
so the same master key can later derive other keys without weakening this one.
"""

import base64
import hashlib
import hmac
import os
from functools import cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

VERSION = "v1"
NONCE_BYTES = 12


class DecryptionError(Exception):
    pass


@cache
def _key(raw: str) -> bytes:
    try:
        master = base64.b64decode(raw, validate=True)
    except ValueError as exc:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be base64") from exc
    if len(master) != 32:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must decode to 32 bytes")
    return hmac.new(master, b"cammind:encrypt", hashlib.sha256).digest()


def _encryption_key() -> bytes:
    if not settings.FIELD_ENCRYPTION_KEY:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not set")
    return _key(settings.FIELD_ENCRYPTION_KEY)


def encrypt(plaintext: str, *, org_id: str) -> str:
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(_encryption_key()).encrypt(nonce, plaintext.encode(), org_id.encode())
    return f"{VERSION}:{base64.b64encode(nonce + sealed).decode()}"


def decrypt(token: str, *, org_id: str) -> str:
    version, _, payload = token.partition(":")
    if version != VERSION:
        raise DecryptionError(f"unknown format {version!r}")
    try:
        blob = base64.b64decode(payload, validate=True)
        plain = AESGCM(_encryption_key()).decrypt(
            blob[:NONCE_BYTES], blob[NONCE_BYTES:], org_id.encode()
        )
    except Exception as exc:  # noqa: BLE001 - any failure means the value can't be trusted
        raise DecryptionError("value could not be decrypted") from exc
    return plain.decode()
