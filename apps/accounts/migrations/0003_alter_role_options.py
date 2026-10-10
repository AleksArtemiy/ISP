from django.db import migrations


class Migration(migrations.Migration):
    """
    Синхронизирует Meta-настройки модели Role
    с состоянием миграций Django.

    Миграция не изменяет физическую структуру таблицы roles
    и не затрагивает существующие данные.

    Таблица roles остаётся внешней для Django:
    managed=False.
    """

    dependencies = [
        ("accounts", "0002_role_code_nullable"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="role",
            options={
                "managed": False,
                "verbose_name": "Роль",
                "verbose_name_plural": "Роли",
            },
        ),
    ]