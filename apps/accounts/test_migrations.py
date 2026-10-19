from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.db.migrations.executor import MigrationExecutor

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


class LegacyMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        self.before = [('accounts', '0003_alter_role_options')]
        executor.migrate(self.before)
        self.old_apps = executor.loader.project_state(self.before).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.latest)

    def test_existing_nullable_role_codes_preserve_user_and_role_ids(self):
        LegacyRole = self.old_apps.get_model('accounts', 'Role')
        LegacyUser = self.old_apps.get_model('accounts', 'User')
        for name in ('admin', 'committee', 'director'):
            LegacyRole.objects.get_or_create(name=name)
        LegacyRole.objects.update(code=None)
        role = LegacyRole.objects.get(name='director')
        user = LegacyUser.objects.create(email='legacy@example.test', first_name='Legacy', last_name='User',
                                         password='test-only-unusable', role=role)
        ids = set(LegacyRole.objects.values_list('id', flat=True))
        MigrationExecutor(connection).migrate(self.latest)
        user = User.objects.get(pk=user.pk)
        self.assertEqual(user.role_id, role.pk)
        self.assertEqual(user.role.code, 'DIRECTOR')
        self.assertSetEqual(set(Role.objects.values_list('id', flat=True)), ids)

    def test_empty_legacy_roles_are_created(self):
        LegacyRole = self.old_apps.get_model('accounts', 'Role')
        LegacyRole.objects.all().delete()
        MigrationExecutor(connection).migrate(self.latest)
        self.assertSetEqual(set(Role.objects.values_list('code', flat=True)), set(Role.Code.values))
