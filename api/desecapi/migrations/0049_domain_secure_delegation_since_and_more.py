from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_secure_delegation_since(apps, schema_editor):
    """
    Adopts the checks that have already been recorded: a domain whose current
    check found it securely delegated to us has been secure since that check
    began. Everything else stays null, including domains never checked.
    """
    Domain = apps.get_model("desecapi", "Domain")
    DelegationCheck = apps.get_model("desecapi", "DelegationCheck")
    Domain.objects.filter(
        # SecurityStatus.SECURE, and NameserverStatus.CORRECTLY_DELEGATED or
        # MULTI_PROVIDER. Spelled out, because a migration must keep meaning
        # what it meant when it was written, however the enums move on.
        current_delegation_check__security_status=0,
        current_delegation_check__nameserver_status__in=[0, 1],
    ).update(
        # A join cannot be dereferenced in update(), hence the subquery.
        secure_delegation_since=Subquery(
            DelegationCheck.objects.filter(
                pk=OuterRef("current_delegation_check")
            ).values("created")[:1]
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("desecapi", "0048_delegation"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="secure_delegation_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            backfill_secure_delegation_since, migrations.RunPython.noop, elidable=True
        ),
        # Null now means "computed from the user's securely delegated domains"
        # rather than "unlimited", and is the default, so that new accounts are
        # on the automatic limit. No account currently has null.
        migrations.AlterField(
            model_name="user",
            name="limit_domains",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
