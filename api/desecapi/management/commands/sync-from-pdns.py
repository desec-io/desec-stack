from django.core.management import BaseCommand, CommandError
from desecapi.models import Domain, RRset
from desecapi import pdns
from django.db import transaction


class Command(BaseCommand):
    help = 'Import authoritative data from pdns, making the local database consistent with pdns.'

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*', help='Domain name to import. If omitted, will import all domains that are known locally.')

    def handle(self, *args, **options):
        domains = Domain.objects.all()

        if options['domain-name']:
            domains = domains.filter(name__in=options['domain-name'])
            domain_names = domains.values_list('name', flat=True)

            for domain_name in options['domain-name']:
                if domain_name not in domain_names:
                    raise CommandError('{} is not a known domain'.format(domain_name))

        for domain in domains:
            try:
                with transaction.atomic():
                    RRset.objects.filter(domain=domain).delete()
                    rrsets = pdns.get_rrsets(domain)
                    rrsets = [rrset for rrset in rrsets if rrset.type != 'SOA']
                    RRset.objects.bulk_create(rrsets)

            except Exception as e:
                msg = 'Error while processing {}: {}'.format(domain.name, e)
                raise CommandError(msg)

            else:
                print(domain.name)
