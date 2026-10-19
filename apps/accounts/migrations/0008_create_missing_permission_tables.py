"""Non-destructive bridge for manually prepared pre-production schemas."""
from django.db import migrations


def ensure_permission_tables(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    tables = set(schema_editor.connection.introspection.table_names())
    for field in User._meta.local_many_to_many:
        through = field.remote_field.through
        if through._meta.db_table not in tables:
            schema_editor.create_model(through)
            tables.add(through._meta.db_table)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_login_throttling')]
    operations = [migrations.RunPython(ensure_permission_tables, migrations.RunPython.noop)]
