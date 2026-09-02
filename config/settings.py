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
# `"test" in sys.argv` cobria só `manage.py test`. O CI roda pytest, e sem a
# segunda condição o bloco `if IS_TEST` mais abaixo nunca valia para a suíte:
# ela rodava com o hasher de produção e com o HEALTHZ_TOKEN do ambiente.
IS_TEST = "test" in sys.argv or Path(sys.argv[0]).name.startswith(("pytest", "py.test"))


def env_bool(nome, default=False):
    return os.getenv(nome, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(nome, default=""):
    return [item.strip() for item in os.getenv(nome, default).split(",") if item.strip()]


DEFAULT_SECRET_KEY = "dev-only-insecure-secret-key-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY)

if IS_PRODUCTION and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise RuntimeError("Defina DJANGO_SECRET_KEY em produção.")

DEBUG = False
DEBUG_EXPOSE_MEDIA = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    # O unfold precisa vir antes do admin: é assim que os templates dele
    # sobrescrevem os do django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "usuarios",
    "financeiro",
    "legal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_headers.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Depois do Authentication (precisa de request.user) e antes das views:
    # nova versão dos termos bloqueia o uso até ser aceita.
    "legal.middleware.AceiteObrigatorioMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

UNFOLD = {
    "SITE_TITLE": "StölbenFinanças",
    "SITE_HEADER": "StölbenFinanças",
    "SITE_SUBHEADER": "Administração",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        # Verde do DS, para não parecer o admin de outro sistema.
        #
        # A rampa é a do verde padrão deslocada um degrau a partir do 600. O
        # unfold usa `primary-600` como fundo de botão com texto branco, e o
        # 600 original (5 150 105) dá 3,77:1 — abaixo dos 4,5:1 que o WCAG AA
        # exige para texto normal, e o axe reprova a tela de login do admin por
        # isso. O 700 do mesmo verde (4 120 87) dá 5,48:1, então o conserto é
        # escurecer a metade escura da rampa, não trocar de cor. A metade clara
        # fica como estava: ela não serve de fundo para texto branco.
        "primary": {
            "50": "236 253 245",
            "100": "209 250 229",
            "200": "167 243 208",
            "300": "110 231 183",
            "400": "52 211 153",
            "500": "16 185 129",
            "600": "4 120 87",
            "700": "6 95 70",
            "800": "6 78 59",
            "900": "2 44 34",
            "950": "1 31 24",
        },
    },
}

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
                "financeiro.context_processors.compartilhamentos_pendentes",
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
            "NAME": str(BASE_DIR / "db.sqlite3"),
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

# O Usuario não tem `groups` nem `user_permissions`; o backend padrão tentaria
# consultá-los ao avaliar has_perm(). Ver usuarios/auth_backends.py.
AUTHENTICATION_BACKENDS = ["usuarios.auth_backends.UsuarioModelBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Destino após o aceite nas telas do app `legal`. Existe para o app não
# depender de uma rota chamada `dashboard`, que não há em todos os projetos.
LEGAL_REDIRECT_URL = "dashboard"

# Para onde a tela de aceite de visitante posta, e o que aquela view espera.
# Aqui a criação do visitante vive no ramo `entrar_visitante` do LoginView.
LEGAL_VISITOR_ACTION = "login"
LEGAL_VISITOR_EXTRA = {"entrar_visitante": "1"}
HEALTHZ_TOKEN = os.getenv("DJANGO_HEALTHZ_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MENTORIA_MODEL = os.getenv("ANTHROPIC_MENTORIA_MODEL", "claude-opus-4-8").strip()
ANTHROPIC_TIMEOUT_SECONDS = int(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "60"))
AI_MENTORIA_ENABLED = os.getenv("AI_MENTORIA_ENABLED", "true").strip().lower() == "true"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.getenv("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

USE_MANIFEST_STATICFILES = env_bool("DJANGO_USE_MANIFEST_STATICFILES", default=IS_PRODUCTION)

if USE_MANIFEST_STATICFILES:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
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

ADMIN_PATH_PREFIX = "/admin/"

# Política exclusiva do admin. O 'unsafe-eval' é exigido pelo Alpine.js que o
# django-unfold usa: ele compila as expressões de `x-data`/`x-init` com
# `new Function()`. Sem isso o painel carrega sem menu, abas nem tema. A
# concessão fica presa ao /admin/, que só `is_staff` alcança — o app público
# continua sob a política estrita acima.
CONTENT_SECURITY_POLICY_ADMIN = os.getenv(
    "DJANGO_CONTENT_SECURITY_POLICY_ADMIN",
    "default-src 'self'; img-src 'self' data: blob:; "
    "script-src 'self' 'unsafe-eval' 'nonce-{nonce}'; "
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
    SECURE_SSL_REDIRECT = False
    HEALTHZ_TOKEN = ""
    PASSWORD_HASHERS = [
        "core.hashers.PBKDF2RapidoParaTestes",
    ]
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "padrao",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# ==============================================================================
# Monitoramento de erros (Sentry) — ativo só quando SENTRY_DSN está definido.
# ==============================================================================

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
# `not IS_TEST` porque o .env é lido em qualquer execução local, inclusive a
# da suíte, e traz o DSN de produção: sem isso, rodar os testes na máquina
# manda evento de verdade para o projeto do Sentry. Na CI não aparece — lá o
# .env não existe — o que torna o problema invisível para quem não roda local.
if SENTRY_DSN and not IS_TEST:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE") or None,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            send_default_pii=False,
        )
    except Exception:
        # Pacote ausente ou integração indisponível (ex.: Celery não instalado):
        # seguimos sem monitoramento, sem quebrar o app.
        pass
