import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


ENV_FILE = os.getenv("DJANGO_ENV_FILE", "").strip()

if ENV_FILE:
    load_env_file(Path(ENV_FILE))
else:
    load_env_file(BASE_DIR / ".env")
    load_env_file(Path("/var/www/sistema_financas/shared/.env"))

ENV = os.getenv("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"
IS_TEST = "test" in sys.argv


def env_bool(nome, default=False):
    return os.getenv(nome, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(nome, default=""):
    return [item.strip() for item in os.getenv(nome, default).split(",") if item.strip()]


DEFAULT_SECRET_KEY = "dev-only-insecure-secret-key-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY)

if IS_PRODUCTION and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise RuntimeError("Defina DJANGO_SECRET_KEY em produção.")

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)
DEBUG_EXPOSE_MEDIA = env_bool("DJANGO_DEBUG_EXPOSE_MEDIA", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "usuarios",
    "financeiro",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_headers.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_CONN_MAX_AGE = int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60"))
DB_SSL_REQUIRE = env_bool("DJANGO_DB_SSL_REQUIRE", default=IS_PRODUCTION)

if DATABASE_URL:
    try:
        import dj_database_url
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL foi definido, mas a dependência 'dj-database-url' não está instalada."
        ) from exc

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=DB_CONN_MAX_AGE,
            ssl_require=DB_SSL_REQUIRE,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                "timeout": int(os.getenv("SQLITE_TIMEOUT", "20")),
            },
        }
    }

CACHE_BACKEND = os.getenv("DJANGO_CACHE_BACKEND", "").strip().lower()
REDIS_CACHE_URL = os.getenv("DJANGO_REDIS_CACHE_URL", "").strip()

if CACHE_BACKEND == "redis" or REDIS_CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_CACHE_URL or "redis://127.0.0.1:6379/1",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sistema-financas-cache",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
DATE_FORMAT = "d/m/Y"
SHORT_DATE_FORMAT = "d/m/Y"

AUTH_USER_MODEL = "usuarios.Usuario"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
HEALTHZ_TOKEN = os.getenv("DJANGO_HEALTHZ_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MENTORIA_MODEL = os.getenv("OPENAI_MENTORIA_MODEL", "gpt-5-mini").strip()
OPENAI_MENTORIA_FALLBACK_MODEL = os.getenv("OPENAI_MENTORIA_FALLBACK_MODEL", "gpt-4.1-mini").strip()
OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "45"))

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

USE_MANIFEST_STATICFILES = env_bool(
    "DJANGO_USE_MANIFEST_STATICFILES", default=IS_PRODUCTION
)

if USE_MANIFEST_STATICFILES:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        },
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv(
    "DJANGO_MEDIA_ROOT",
    "/var/www/sistema_financas/shared/media" if IS_PRODUCTION else str(BASE_DIR / "media"),
)

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.getenv(
    "DJANGO_SECURE_CROSS_ORIGIN_OPENER_POLICY", "same-origin"
)
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = os.getenv(
    "DJANGO_SECURE_CROSS_ORIGIN_RESOURCE_POLICY", "same-origin"
)

if env_bool("DJANGO_USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ENABLE_CSP = env_bool("DJANGO_ENABLE_CSP", default=IS_PRODUCTION)
CONTENT_SECURITY_POLICY = os.getenv(
    "DJANGO_CONTENT_SECURITY_POLICY",
    "default-src 'self'; img-src 'self' data: blob:; script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'unsafe-inline'; font-src 'self' data:; object-src 'none'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
)

if IS_PRODUCTION:
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", True)
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

if IS_TEST:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}
