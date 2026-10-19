"""
Django settings for the "Реестр предписаний" project.

Настройки приложения загружаются из переменных окружения.
Для локальной разработки переменные могут храниться в файле .env.

Файл .env не должен попадать в систему контроля версий.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Локальный .env используется прежде всего для разработки.
# Системные переменные окружения имеют приоритет над .env.
load_dotenv(BASE_DIR / ".env", override=False)


# ============================================================
# Helpers
# ============================================================

def env_bool(name: str, default: bool = False) -> bool:
    """
    Возвращает boolean-значение переменной окружения.

    True:
        1, true, yes, on

    False:
        0, false, no, off
    """
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    """
    Преобразует строку вида:

        value1,value2,value3

    в список непустых значений.
    """
    value = os.getenv(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


# ============================================================
# Environment
# ============================================================

ENVIRONMENT = os.getenv(
    "DJANGO_ENV",
    "development",
).strip().lower()

IS_PRODUCTION = ENVIRONMENT == "production"


# ============================================================
# Core security
# ============================================================

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "Переменная окружения DJANGO_SECRET_KEY не задана. "
        "Создайте файл .env на основе .env.example "
        "или задайте переменную окружения средствами ОС."
    )


# В production DEBUG принудительно отключён,
# независимо от содержимого переменной окружения.
if IS_PRODUCTION:
    DEBUG = False
else:
    DEBUG = env_bool(
        "DJANGO_DEBUG",
        default=True,
    )


ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default="127.0.0.1,localhost",
)

if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise RuntimeError(
        "Для production необходимо задать DJANGO_ALLOWED_HOSTS."
    )


CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
)


# ============================================================
# Applications
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Project applications
    "apps.accounts",
    "apps.institutions",
    "apps.prescriptions",
    "apps.funding",
    "apps.notifications",
    "apps.audit",
    "apps.dashboard",
    "apps.admin_panel",
]


# ============================================================
# Middleware
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URL / WSGI
# ============================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# Templates
# ============================================================

TEMPLATES_DIR = BASE_DIR / "templates"

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [
            TEMPLATES_DIR,
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.user_role",
            ],
        },
    },
]


# ============================================================
# Database
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv(
            "DB_NAME",
            "minobr",
        ),
        "USER": os.getenv(
            "DB_USER",
            "postgres",
        ),
        "PASSWORD": os.getenv(
            "DB_PASSWORD",
            "",
        ),
        "HOST": os.getenv(
            "DB_HOST",
            "localhost",
        ),
        "PORT": os.getenv(
            "DB_PORT",
            "5432",
        ),
    }
}


# ============================================================
# Authentication
# ============================================================

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/login/"


# ============================================================
# Password validation
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# Internationalization
# ============================================================

LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


# ============================================================
# Static files
# ============================================================

STATIC_URL = "/static/"

STATIC_DIR = BASE_DIR / "static"

STATICFILES_DIRS = [
    STATIC_DIR,
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# ============================================================
# Media
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# Django model defaults
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# Security headers / cookies
# ============================================================

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = "same-origin"


# ============================================================
# Production security
# ============================================================

if IS_PRODUCTION:
    # В production приложение должно использовать HTTPS.
    SECURE_SSL_REDIRECT = env_bool(
        "DJANGO_SECURE_SSL_REDIRECT",
        default=True,
    )

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True

    SESSION_COOKIE_HTTPONLY = True

    CSRF_COOKIE_HTTPONLY = True

    # Если Django находится за Nginx / reverse proxy,
    # Django должен корректно распознавать HTTPS.
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    # Начинаем с небольшого HSTS.
    # После проверки production-инфраструктуры
    # значение можно увеличить до 31536000.
    SECURE_HSTS_SECONDS = int(
        os.getenv(
            "DJANGO_SECURE_HSTS_SECONDS",
            "3600",
        )
    )

    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

    SECURE_HSTS_PRELOAD = False

else:
    # Локальная разработка работает по HTTP.
    SECURE_SSL_REDIRECT = False

    SESSION_COOKIE_SECURE = False

    CSRF_COOKIE_SECURE = False

    SECURE_HSTS_SECONDS = 0


# ============================================================
# Error handlers
# ============================================================

handler403 = "django.views.defaults.permission_denied"