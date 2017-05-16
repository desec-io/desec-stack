from django.core.management import BaseCommand
from desecapi.models import Domain, RRset
from desecapi import pdns
from jq import jq
import json, sys
from django.db import transaction


class Command(BaseCommand):
    help = 'Import authoritative data from pdns, making the local database consistent with pdns.'

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*', help='Domain name to import. If omitted, will import all domains that are known locally.')

    def handle(self, *args, **options):
        domains = Domain.objects.all()

        if options['domain-name']:
            domains = domains.filter(name__in=options['domain-name'])

        for domain in domains:
            print(domain.name + ' ', end='', flush=True)

            try:
                rrsets_pdns = pdns.get_rrsets(domain.name)
                rrsets_pdns = jq('map(select( .type != "SOA" ))').transform(rrsets_pdns)

                rrsets = []
                for rrset_pdns in rrsets_pdns:
                    records = json.dumps(rrset_pdns['records'])
                    ttl = rrset_pdns['ttl']
                    type = rrset_pdns['type']

                    if rrset_pdns['name'] == domain.name + '.':
                        subname = ''
                    else:
                        if not rrset_pdns['name'].endswith('.' + domain.name + '.'):
                            raise Exception('inconsistent rrset name')
                        subname = rrset_pdns['name'][:-(len(domain.name) + 2)]

                    rrsets.append(RRset(domain=domain, subname=subname, records=records, ttl=ttl, type=type))

                with transaction.atomic():
                    RRset.objects.filter(domain=domain).delete()
                    RRset.objects.bulk_create(rrsets)

                print('ok')

            except Exception as e:
                print(e)

