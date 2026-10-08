"""Settings shared by every environment. Environment-specific overrides live in dev/prod/test."""

from datetime import timedelta
from pathlib import Path

import environ

CORE_DIR = Path(__file__).resolve().parents[2]  # services/core
REPO_ROOT = CORE_DIR.parents[1]

env = environ.Env()
# Local development reads the repo-root .env. In containers the variables come from the environment.
if (REPO_ROOT / ".env").is_file():
    # parse_comments: .env.example documents values with trailing "# ..." comments.
    env.read_env(str(REPO_ROOT / ".env"), overwrite=False, parse_comments=True)

APP_ENV = env.str("APP_ENV", default="local")
SECRET_KEY = env.str("DJANGO_SECRET_KEY").strip()
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
APP_BASE_URL = env.str("APP_BASE_URL", default="http://localhost:3200")
API_BASE_URL = env.str("API_BASE_URL", default="http://localhost:8200")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # third party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",
    # cammind
    "common",
    "accounts",
    "audit",
    "cameras",
    "rules",
    "events",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = CORE_DIR / "staticfiles"

REDIS_URL = env.str("REDIS_URL", default="redis://localhost:6381/0")

# --- DRF / OpenAPI ---
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.PersonalAccessTokenAuthentication",  # "Bearer pat_..."
        "rest_framework_simplejwt.authentication.JWTAuthentication",  # "Bearer <jwt>"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.CursorPagination",
    "DEFAULT_THROTTLE_RATES": {
        "login_ip": "20/min",
        "login_email": "5/min",  # with login_ip: brute-force lockout per account
        "register": "10/hour",
    },
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "CamMind API",
    "DESCRIPTION": "Plain-English rules for IP cameras: compiled, confirmed, watched on site.",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- Auth tokens (docs/12-api-spec.md) ---
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "sub",
    "AUTH_HEADER_TYPES": ("Bearer",),
}
REFRESH_COOKIE = {
    "key": "cm_refresh",
    "path": "/api/v1/auth/",
    "httponly": True,
    "secure": not DEBUG,
    "samesite": "Lax",  # served first-party through the dashboard's server (BFF)
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = env.list("CORS_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# --- Celery (queues in docs/03-architecture.md) ---
CELERY_QUEUES = ("compile", "verify", "media", "actions")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_DEFAULT_QUEUE = "actions"
# Tasks are named "<queue>.<task>", e.g. "media.cut_clip"; the prefix picks the queue.
CELERY_TASK_ROUTES = {
    f"{queue}.*": {"queue": queue, "routing_key": queue} for queue in CELERY_QUEUES
}
CELERY_BEAT_SCHEDULE = {
    # A restarted go2rtc gets its streams back within a minute.
    "sync-go2rtc": {"task": "media.sync_go2rtc", "schedule": 60},
}

# --- Encryption of camera URLs and channel secrets (docs/14-security-privacy.md) ---
FIELD_ENCRYPTION_KEY = env.str("FIELD_ENCRYPTION_KEY", default="").strip()

# --- Snapshots and clips (docs/04-tech-stack.md) ---
STORAGE_BACKEND = env.str("STORAGE_BACKEND", default="s3").strip()  # s3 | local
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(CORE_DIR / "media")))
S3_ENDPOINT = env.str("S3_ENDPOINT", default="http://localhost:9200").strip()
S3_BUCKET = env.str("S3_BUCKET", default="cammind-dev").strip()
S3_ACCESS_KEY_ID = env.str("S3_ACCESS_KEY_ID", default="").strip()
S3_SECRET_ACCESS_KEY = env.str("S3_SECRET_ACCESS_KEY", default="").strip()
S3_REGION = env.str("S3_REGION", default="us-east-1").strip()

# --- Cameras and go2rtc (docs/07-video-pipeline.md) ---
GO2RTC_URL = env.str("GO2RTC_URL", default="http://localhost:1984").strip()
CAMERA_PROBE_TIMEOUT_S = env.float("CAMERA_PROBE_TIMEOUT_S", default=5.0)


def _aliases(raw: str) -> dict[str, str]:
    """ "mediamtx:8554=localhost:8654,..." -> {"mediamtx:8554": "localhost:8654"}"""
    pairs = (item.split("=", 1) for item in raw.split(",") if "=" in item)
    return {name.strip().lower(): target.strip() for name, target in pairs}


# Development only: lets the core reach test cameras that only have a name inside Docker.
CAMERA_HOST_ALIASES = _aliases(env.str("CAMERA_HOST_ALIASES", default=""))

# --- Vision worker (docs/12-api-spec.md, "Internal") ---
WORKER_TOKEN = env.str("WORKER_TOKEN", default="").strip()

# --- Alerts (docs/10-actions-and-notifications.md) ---
SLACK_WEBHOOK_URL = env.str("SLACK_WEBHOOK_URL", default="").strip()

# --- AI: rule compiler and verification (docs/06, docs/09) ---
LLM_PROVIDER = env.str("LLM_PROVIDER", default="fake").strip().lower()  # gemini | fake
GEMINI_API_KEYS = [k.strip() for k in env.list("GEMINI_API_KEYS", default=[]) if k.strip()]
GEMINI_MODELS = [
    m.strip() for m in env.list("GEMINI_MODELS", default=["gemini-3.6-flash", "gemini-3.5-flash"])
]

# --- Demo workspace (manage.py seed_demo) ---
DEMO_PASSWORD = env.str("DEMO_PASSWORD", default="").strip()

# --- Logging: single-line logs to stdout ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "line": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "line"}},
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"}},
}

# --- Error reporting (off unless a DSN is set) ---
SENTRY_DSN_API = env.str("SENTRY_DSN_API", default="")
SENTRY_ENVIRONMENT = env.str("SENTRY_ENVIRONMENT", default="development")
