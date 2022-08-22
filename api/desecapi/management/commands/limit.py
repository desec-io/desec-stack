from django.core.management import BaseCommand, CommandError
from django.db.models import Q

from api import settings
from desecapi.models import RRset, Domain, User
from desecapi.pdns_change_tracker import PDNSChangeTracker


class Command(BaseCommand):
    help = "Sets/updates limits for users and domains."

    def add_arguments(self, parser):
        parser.add_argument(
            "kind",
            help="Identifies which limit should be updated. Possible values: domains, ttl",
        )
        parser.add_argument(
            "id",
            help="Identifies the entity to be updated. Users are identified by email address; "
            "domains by their name.",
        )
        parser.add_argument("new_limit", help="New value for the limit.")

    def handle(self, *args, **options):
        if options["kind"] == "domains":
            try:
                user = User.objects.get(email=options["id"])
            except User.DoesNotExist:
                raise CommandError(
                    f'User with email address "{options["id"]}" could not be found.'
                )
            user.limit_domains = options["new_limit"]
            user.save()
            print(
                f"Updated {user.email}: set max number of domains to {user.limit_domains}."
            )
        elif options["kind"] == "ttl":
            try:
                domain = Domain.objects.get(name=options["id"])
            except Domain.DoesNotExist:
                raise CommandError(
                    f'Domain with name "{options["id"]}" could not be found.'
                )
            domain.minimum_ttl = options["new_limit"]
            domain.save()
            print(f"Updated {domain.name}: set minimum TTL to {domain.minimum_ttl}.")
        else:
            raise CommandError(f'Unknown limit "{options["kind"]}" specified.')
