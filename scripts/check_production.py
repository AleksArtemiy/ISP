"""Production-like settings gate, with no .env or live database access."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update({
    'DJANGO_SETTINGS_MODULE': 'config.settings', 'PYTHON_DOTENV_DISABLED': '1',
    'DJANGO_ENV': 'production', 'DJANGO_SECRET_KEY': 'test-only-security-check-0123456789-abcdefghijklmnopqrstuvwxyz-!@#',
    'DJANGO_ALLOWED_HOSTS': 'minobr.example.test',
    'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://minobr.example.test',
    'DJANGO_SECURE_SSL_REDIRECT': 'True', 'DJANGO_SECURE_HSTS_SECONDS': '3600',
    'DB_USER': 'minobr_app', 'DB_NAME': 'security_check_unused',
    'DB_HOST': '127.0.0.1', 'DB_PORT': '55432', 'DB_PASSWORD': '',
})
import django
django.setup()
from django.core.management import call_command
from django.core.checks import run_checks

call_command('check', deploy=True)
# Do not silently enable HSTS for unknown subdomains or submit a preload policy.
allowed = {'security.W005', 'security.W021'}
unexplained = [item for item in run_checks(include_deployment_checks=True) if item.id not in allowed]
if unexplained:
    raise SystemExit('\n'.join(str(item) for item in unexplained))
print('Production-like settings checked. HSTS subdomains/preload require infrastructure approval.')
