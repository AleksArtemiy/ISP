from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_role_code_constraints")]
    operations = [migrations.AlterModelOptions(
        name="role",
        options={"managed": True, "verbose_name": "Роль", "verbose_name_plural": "Роли"},
    )]
