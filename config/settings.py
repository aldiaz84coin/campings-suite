"""
Django settings for Campings Suite.

All deployment-specific values come from environment variables (see
``.env.example``). Locally a ``.env`` file is read if present.
"""

import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

DEBUG = env.bool("DEBUG", default=False)

SECRET_KEY = env("SECRET_KEY", default="")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-development-key-change-me"
    else:
        raise ImproperlyConfigured("Set the SECRET_KEY environment variable.")

# --- Hosts -------------------------------------------------------------------
# Fly.io injects FLY_APP_NAME into every machine.
FLY_APP_NAME = env("FLY_APP_NAME", default="")
_default_hosts = ["localhost", "127.0.0.1", "[::1]"]
if FLY_APP_NAME:
    _default_hosts.append(f"{FLY_APP_NAME}.fly.dev")

# Hosts of the platform itself: panel for every camping, super-admin and
# the sites of campings that do not have their own address yet.
PLATFORM_HOSTS = env.list("ALLOWED_HOSTS", default=_default_hosts)
if TESTING:
    PLATFORM_HOSTS.append("testserver")

# Every camping is served on its own domain (and optionally on a subdomain),
# so Django's own host check is delegated to
# core.middleware.HostRoutingMiddleware, which accepts PLATFORM_HOSTS plus
# the camping addresses stored in the database.
ALLOWED_HOSTS = ["*"]

PLATFORM_NAME = env("PLATFORM_NAME", default="Campings Suite")
# Absolute base URL of the platform, used for links in e-mails
# (e.g. https://campings-suite.fly.dev).
PLATFORM_URL = env("PLATFORM_URL", default=f"https://{FLY_APP_NAME}.fly.dev" if FLY_APP_NAME else "").rstrip("/")
# Where the optional "Powered by" credit on camping websites points to.
PLATFORM_CREDIT_URL = env("PLATFORM_CREDIT_URL", default=PLATFORM_URL)

# Optional: give every camping https://<slug>.<CAMPING_DOMAIN_SUFFIX> from day
# one (needs a wildcard DNS record and certificate, see README). A camping's
# own domain always takes precedence once it is receiving visits.
CAMPING_DOMAIN_SUFFIX = env("CAMPING_DOMAIN_SUFFIX", default="").strip().lower().strip(".")
CAMPING_URL_SCHEME = env("CAMPING_URL_SCHEME", default="http" if DEBUG and not TESTING else "https")

# Campings are sold one by one: the platform administrators create them from
# the panel. SIGNUP_ENABLED=true lets campings create their own account.
SIGNUP_ENABLED = env.bool("SIGNUP_ENABLED", default=False)
SIGNUP_REQUIRES_APPROVAL = env.bool("SIGNUP_REQUIRES_APPROVAL", default=True)
MAX_PHOTOS_PER_CAMPING = env.int("MAX_PHOTOS_PER_CAMPING", default=80)
# Importing a camping's current website: seconds spent reading pages, and
# whether private network addresses may be read (only for local testing).
IMPORTER_TIME_BUDGET = env.int("IMPORTER_TIME_BUDGET", default=25)
IMPORTER_ALLOW_PRIVATE_HOSTS = env.bool("IMPORTER_ALLOW_PRIVATE_HOSTS", default=False)
MAX_UPLOAD_MB = env.int("MAX_UPLOAD_MB", default=20)

# --- Applications ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "core",
    "accounts",
    "campings",
    "bookings",
    "public",
    "panel",
    "importer",
]

MIDDLEWARE = [
    "core.middleware.HostRoutingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.platform",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ----------------------------------------------------------------
# Any PostgreSQL works (Supabase, Neon, Fly Postgres...). Without DATABASE_URL
# a local SQLite file is used, which is handy for development.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if env.bool("DB_TRANSACTION_POOLER", default=False):
    # Transaction-mode poolers (Supabase port 6543, PgBouncer) cannot keep
    # server-side cursors or prepared statements between transactions.
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None
    DATABASES["default"]["CONN_MAX_AGE"] = 0

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "panel:login"
LOGIN_REDIRECT_URL = "panel:home"
LOGOUT_REDIRECT_URL = "public:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Internationalisation ----------------------------------------------------
LANGUAGE_CODE = env("LANGUAGE_CODE", default="es")
LANGUAGES = [
    ("es", "Español"),
    ("en", "English"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("nl", "Nederlands"),
    ("it", "Italiano"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = True
TIME_ZONE = env("TIME_ZONE", default="Europe/Madrid")

# --- Static & media files ----------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))

# Where uploaded photos live:
#   s3    -> any S3 compatible bucket (Tigris on Fly, Supabase Storage, R2...)
#   db    -> inside PostgreSQL (zero configuration, fine for small sites)
#   local -> MEDIA_ROOT on disk (development, or a Fly volume)
_bucket = env("AWS_STORAGE_BUCKET_NAME", default=env("BUCKET_NAME", default=""))
MEDIA_STORAGE = env("MEDIA_STORAGE", default="") or ("s3" if _bucket else ("local" if DEBUG else "db"))

if MEDIA_STORAGE == "s3":
    from botocore.config import Config as BotoConfig

    _addressing_style = env("AWS_S3_ADDRESSING_STYLE", default="auto")
    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _bucket,
            "access_key": env("AWS_ACCESS_KEY_ID", default=None),
            "secret_key": env("AWS_SECRET_ACCESS_KEY", default=None),
            "endpoint_url": env("AWS_S3_ENDPOINT_URL", default=env("AWS_ENDPOINT_URL_S3", default=None)),
            "region_name": env("AWS_S3_REGION_NAME", default=env("AWS_REGION", default=None)),
            # Public base URL for files, without scheme, e.g.
            # "<bucket>.fly.storage.tigris.dev" or
            # "<ref>.supabase.co/storage/v1/object/public/<bucket>".
            "custom_domain": env("MEDIA_PUBLIC_DOMAIN", default=None),
            "location": env("MEDIA_LOCATION", default="media"),
            "querystring_auth": env.bool("AWS_QUERYSTRING_AUTH", default=False),
            "default_acl": env("AWS_DEFAULT_ACL", default=None),
            "file_overwrite": False,
            "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
            "client_config": BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": _addressing_style},
                # Many S3-compatible providers reject the newer default
                # integrity checksums added by botocore >= 1.36.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        },
    }
elif MEDIA_STORAGE == "db":
    _default_storage = {"BACKEND": "core.storage.DatabaseStorage"}
elif MEDIA_STORAGE == "local":
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
else:
    raise ImproperlyConfigured("MEDIA_STORAGE must be one of: s3, db, local.")

if TESTING:
    _default_storage = {"BACKEND": "django.core.files.storage.InMemoryStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# Uploads bigger than this are streamed to a temporary file.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# --- Cache -------------------------------------------------------------------
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

# --- E-mail ------------------------------------------------------------------
# e.g. EMAIL_URL=smtp+tls://user:password@smtp-relay.brevo.com:587
EMAIL_CONFIG = env.email_url("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=f"{PLATFORM_NAME} <no-reply@example.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 10

# --- Security ----------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not DEBUG and not TESTING:
    # Fly.io terminates TLS and forwards the original scheme.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env.bool("SECURE_COOKIES", default=True)
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

# --- Logging -----------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO"), "propagate": False},
        "campings": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "bookings": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
if TESTING:
    for _logger in LOGGING["loggers"].values():
        _logger["level"] = "CRITICAL"
