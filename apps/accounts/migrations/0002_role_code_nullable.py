from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Первый этап внедрения стабильного программного кода роли.

    Таблица roles является существующей таблицей и модель Role имеет
    managed=False. Поэтому обычная операция AddField не должна напрямую
    использоваться для изменения физической структуры таблицы.

    SeparateDatabaseAndState позволяет:

    1. явно добавить колонку code в PostgreSQL;
    2. сообщить состоянию миграций Django о существовании нового поля.

    На данном этапе поле остаётся nullable.

    Это сделано специально, чтобы существующие роли продолжили работать
    до выполнения отдельной миграции заполнения кодов.
    """

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE roles
                        ADD COLUMN code VARCHAR(50) NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE roles
                        DROP COLUMN code;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="role",
                    name="code",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("ADMIN", "Администратор"),
                            ("COMMITTEE", "Комитет образования"),
                            ("DIRECTOR", "Директор учреждения"),
                        ],
                        db_column="code",
                        max_length=50,
                        null=True,
                    ),
                ),
            ],
        ),
    ]