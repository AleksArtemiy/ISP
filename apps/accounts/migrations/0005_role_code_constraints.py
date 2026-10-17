from django.db import migrations, models
from django.db.models import Count


EXPECTED_ROLE_CODES = {
    "ADMIN",
    "COMMITTEE",
    "DIRECTOR",
}


def validate_role_codes(apps, schema_editor):
    """
    Проверяет существующие роли перед установкой ограничений
    NOT NULL и UNIQUE на поле roles.code.

    Миграция прерывается, если:

    1. существует роль без программного кода;
    2. существуют дублирующиеся программные коды;
    3. обнаружен неизвестный программный код;
    4. отсутствует одна из обязательных системных ролей.

    Проверка выполняется до изменения физической структуры таблицы,
    чтобы при проблемах с данными миграция завершалась безопасно
    и с понятным сообщением об ошибке.
    """

    Role = apps.get_model(
        "accounts",
        "Role",
    )

    roles = list(
        Role.objects.all().values(
            "id",
            "name",
            "code",
        )
    )

    # --------------------------------------------------------
    # Проверка отсутствующих кодов
    # --------------------------------------------------------

    roles_without_code = [
        role
        for role in roles
        if not role["code"]
    ]

    if roles_without_code:
        details = "; ".join(
            (
                f"id={role['id']}, "
                f"name={role['name']!r}"
            )
            for role in roles_without_code
        )

        raise RuntimeError(
            "Невозможно установить NOT NULL для roles.code. "
            "Обнаружены роли без программного кода: "
            + details
        )

    # --------------------------------------------------------
    # Проверка множества кодов
    # --------------------------------------------------------

    actual_codes = {
        role["code"]
        for role in roles
    }

    unknown_codes = actual_codes - EXPECTED_ROLE_CODES

    if unknown_codes:
        raise RuntimeError(
            "Обнаружены неизвестные программные коды ролей: "
            + ", ".join(sorted(unknown_codes))
        )

    missing_codes = EXPECTED_ROLE_CODES - actual_codes

    if missing_codes:
        raise RuntimeError(
            "Отсутствуют обязательные системные роли: "
            + ", ".join(sorted(missing_codes))
        )

    # --------------------------------------------------------
    # Проверка дублирующихся кодов
    # --------------------------------------------------------

    duplicates = list(
        Role.objects
        .values("code")
        .annotate(
            count=Count("id"),
        )
        .filter(
            count__gt=1,
        )
    )

    if duplicates:
        details = "; ".join(
            (
                f"code={item['code']!r}, "
                f"count={item['count']}"
            )
            for item in duplicates
        )

        raise RuntimeError(
            "Невозможно установить UNIQUE для roles.code. "
            "Обнаружены дублирующиеся значения: "
            + details
        )


class Migration(migrations.Migration):
    """
    Финальный этап внедрения стабильного программного кода роли.

    Поле Role.code уже заполнено миграцией 0004.

    Настоящая миграция устанавливает ограничения:

        NOT NULL
            каждая роль должна иметь программный код;

        UNIQUE
            один программный код может принадлежать только одной роли.

    Модель Role имеет managed=False, поэтому Django самостоятельно
    не управляет физической структурой таблицы roles.

    По этой причине используются:

        RunSQL
            для непосредственного изменения PostgreSQL;

        SeparateDatabaseAndState
            для синхронизации физической схемы БД
            с состоянием миграций Django.
    """

    dependencies = [
        (
            "accounts",
            "0004_populate_role_codes",
        ),
    ]

    operations = [
        migrations.RunPython(
            validate_role_codes,
            reverse_code=migrations.RunPython.noop,
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE roles
                        ALTER COLUMN code SET NOT NULL;

                        ALTER TABLE roles
                        ADD CONSTRAINT roles_code_uniq
                        UNIQUE (code);
                    """,
                    reverse_sql="""
                        ALTER TABLE roles
                        DROP CONSTRAINT IF EXISTS roles_code_uniq;

                        ALTER TABLE roles
                        ALTER COLUMN code DROP NOT NULL;
                    """,
                ),
            ],

            state_operations=[
                migrations.AlterField(
                    model_name="role",
                    name="code",
                    field=models.CharField(
                        choices=[
                            (
                                "ADMIN",
                                "Администратор",
                            ),
                            (
                                "COMMITTEE",
                                "Комитет образования",
                            ),
                            (
                                "DIRECTOR",
                                "Директор учреждения",
                            ),
                        ],
                        db_column="code",
                        max_length=50,
                        unique=True,
                    ),
                ),
            ],
        ),
    ]