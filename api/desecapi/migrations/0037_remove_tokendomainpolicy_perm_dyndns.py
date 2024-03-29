# Generated by Django 5.0rc1 on 2023-12-01 15:01

from django.db import migrations, transaction
from django.db.models import OuterRef, Subquery


@transaction.atomic
def forwards_func(apps, schema_editor):
    TokenDomainPolicy = apps.get_model("desecapi", "TokenDomainPolicy")
    db_alias = schema_editor.connection.alias

    # Tokens with perm_dyndns effectively have perm_write for type=A/AAAA on any subname of their domain. We create
    # corresponding policies explicitly. Uniqueness violation cannot occur (no polices with non-NULL type exist).
    # We don't need to do anything for policies with perm_dyndns=False; perm_write determines their capabilities.
    queryset = TokenDomainPolicy.objects.using(db_alias)
    TokenDomainPolicy.objects.bulk_create(
        [
            TokenDomainPolicy(
                token=policy.token,
                domain=policy.domain,
                subname=None,
                type=type_,
                perm_write=True,
            )
            for policy in queryset.filter(perm_dyndns=True).all()
            for type_ in ("A", "AAAA")
        ]
    )
    # Now clean up (non-default) policies which have no further use, i.e. where perm_dyndns was different from the
    # default policy (that was taken care of above), but perm_write is equal to the default policy (that's useless).
    default_policy = queryset.filter(
        token=OuterRef("token"),
        domain__isnull=True,
        subname__isnull=True,
        type__isnull=True,
    )
    queryset.filter(
        domain__isnull=False, perm_write=Subquery(default_policy.values("perm_write"))
    ).exclude(perm_dyndns=Subquery(default_policy.values("perm_dyndns"))).delete()


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("desecapi", "0036_remove_tokendomainpolicy_default_policy_on_insert_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards_func, atomic=True),
        migrations.RemoveField(
            model_name="tokendomainpolicy",
            name="perm_dyndns",
        ),
    ]
