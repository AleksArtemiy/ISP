from datetime import timedelta
from ipaddress import ip_address

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginThrottle


WINDOW = timedelta(minutes=15)


def login_keys(request, email):
    remote = request.META.get("REMOTE_ADDR", "")
    if remote in getattr(settings, "TRUSTED_PROXY_IPS", []):
        remote = request.META.get("HTTP_X_REAL_IP", remote)
    try:
        remote = str(ip_address(remote))
    except ValueError:
        remote = "unknown"
    return [(salted_hmac("login-account", email.casefold(), algorithm="sha256").hexdigest(), 5),
            (salted_hmac("login-ip", remote, algorithm="sha256").hexdigest(), 30)]


def reserve_login_attempt(request, email):
    """Serialize counters across workers; count attempts before authentication."""
    now = timezone.now()
    keys = login_keys(request, email)
    with transaction.atomic():
        locked = []
        for key, limit in sorted(keys):
            LoginThrottle.objects.get_or_create(key=key, defaults={"started_at": now})
            row = LoginThrottle.objects.select_for_update().get(key=key)
            if row.started_at <= now - WINDOW:
                row.attempts, row.started_at = 0, now
            locked.append((row, limit))
        if any(row.attempts >= limit for row, limit in locked):
            return False
        for row, _ in locked:
            row.attempts += 1
            row.save(update_fields=["attempts", "started_at"])
    return True


def reset_account_counter(request, email):
    # A successful login resets only this account; the IP flood limit remains.
    key = login_keys(request, email)[0][0]
    LoginThrottle.objects.filter(key=key).update(attempts=0)
