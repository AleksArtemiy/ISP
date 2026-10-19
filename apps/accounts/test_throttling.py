import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from apps.test_support import Stage1DataMixin
from .models import LoginThrottle, User
from .throttling import (
    ACCOUNT_LIMIT, CLEANUP_BATCH_SIZE, IP_LIMIT, WINDOW,
    cleanup_expired_counters, login_keys, release_login_attempt, reserve_login_attempt,
)


class LoginThrottleTests(Stage1DataMixin, TestCase):
    def request(self, remote="192.0.2.10"):
        return RequestFactory().post("/login/", REMOTE_ADDR=remote)

    def test_forty_successful_users_behind_one_nat_do_not_spend_budget(self):
        for index in range(40):
            user = User.objects.create_user(
                f"nat{index}@example.test", "Valid-Stage1-Pass!42",
                role=self.roles["COMMITTEE"],
            )
            client = Client()
            response = client.post(
                "/login/" if index % 2 else "/accounts/login/",
                {"email": user.email, "password": "Valid-Stage1-Pass!42"},
                REMOTE_ADDR="192.0.2.10",
            )
            self.assertEqual(response.status_code, 302, index)
            self.assertEqual(client.session["_auth_user_id"], str(user.pk))
        self.assertFalse(LoginThrottle.objects.exclude(attempts=0).exists())
        self.assertEqual(LoginThrottle.objects.count(), 41)

    def test_success_refunds_only_its_own_reservation_not_other_failures(self):
        request = self.request()
        failed = reserve_login_attempt(request, self.committee.email)
        successful = reserve_login_attempt(request, self.committee.email)
        release_login_attempt(successful)
        for counter in failed.counters:
            self.assertEqual(LoginThrottle.objects.get(pk=counter.key).attempts, 1)
        # A valid password at the application endpoint refunds both counters.
        response = self.client.post("/login/", {
            "email": self.committee.email, "password": "Valid-Stage1-Pass!42",
        }, REMOTE_ADDR="192.0.2.10")
        self.assertEqual(response.status_code, 302)
        for counter in failed.counters:
            self.assertEqual(LoginThrottle.objects.get(pk=counter.key).attempts, 1)

    def test_success_cannot_erase_near_exhausted_shared_nat_budget(self):
        request = self.request()
        ip_key = login_keys(request, self.committee.email)[1][0]
        LoginThrottle.objects.create(key=ip_key, attempts=IP_LIMIT - 1, started_at=timezone.now())
        for _ in range(40):
            self.client.logout()
            response = self.client.post("/login/", {
                "email": self.committee.email, "password": "Valid-Stage1-Pass!42",
            }, REMOTE_ADDR="192.0.2.10")
            self.assertEqual(response.status_code, 302)
        self.assertEqual(LoginThrottle.objects.get(pk=ip_key).attempts, IP_LIMIT - 1)
        self.assertIsNotNone(reserve_login_attempt(request, "unknown@example.invalid"))
        self.assertIsNone(reserve_login_attempt(request, "another@example.invalid"))

    def test_random_email_flood_creates_only_one_ip_counter(self):
        request = self.request()
        for index in range(IP_LIMIT + 20):
            attempt = reserve_login_attempt(request, f"random{index}@example.invalid")
            self.assertEqual(attempt is not None, index < IP_LIMIT)
        self.assertEqual(LoginThrottle.objects.count(), 1)
        self.assertEqual(LoginThrottle.objects.get().attempts, IP_LIMIT)

    def test_expired_counters_pruned_on_login_and_idle_cleanup_command(self):
        now = timezone.now()
        LoginThrottle.objects.bulk_create([
            LoginThrottle(key=f"{index:064x}", attempts=1, started_at=now - WINDOW)
            for index in range(CLEANUP_BATCH_SIZE + 3)
        ])
        LoginThrottle.objects.create(key="fresh", attempts=2, started_at=now)
        with patch("apps.accounts.throttling.timezone.now", return_value=now):
            self.assertIsNotNone(reserve_login_attempt(self.request(), "absent@example.invalid"))
            self.assertEqual(LoginThrottle.objects.filter(started_at__lte=now - WINDOW).count(), 3)
            output = io.StringIO()
            call_command("cleanup_login_counters", stdout=output)
        self.assertIn("Deleted expired login counters: 3", output.getvalue())
        self.assertEqual(LoginThrottle.objects.get(pk="fresh").attempts, 2)
        self.assertFalse(LoginThrottle.objects.filter(started_at__lte=now - WINDOW).exists())
        with patch("apps.accounts.throttling.timezone.now", return_value=now + WINDOW):
            call_command("cleanup_login_counters", stdout=io.StringIO())
        self.assertFalse(LoginThrottle.objects.exists())

    def test_slow_success_does_not_refund_a_recreated_window(self):
        now = timezone.now()
        with patch("apps.accounts.throttling.timezone.now", return_value=now):
            old = reserve_login_attempt(self.request(), self.committee.email)
        with patch("apps.accounts.throttling.timezone.now", return_value=now + WINDOW):
            new = reserve_login_attempt(self.request(), self.committee.email)
        release_login_attempt(old)
        for counter in new.counters:
            self.assertEqual(LoginThrottle.objects.get(pk=counter.key).attempts, 1)

    def test_proxy_header_only_used_from_a_trusted_proxy(self):
        request = self.request()
        keys = login_keys(request, self.committee.email)
        request.META["HTTP_X_REAL_IP"] = "203.0.113.15"
        self.assertEqual(login_keys(request, self.committee.email), keys)
        with self.settings(TRUSTED_PROXY_IPS=["192.0.2.10"]):
            self.assertNotEqual(login_keys(request, self.committee.email)[1], keys[1])

    def test_ttl_index_exists_in_postgresql(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, LoginThrottle._meta.db_table)
        self.assertEqual(constraints["login_throttle_ttl_idx"]["columns"], ["started_at"])

    def test_admin_login_shares_account_budget_and_skips_password_hash_when_blocked(self):
        for _ in range(ACCOUNT_LIMIT):
            self.assertEqual(self.client.post("/login/", {
                "email": self.system.email, "password": "bad",
            }).status_code, 200)
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.client.post("/admin/login/", {
                "username": self.system.email, "password": "Valid-Stage1-Pass!42",
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Слишком много попыток")
        authenticate.assert_not_called()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_success_and_nonstaff_correct_password_do_not_spend_budget(self):
        for user in (self.system, self.committee):
            for _ in range(40):
                client = Client()
                response = client.post("/admin/login/", {
                    "username": user.email, "password": "Valid-Stage1-Pass!42",
                })
                self.assertEqual(response.status_code, 302 if user.is_staff else 200)
        self.assertFalse(LoginThrottle.objects.exclude(attempts=0).exists())


class LoginThrottleConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.email = "parallel@example.test"
        User.objects.create_user(self.email, "Valid-Stage1-Pass!42")

    def reserve(self, index):
        close_old_connections()
        try:
            request = RequestFactory().post("/login/", REMOTE_ADDR=f"192.0.2.{index + 1}")
            return reserve_login_attempt(request, self.email)
        finally:
            close_old_connections()

    def test_parallel_workers_cannot_overrun_account_budget(self):
        with ThreadPoolExecutor(max_workers=8) as workers:
            attempts = list(workers.map(self.reserve, range(12)))
        self.assertEqual(sum(attempt is not None for attempt in attempts), ACCOUNT_LIMIT)
        self.assertEqual(max(LoginThrottle.objects.values_list("attempts", flat=True)), ACCOUNT_LIMIT)

    def test_cleanup_skips_counters_locked_by_another_worker(self):
        from django.db import transaction
        LoginThrottle.objects.create(key="locked", started_at=timezone.now() - WINDOW)
        with transaction.atomic():
            LoginThrottle.objects.select_for_update().get(pk="locked")
            with ThreadPoolExecutor(max_workers=1) as workers:
                def cleanup():
                    close_old_connections()
                    try:
                        return cleanup_expired_counters()
                    finally:
                        close_old_connections()
                self.assertEqual(workers.submit(cleanup).result(timeout=10), 0)
        self.assertEqual(cleanup_expired_counters(), 1)

    def test_forty_inflight_nat_reservations_all_refund_across_workers(self):
        request = RequestFactory().post("/login/", REMOTE_ADDR="192.0.2.100")
        attempts = []
        for index in range(40):
            user = User.objects.create_user(f"parallel-nat{index}@example.test")
            attempt = reserve_login_attempt(request, user.email)
            self.assertIsNotNone(attempt)
            attempts.append(attempt)
        ip_key = login_keys(request, self.email)[1][0]
        self.assertEqual(LoginThrottle.objects.get(pk=ip_key).attempts, 40)

        def refund(attempt):
            close_old_connections()
            try:
                release_login_attempt(attempt)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(refund, attempts))
        self.assertFalse(LoginThrottle.objects.exclude(attempts=0).exists())
