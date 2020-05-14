from django.core.management import BaseCommand, CommandError
from django.db import transaction

from desecapi import pdns
from desecapi.models import Domain, RRset, RR, RR_SET_TYPES_AUTOMATIC


class Command(BaseCommand):
    help = 'Import authoritative data from pdns, making the local database consistent with pdns.'

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*',
                            help='Domain name to import. If omitted, will import all domains that are known locally.')

    def handle(self, *args, **options):
        domains = Domain.objects.all()

        if options['domain-name']:
            domains = domains.filter(name__in=options['domain-name'])
            domain_names = domains.values_list('name', flat=True)

            for domain_name in options['domain-name']:
                if domain_name not in domain_names:
                    raise CommandError('{} is not a known domain'.format(domain_name))

        for domain in domains:
            self.stdout.write('%s ...' % domain.name, ending='')
            try:
                self._sync_domain(domain)
                self.stdout.write(' synced')
            except Exception as e:
                self.stdout.write(' failed')
                msg = 'Error while processing {}: {}'.format(domain.name, e)
                raise CommandError(msg)

    @staticmethod
    @transaction.atomic
    def _sync_domain(domain):
        domain.rrset_set.all().delete()
        rrsets = []
        rrs = []
        for rrset_data in pdns.get_rrset_datas(domain):
            if rrset_data['type'] in RR_SET_TYPES_AUTOMATIC:
                continue
            records = rrset_data.pop('records')
            rrset = RRset(**rrset_data)
            rrsets.append(rrset)
            rrs.extend([RR(rrset=rrset, content=record) for record in records])
        RRset.objects.bulk_create(rrsets)
        RR.objects.bulk_create(rrs)
