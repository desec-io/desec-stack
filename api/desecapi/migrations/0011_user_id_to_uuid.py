from django.conf import settings
from django.db import migrations, models, transaction
import django.db.models.deletion
import uuid


def migrate_data(apps, schema_editor):
    # SQLite does not support altering constraints. However, we use it for tests only, and there's no data to migrate.
    if schema_editor.connection.vendor == 'sqlite':
        return

    def _sql_add_cascading_user_constraint(model_name, field_name):
        return f'ALTER TABLE desecapi_{model_name}' \
               f' ADD CONSTRAINT desecapi_{model_name}_{field_name}_id_update_cascade' \
               f' FOREIGN KEY (`{field_name}_id`) REFERENCES `desecapi_user` (`id`) ON UPDATE CASCADE'

    def _sql_drop_cascading_user_constraint(model_name, field_name):
        return f'ALTER TABLE desecapi_{model_name} DROP CONSTRAINT desecapi_{model_name}_{field_name}_id_update_cascade'

    # Add cascading foreign key constraints.
    # This has to be done after removing the regular constraints using migrations.AlterField. If done the other
    # way around, AlterField will drop the cascading constraint.
    schema_editor.execute(_sql_add_cascading_user_constraint('domain', 'owner')),
    schema_editor.execute(_sql_add_cascading_user_constraint('token', 'user')),

    # Repopulate user ID fields
    User = apps.get_model('desecapi', 'User')
    with transaction.atomic():
        for user in User.objects.all():
            User.objects.filter(email=user.email).update(id=uuid.uuid4().hex)

    # Remove cascading foreign key constraints
    schema_editor.execute(_sql_drop_cascading_user_constraint('domain', 'owner')),
    schema_editor.execute(_sql_drop_cascading_user_constraint('token', 'user')),


class Migration(migrations.Migration):
    dependencies = [
        ('desecapi', '0010_hash_tokens_and_switch_to_uuid'),
    ]

    operations = [
        # Switch to intermediate field type
        migrations.AlterField(
            model_name='user',
            name='id',
            field=models.CharField(default=uuid.uuid4, max_length=32, primary_key=True, serialize=False),
        ),

        # Remove regular foreign key constraints.
        # This is the migration Django generates when you set db_constraint=False on the model field.
        migrations.AlterField(
            model_name='domain',
            name='owner',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='domains', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='token',
            name='user',
            field=models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='auth_tokens', to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),

        # Repopulate user IDs with random UUIDs
        migrations.RunPython(migrate_data, migrations.RunPython.noop, atomic=False),

        # Restore regular foreign key constraints
        migrations.AlterField(
            model_name='token',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auth_tokens',
                                    to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),
        migrations.AlterField(
            model_name='domain',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='domains',
                                    to=settings.AUTH_USER_MODEL),
        ),

        # Switch to final field type
        migrations.AlterField(
            model_name='user',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
