from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "desecapi",
            "0045_rr_unique_record_in_rrset_squashed_0046_remove_rr_unique_record_in_rrset_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="domain",
            name="minimum_ttl",
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
    ]
