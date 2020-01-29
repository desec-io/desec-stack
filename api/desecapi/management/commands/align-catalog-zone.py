from django.conf import settings
from django.core.management import BaseCommand

from desecapi.exceptions import PDNSException
from desecapi.pdns import _pdns_delete, _pdns_get, _pdns_post, NSLORD, NSMASTER, pdns_id, construct_catalog_rrset


class Command(BaseCommand):
    # https://tools.ietf.org/html/draft-muks-dnsop-dns-catalog-zones-04
    help = 'Generate a catalog zone on nsmaster, based on zones known on nslord.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        catalog_zone_id = pdns_id(settings.CATALOG_ZONE)

        # Fetch zones from NSLORD
        response = _pdns_get(NSLORD, '/zones').json()
        zones = {zone['name'] for zone in response}

        # Retrieve catalog zone serial (later reused for recreating the catalog zone, for allow for smooth rollover)
        try:
            response = _pdns_get(NSMASTER, f'/zones/{catalog_zone_id}')
            serial = response.json()['serial']
        except PDNSException as e:
            if e.response.status_code == 404:
                serial = None
            else:
                raise e

        # Purge catalog zone if exists
        try:
            _pdns_delete(NSMASTER, f'/zones/{catalog_zone_id}')
        except PDNSException as e:
            if e.response.status_code != 404:
                raise e

        # Create new catalog zone
        rrsets = [
            construct_catalog_rrset(subname='', qtype='NS', rdata='invalid.'),  # as per the specification
            construct_catalog_rrset(subname='version', qtype='TXT', rdata='"2"'),  # as per the specification
            *(construct_catalog_rrset(zone=zone) for zone in zones)
        ]

        data = {
            'name': settings.CATALOG_ZONE + '.',
            'kind': 'MASTER',
            'dnssec': False,  # as per the specification
            'nameservers': [],
            'rrsets': rrsets,
        }

        if serial is not None:
            data['serial'] = serial + 1  # actually, pdns does increase this as well, but let's not rely on this

        _pdns_post(NSMASTER, '/zones?rrsets=false', data)
        print(f'Aligned catalog zone ({len(zones)} member zones).')
