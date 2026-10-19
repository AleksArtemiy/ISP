from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.test_support import Stage1DataMixin
from .models import LoginThrottle, Role, User
from .permissions import can_access_admin_panel


class AuthenticationTests(Stage1DataMixin, TestCase):
    def test_login_roles_redirect_and_system_flags_unchanged(self):
        for user, target in ((self.admin, reverse('admin_panel:admin_panel')),
                             (self.system, reverse('admin_panel:admin_panel')),
                             (self.committee, reverse('committee_dashboard')),
                             (self.director, reverse('institution_dashboard', args=[self.inst.pk]))):
            self.client.logout()
            response = self.client.post('/login/', {'email': user.email, 'password': 'Valid-Stage1-Pass!42'})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], target)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)

    def test_unknown_wrong_password_and_inactive_have_same_message(self):
        self.director.is_active = False
        self.director.save()
        cases = (("missing@example.test", "incorrect"), (self.committee.email, "incorrect"),
                 (self.director.email, "Valid-Stage1-Pass!42"))
        messages = []
        for email, password in cases:
            response = self.client.post('/login/', {'email': email, 'password': password})
            self.assertEqual(response.status_code, 200)
            messages.append([str(m) for m in response.context['messages']])
            self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(messages, [["Неверный email или пароль."]] * 3)

    def test_bad_role_or_missing_institution_does_not_log_in(self):
        for user in (self.unknown, self.unassigned):
            response = self.client.post('/login/', {'email': user.email, 'password': 'Valid-Stage1-Pass!42'})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_account_rate_limit_applies_across_ips_and_expires(self):
        for index in range(5):
            response = self.client.post('/login/', {'email': self.committee.email, 'password': 'bad'}, REMOTE_ADDR=f'127.0.0.{index+1}')
            self.assertEqual(response.status_code, 200)
        blocked = self.client.post('/login/', {'email': self.committee.email, 'password': 'Valid-Stage1-Pass!42'})
        self.assertEqual(blocked.status_code, 429)
        self.assertIn('Retry-After', blocked)
        self.assertNotIn('_auth_user_id', self.client.session)
        LoginThrottle.objects.update(started_at=timezone.now()-timedelta(minutes=16))
        self.assertEqual(self.client.post('/login/', {'email': self.committee.email, 'password': 'Valid-Stage1-Pass!42'}).status_code, 302)

    def test_ip_rate_limit_applies_to_different_account_names(self):
        for index in range(30):
            self.assertEqual(self.client.post('/login/', {'email': f'unknown{index}@example.test', 'password': 'bad'}).status_code, 200)
        self.assertEqual(self.client.post('/login/', {'email': 'next@example.test', 'password': 'bad'}).status_code, 429)

    def test_logout_requires_post_and_csrf(self):
        self.client.force_login(self.committee)
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.committee)
        self.assertEqual(secure_client.post('/logout/').status_code, 403)
        self.assertEqual(self.client.post('/logout/').status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_application_admin_has_no_django_admin_access(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin-panel/').status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        for user in (self.committee, self.director, self.unknown, self.unassigned):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/admin-panel/').status_code, 403)

    def test_inactive_admin_denied_by_permission_layer(self):
        self.admin.is_active = False
        self.assertFalse(can_access_admin_panel(self.admin))

    def test_superuser_manager_rejects_false_system_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser('invalid@example.test', is_staff=False)

    def test_standard_django_admin_user_pages(self):
        self.client.force_login(self.system)
        self.assertEqual(self.client.get('/admin/accounts/user/').status_code, 200)
        self.assertEqual(self.client.get('/admin/accounts/user/add/').status_code, 200)

    def test_system_role_identity_cannot_be_deleted_in_admin(self):
        self.client.force_login(self.system)
        role = self.roles['ADMIN']
        self.assertEqual(self.client.post(f'/admin/accounts/role/{role.pk}/delete/', {'post': 'yes'}).status_code, 403)
        self.assertTrue(Role.objects.filter(pk=role.pk, code='ADMIN').exists())
