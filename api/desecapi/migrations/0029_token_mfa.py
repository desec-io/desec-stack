# Generated by Django 4.1 on 2022-08-25 03:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "desecapi",
            "0028_authenticatedcreatetotpfactoruseraction_basefactor_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="token",
            name="mfa",
            field=models.BooleanField(default=None, null=True),
        ),
    ]
