from django.core.management import BaseCommand
from django.db.models import Q

from api import settings
from desecapi.models import RRset, Domain, User
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):
    help = 'Removes all DNS records from domains given either by name or by email address of their owner. ' \
           'Locks all implicated user accounts.'

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='*',
                            help='Domain(s) and User(s) to truncate and disable identified by name and email addresses')

    def handle(self, *args, **options):
        with PDNSChangeTracker():
            # domains to truncate: all domains given and all domains belonging to a user given
            domains = Domain.objects.filter(
                Q(name__in=options['names']) |
                Q(owner__email__in=options['names'])
            )

            # users to lock: all associated with any of the domains and all given
            users = User.objects.filter(
                Q(domains__name__in=options['names']) |
                Q(email__in=options['names'])
            )

            # rrsets to delete: all belonging to (all domains given and all domains belonging to a user given)
            rrsets = RRset.objects.filter(
                Q(domain__name__in=options['names']) |
                Q(domain__owner__email__in=options['names'])
            )

            print(f'Deleting {rrsets.count()} RRset(s) from {domains.count()} domain(s); '
                  f'disabling {users.count()} associated user account(s).')

            # delete rrsets and create default NS records
            rrsets.delete()
            for d in domains:
                RRset.objects.create(domain=d, subname='', type='NS', ttl=3600, contents=settings.DEFAULT_NS)

        # lock users
        users.update(is_active=False)
