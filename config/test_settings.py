"""Isolated PostgreSQL checks. Never load the developer's .env or working DB."""
import os

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DJANGO_ENV"] = "development"
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-stage1-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz")

from .settings import *  # noqa: E402,F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("TEST_DB_NAME", "minobr_stage1_audit"),
    "USER": os.getenv("TEST_DB_USER", "stage1_test"),
    "PASSWORD": os.getenv("TEST_DB_PASSWORD", ""),
    "HOST": os.getenv("TEST_DB_HOST", "127.0.0.1"),
    "PORT": os.getenv("TEST_DB_PORT", "55432"),
}}
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = BASE_DIR / ".stage1" / "test_media"  # noqa: F405
DEBUG = False
LOGGING['loggers']['django']['level'] = 'CRITICAL'  # noqa: F405
