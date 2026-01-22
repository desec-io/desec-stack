from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0044_alter_captcha_created_alter_domain_renewal_state_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="delegation_checked",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="has_all_nameservers",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="is_delegated",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="is_registered",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="is_secured",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
