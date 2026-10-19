from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from .models import Role, User


class RoleSeedingTests(TestCase):
    def seed(self):
        import_module("apps.accounts.migrations.0004_populate_role_codes").populate_role_codes(
            apps, SimpleNamespace(connection=connection),
        )

    def test_migrations_seed_all_system_roles(self):
        self.assertSetEqual(set(Role.objects.values_list("code", flat=True)), set(Role.Code.values))

    def test_seeding_is_idempotent_and_preserves_user_and_role_ids(self):
        role = Role.objects.get(code=Role.Code.DIRECTOR)
        user = User.objects.create_user("seed@example.test", role=role)
        before = list(Role.objects.values_list("pk", "code").order_by("pk"))
        self.seed()
        self.seed()
        user.refresh_from_db()
        self.assertEqual(user.role_id, role.pk)
        self.assertEqual(before, list(Role.objects.values_list("pk", "code").order_by("pk")))

    def test_missing_role_created_without_replacing_existing_roles(self):
        Role.objects.filter(code=Role.Code.ADMIN).delete()
        self.seed()
        self.assertEqual(Role.objects.count(), 3)

    def test_unknown_role_stops_without_changing_existing_data(self):
        Role.objects.create(name="unknown", code="UNKNOWN")
        with self.assertRaises(RuntimeError):
            self.seed()
