from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginThrottle, User


WINDOW = timedelta(minutes=15)
ACCOUNT_LIMIT = 5
# A shared NAT is a flood signal, not an account lockout boundary. Successful
# password checks refund their reservation; the per-account limit stays strict.
IP_LIMIT = 300
CLEANUP_BATCH_SIZE = 500


@dataclass(frozen=True)
class CounterReservation:
    key: str
    started_at: datetime


@dataclass(frozen=True)
class LoginAttempt:
    counters: tuple[CounterReservation, ...]


def login_keys(request, email):
    remote = request.META.get("REMOTE_ADDR", "")
    if remote in getattr(settings, "TRUSTED_PROXY_IPS", []):
        remote = request.META.get("HTTP_X_REAL_IP", remote)
    try:
        remote = str(ip_address(remote))
    except ValueError:
        remote = "unknown"
    return [(salted_hmac("login-account", email.casefold(), algorithm="sha256").hexdigest(), ACCOUNT_LIMIT),
            (salted_hmac("login-ip", remote, algorithm="sha256").hexdigest(), IP_LIMIT)]


def cleanup_expired_counters(*, now=None, batch_size=CLEANUP_BATCH_SIZE):
    """Delete one indexed TTL batch, without waiting for another worker's locks."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    cutoff = (now or timezone.now()) - WINDOW
    with transaction.atomic():
        keys = list(LoginThrottle.objects.select_for_update(skip_locked=True)
                    .filter(started_at__lte=cutoff).order_by("started_at", "key")
                    .values_list("key", flat=True)[:batch_size])
        deleted, _ = LoginThrottle.objects.filter(key__in=keys).delete()
    return deleted


def reserve_login_attempt(request, email):
    """Reserve failure/in-flight budget atomically before expensive hashing.

    Unknown emails share only their IP counter, so random identifiers cannot
    create unbounded account rows. All rows expire after WINDOW; every request
    prunes a bounded batch, and a scheduled command handles idle periods.
    """
    now = timezone.now()
    cleanup_expired_counters(now=now)
    account, ip = login_keys(request, email)
    with transaction.atomic():
        locked = []
        # Always lock IP before account, including when releasing a reservation.
        for key, limit in (ip, account):
            if key == account[0] and not User.objects.filter(email__iexact=email).exists():
                continue
            row, _ = LoginThrottle.objects.select_for_update().get_or_create(
                key=key, defaults={"started_at": now})
            if row.started_at <= now - WINDOW:
                row.attempts, row.started_at = 0, now
            if row.attempts >= limit:
                return None
            locked.append(row)
        for row in locked:
            row.attempts += 1
            row.save(update_fields=["attempts", "started_at"])
        return LoginAttempt(tuple(CounterReservation(row.key, row.started_at) for row in locked))


def release_login_attempt(attempt):
    """Refund only this successful password check, never other attempts.

    The window comparison prevents a slow authentication result from changing
    a counter which has already expired and been recreated by another worker.
    Keep zero rows until TTL rather than racing concurrent reservations/deletes.
    """
    with transaction.atomic():
        for counter in attempt.counters:
            LoginThrottle.objects.filter(
                key=counter.key, started_at=counter.started_at, attempts__gt=0,
            ).update(attempts=F("attempts") - 1)
