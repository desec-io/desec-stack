import desecapi.models
import django.core.validators
from django.db import migrations, models


def lowercase_names(apps, schema_editor):
    # Domains
    Domain = apps.get_model('desecapi', 'Domain')
    domains = list(Domain.objects.all())
    for domain in domains:
        domain.name = domain.name.lower()
    Domain.objects.bulk_update(domains, ['name'], batch_size=500)

    # RRsets
    RRset = apps.get_model('desecapi', 'RRset')
    rrsets = list(RRset.objects.all())
    for rrset in rrsets:
        rrset.subname = rrset.subname.lower()
    RRset.objects.bulk_update(rrsets, ['subname'], batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ('desecapi', '0001_initial_squashed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domain',
            name='name',
            field=models.CharField(max_length=191, unique=True, validators=[desecapi.models.validate_lower, django.core.validators.RegexValidator(code='invalid_domain_name', message='Domain name malformed.', regex='^[a-z0-9_.-]+$')]),
        ),
        migrations.AlterField(
            model_name='domain',
            name='published',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='rrset',
            name='subname',
            field=models.CharField(blank=True, max_length=178, validators=[desecapi.models.validate_lower, django.core.validators.RegexValidator(code='invalid_subname', message='Subname malformed.', regex='^[*]?[a-z0-9_.-]*$')]),
        ),
        migrations.AlterField(
            model_name='rrset',
            name='type',
            field=models.CharField(max_length=10, validators=[desecapi.models.validate_upper, django.core.validators.RegexValidator(code='invalid_type', message='Type malformed.', regex='^[A-Z][A-Z0-9]*$')]),
        ),
        migrations.RunPython(lowercase_names, reverse_code=migrations.RunPython.noop),
    ]
