# Generated by Django 4.0.1 on 2022-01-19 14:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0020_user_email_verified'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthenticatedNoopUserAction',
            fields=[
                ('authenticateduseraction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='desecapi.authenticateduseraction')),
            ],
            options={
                'managed': False,
            },
            bases=('desecapi.authenticateduseraction',),
        ),
    ]
