# Generated by Django 3.1.6 on 2021-02-14 18:04

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0014_replication"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rrset",
            name="touched",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
