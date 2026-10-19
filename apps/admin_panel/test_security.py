from django.test import TestCase
from django.urls import reverse

from apps.test_support import Stage1DataMixin
from .forms import UserForm


class UserPolicyTests(Stage1DataMixin, TestCase):
    def payload(self, password='Fortress!Birch-9472', **extra):
        result = {'email': 'user@example.test', 'first_name': 'Alexander', 'last_name': 'Petrov',
                  'role': self.roles['COMMITTEE'].pk, 'password': password,
                  'password_confirm': password, 'is_active': True}
        result.update(extra)
        return result

    def test_password_validators_reject_short_common_numeric_and_similar(self):
        for password in ('aA!2', 'password', '5839405823048', 'AlexanderPetrov'):
            with self.subTest(password=password):
                form = UserForm(self.payload(password))
                self.assertFalse(form.is_valid())
                self.assertIn('password', form.errors)

    def test_valid_password_saved_as_hash(self):
        form = UserForm(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password('Fortress!Birch-9472'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_edit_without_password_preserves_hash(self):
        old = self.committee.password
        form = UserForm(self.payload('', email=self.committee.email), instance=self.committee)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().password, old)

    def test_director_requires_institution(self):
        form = UserForm(self.payload(role=self.roles['DIRECTOR'].pk))
        self.assertFalse(form.is_valid())
        self.assertIn('institution', form.errors)

    def test_application_admin_cannot_reset_deactivate_or_read_system_user(self):
        self.client.force_login(self.admin)
        for action in ('admin_user_edit', 'admin_user_delete'):
            url = reverse('admin_panel:' + action, args=[self.system.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, self.payload()).status_code, 404)
        self.system.refresh_from_db()
        self.assertTrue(self.system.is_active)
        self.assertTrue(self.system.check_password('Valid-Stage1-Pass!42'))
