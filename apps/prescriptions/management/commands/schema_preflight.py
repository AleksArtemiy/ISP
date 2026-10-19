"""Read-only inspection before upgrading an existing database."""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Проверить таблицы и FK журнала перед обновлением; данные не изменяются.'

    def handle(self, *args, **options):
        problems = []
        expected = {model._meta.db_table for model in apps.get_models(include_auto_created=True)
                    if model._meta.managed and not model._meta.proxy}
        tables = set(connection.introspection.table_names())
        for name in sorted(expected-tables):
            problems.append(f'Отсутствует таблица {name}; сначала проверить историю миграций.')
        if 'django_admin_log' in tables:
            with connection.cursor() as cursor:
                constraints = connection.introspection.get_constraints(cursor, 'django_admin_log')
            for constraint in constraints.values():
                if constraint.get('columns') == ['user_id'] and constraint.get('foreign_key'):
                    if constraint['foreign_key'][0] != 'users':
                        problems.append('django_admin_log.user_id ссылается не на users. Нужна проверка существующих логов и согласованный план миграции.')
        for name in sorted(tables-expected):
            self.stdout.write(f'Дополнительная таблица {name}: назначение/данные проверить отдельно; не удалять.')
        if problems:
            raise CommandError('\n'.join(problems))
        self.stdout.write(self.style.SUCCESS('Проверка обязательных таблиц и FK журнала пройдена.'))
