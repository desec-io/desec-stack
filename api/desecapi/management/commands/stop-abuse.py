import dns.resolver
from django.core.management import BaseCommand
from django.db.models import Q

from api import settings
from desecapi.models import BlockedSubnet, Domain, RR, RRset, User
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):
    help = (
        "Removes all DNS records from domains given either by name or by email address of their owner. "
        "Locks all implicated user accounts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "names",
            nargs="*",
            help="Domain(s) and User(s) to truncate and disable identified by name and email addresses",
        )

    def handle(self, *args, **options):
        with PDNSChangeTracker():
            # domains to truncate: all domains given and all domains belonging to a user given
            domains = Domain.objects.filter(
                Q(name__in=options["names"]) | Q(owner__email__in=options["names"])
            )
            domain_names = domains.distinct().values_list("name", flat=True)

            # users to lock: all associated with any of the domains and all given
            users = User.objects.filter(
                Q(domains__name__in=options["names"]) | Q(email__in=options["names"])
            )
            user_emails = users.distinct().values_list("email", flat=True)

            # rrsets to delete: all belonging to (all domains given and all domains belonging to a user given)
            rrsets = RRset.objects.filter(
                Q(domain__name__in=options["names"])
                | Q(domain__owner__email__in=options["names"])
            )

            blocked_subnets = []
            for rr in RR.objects.filter(rrset__in=rrsets.filter(type="A")):
                if not BlockedSubnet.objects.filter(
                    subnet__net_contains=rr.content
                ).exists():
                    try:
                        blocked_subnet = BlockedSubnet.from_ip(rr.content)
                    except dns.resolver.NXDOMAIN:  # for unallocated IP addresses
                        continue
                    blocked_subnet.save()
                    blocked_subnets.append(blocked_subnet)

            # Print summary
            print(
                f"Deleting {rrsets.distinct().count()} RRset(s) from {domains.distinct().count()} domain(s); "
                f"disabling {users.distinct().count()} associated user account(s). {len(blocked_subnets)} subnets:"
            )
            if blocked_subnets:
                row_format = "{:>11} {:>18} {:>8} {}"
                print(row_format.format("ASN", "Subnet", "Country", "Registry"))
                for bs in blocked_subnets:
                    print(
                        row_format.format(
                            bs.asn, str(bs.subnet), bs.country, bs.registry
                        )
                    )

            # Print details
            for d in domain_names:
                print(f"Truncating domain {d}")
            for e in user_emails:
                print(f"Locking user {e}")

            # delete rrsets and create default NS records
            rrsets.delete()
            for d in domains:
                RRset.objects.create(
                    domain=d,
                    subname="",
                    type="NS",
                    ttl=3600,
                    contents=settings.DEFAULT_NS,
                )

        # lock users
        users.update(is_active=False)
