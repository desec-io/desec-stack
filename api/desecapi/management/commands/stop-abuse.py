from django.core.management import BaseCommand

from desecapi.models import RRset, Domain, User
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):
    help = 'Removes all DNS records from the given domain and suspends the associated user'

    def add_arguments(self, parser):
        parser.add_argument('domain-name', nargs='*', help='Domain(s) to remove all DNS records from')

    def handle(self, *args, **options):
        with PDNSChangeTracker():
            domains = Domain.objects.filter(name__in=options['domain-name'])
            users = User.objects.filter(domains__name__in=options['domain-name'])
            rrsets = RRset.objects.filter(domain__name__in=options['domain-name']).exclude(type='NS', subname='')
            print(f'Deleting {rrsets.count()} RRset(s) from {domains.count()} domain(s); '
                  f'disabling {users.count()} associated user account(s).')
            rrsets.delete()
        users.update(is_active=False)
