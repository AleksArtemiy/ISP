from django.db import migrations


ROLE_CODE_MAPPING = {
    "admin": "ADMIN",
    "committee": "COMMITTEE",
    "director": "DIRECTOR",
}


def populate_role_codes(apps, schema_editor):
    """
    Заполняет коды существующих ролей и создаёт недостающие системные роли.

    Ожидаемые роли в текущей базе данных:

        admin     -> ADMIN
        committee -> COMMITTEE
        director  -> DIRECTOR

    Миграция работает через историческую модель Django,
    полученную через apps.get_model(), а не через импорт
    текущей модели приложения.

    Цепочка исправлена до ввода в эксплуатацию: следующая миграция не могла
    бы устранить ошибку установки, возникающую до её запуска. Уже применённые
    миграции повторно не выполняются. Идентификаторы ролей сохраняются.
    Перед обновлением выполняется проверка существующих ролей.
    Если обнаружена неизвестная роль, миграция прерывается,
    чтобы неизвестному значению не был назначен ошибочный код.
    """

    Role = apps.get_model("accounts", "Role")

    roles = Role.objects.using(schema_editor.connection.alias)
    by_code = {}
    for role in roles.all():
        mapped = ROLE_CODE_MAPPING.get((role.name or "").strip().lower())
        code = role.code or mapped
        if code not in ROLE_CODE_MAPPING.values() or (mapped and mapped != code):
            raise RuntimeError(f"Неоднозначная системная роль id={role.pk}; требуется проверка данных.")
        if code in by_code:
            raise RuntimeError(f"Дублирующиеся роли с кодом {code}; требуется проверка данных.")
        by_code[code] = role

    # Validate every existing row before writing. Preserve all IDs and user FKs.
    for name, code in ROLE_CODE_MAPPING.items():
        if code in by_code:
            roles.filter(pk=by_code[code].pk).update(code=code)
        else:
            roles.create(name=name, code=code)


def clear_role_codes(apps, schema_editor):
    """
    Обратная операция миграции.

    При откате очищает программные коды только у трёх
    известных системных ролей.
    """

    Role = apps.get_model("accounts", "Role")

    Role.objects.using(schema_editor.connection.alias).filter(
        code__in=[
            "ADMIN",
            "COMMITTEE",
            "DIRECTOR",
        ]
    ).update(
        code=None,
    )


class Migration(migrations.Migration):
    """
    Второй этап внедрения стабильных кодов ролей.

    Миграция заполняет поле code существующих записей,
    но пока не устанавливает ограничения NOT NULL и UNIQUE.

    Ограничения будут добавлены отдельным этапом после проверки,
    что все существующие данные заполнены корректно.
    """

    dependencies = [
        ("accounts", "0003_alter_role_options"),
    ]

    operations = [
        migrations.RunPython(
            populate_role_codes,
            reverse_code=clear_role_codes,
        ),
    ]
