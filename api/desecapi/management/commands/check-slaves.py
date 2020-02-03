from datetime import timedelta
from socket import gethostbyname
from time import sleep

from django.conf import settings
from django.core.mail import get_connection, mail_admins
from django.core.management import BaseCommand
from django.utils import timezone
import dns.message, dns.query, dns.rdatatype

from desecapi import pdns
from desecapi.models import Domain


def query_serial(zone, server):
    query = dns.message.make_query(zone, 'SOA')
    response = dns.query.tcp(query, server)

    for rrset in response.answer:
        if rrset.rdtype == dns.rdatatype.SOA:
            return int(rrset[0].serial)
    return None


class Command(BaseCommand):
    help = 'Check slaves for consistency with nsmaster.'

    def __init__(self, *args, **kwargs):
        self.servers = {gethostbyname(server): server for server in settings.WATCHDOG_SLAVES}
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*',
                            help='Domain name to check. If omitted, will check all recently published domains.')
        parser.add_argument('--delay', type=int, default=60, help='Delay SOA checks to allow pending AXFRs to finish.')
        parser.add_argument('--window', type=int, default=settings.WATCHDOG_WINDOW_SEC,
                            help='Check domains that were published no longer than this many seconds ago.')

    def find_outdated_servers(self, zone, local_serial):
        """
        Returns a dict, the key being the outdated slave name, and the value being the slave's current zone serial.
        """
        outdated = {}
        for server in self.servers:
            remote_serial = query_serial(zone, server)
            if not remote_serial or remote_serial < local_serial:
                outdated[self.servers[server]] = remote_serial

        return outdated

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(seconds=options['window'])
        recent_domain_names = Domain.objects.filter(published__gt=threshold).values_list('name', flat=True)
        serials = {zone: s for zone, s in pdns.get_serials().items() if zone.rstrip('.') in recent_domain_names}

        if options['domain-name']:
            serials = {zone: serial for zone, serial in serials.items() if zone.rstrip('.') in options['domain-name']}

        print('Sleeping for {} seconds before checking {} domains ...'.format(options['delay'], len(serials)))
        sleep(options['delay'])

        outdated_zone_count = 0
        outdated_slaves = set()

        output = []
        for zone, local_serial in serials.items():
            outdated_serials = self.find_outdated_servers(zone, local_serial)
            outdated_slaves.update(outdated_serials.keys())

            if outdated_serials:
                output.append(f'{zone} ({local_serial}) is outdated on {outdated_serials}')
                print(output[-1])
                outdated_zone_count += 1
            else:
                print(f'{zone} ok')

        output.append(f'Checked {len(serials)} domains, {outdated_zone_count} were outdated.')
        print(output[-1])

        self.report(outdated_slaves, output)

    def report(self, outdated_slaves, output):
        if not outdated_slaves:
            return

        subject = f'ALERT {len(outdated_slaves)} slaves out of sync'
        message = f'The following {len(outdated_slaves)} slaves are out of sync:\n'
        for outdated_slave in outdated_slaves:
            message += f'* {outdated_slave}\n'
        message += '\n'
        message += f'Current slave IPs: {self.servers}'
        message += '\n'
        message += '\n'.join(output)

        mail_admins(subject, message, connection=get_connection('django.core.mail.backends.smtp.EmailBackend'))
