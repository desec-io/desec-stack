# Generated by Django 4.1 on 2022-08-22 02:13

from django.db import migrations, models
from django.db.models import F


def forwards_func(apps, schema_editor):
    User = apps.get_model("desecapi", "User")
    db_alias = schema_editor.connection.alias
    User.objects.using(db_alias).update(credentials_changed=F("created"))


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0026_remove_domain_replicated_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="credentials_changed",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.RunPython(forwards_func, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="credentials_changed",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
