from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0046_domain_nslord"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="csk_private_key_encrypted",
            field=models.BinaryField(blank=True, null=True),
        ),
    ]
