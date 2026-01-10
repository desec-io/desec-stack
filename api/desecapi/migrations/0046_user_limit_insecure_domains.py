from django.db import migrations, models

import desecapi.models.users


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0045_domain_delegation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="limit_insecure_domains",
            field=models.PositiveIntegerField(
                blank=True,
                default=desecapi.models.users.User._limit_insecure_domains_default,
                null=True,
            ),
        ),
    ]
