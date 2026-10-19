from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_create_missing_permission_tables")]

    operations = [
        migrations.AddIndex(
            model_name="loginthrottle",
            index=models.Index(fields=["started_at"], name="login_throttle_ttl_idx"),
        ),
    ]
