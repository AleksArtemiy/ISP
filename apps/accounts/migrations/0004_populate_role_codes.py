from django.db import migrations


ROLE_CODE_MAPPING = {
    "admin": "ADMIN",
    "committee": "COMMITTEE",
    "director": "DIRECTOR",
}


def populate_role_codes(apps, schema_editor):
    """
    Заполняет стабильные программные коды существующих ролей.

    Ожидаемые роли в текущей базе данных:

        admin     -> ADMIN
        committee -> COMMITTEE
        director  -> DIRECTOR

    Миграция работает через историческую модель Django,
    полученную через apps.get_model(), а не через импорт
    текущей модели приложения.

    Перед обновлением выполняется проверка существующих ролей.
    Если обнаружена неизвестная роль, миграция прерывается,
    чтобы неизвестному значению не был назначен ошибочный код.
    """

    Role = apps.get_model("accounts", "Role")

    roles = list(
        Role.objects.all().values(
            "id",
            "name",
            "code",
        )
    )

    unknown_roles = []

    for role in roles:
        normalized_name = (role["name"] or "").strip().lower()

        if normalized_name not in ROLE_CODE_MAPPING:
            unknown_roles.append(
                f"id={role['id']}, name={role['name']!r}"
            )

    if unknown_roles:
        raise RuntimeError(
            "Обнаружены неизвестные роли. "
            "Миграция Role.code остановлена. "
            "Неизвестные записи: "
            + "; ".join(unknown_roles)
        )

    for role_name, role_code in ROLE_CODE_MAPPING.items():
        updated = Role.objects.filter(
            name__iexact=role_name,
        ).update(
            code=role_code,
        )

        if updated != 1:
            raise RuntimeError(
                "Ожидалась ровно одна роль "
                f"{role_name!r}, но обновлено записей: {updated}."
            )


def clear_role_codes(apps, schema_editor):
    """
    Обратная операция миграции.

    При откате очищает программные коды только у трёх
    известных системных ролей.
    """

    Role = apps.get_model("accounts", "Role")

    Role.objects.filter(
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