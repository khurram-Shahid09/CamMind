import os

# Tests must not depend on a developer's secrets; provide safe defaults before base reads the env.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-not-for-production-" + "x" * 20)
os.environ.setdefault("DATABASE_URL", "postgres://cammind:cammind@localhost:5436/cammind")

from .base import *  # noqa: E402, F403

DEBUG = False
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher"
]  # fast tests only  # noqa: S303
CELERY_TASK_ALWAYS_EAGER = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
