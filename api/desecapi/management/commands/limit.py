from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError

from desecapi.models import Domain, User


class Command(BaseCommand):
    help = "Sets/updates limits for users and domains."

    def add_arguments(self, parser):
        parser.add_argument(
            "kind",
            help="Identifies which limit should be updated. "
            "Possible values: domains, minimum_ttl, default_ttl",
        )
        parser.add_argument(
            "id",
            help="Identifies the entity to be updated. Users are identified by email address; "
            "domains by their name.",
        )
        parser.add_argument("new_limit", type=int, help="New value for the limit.")

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
        elif options["kind"] in ("minimum_ttl", "default_ttl"):
            try:
                domain = Domain.objects.get(name=options["id"])
            except Domain.DoesNotExist:
                raise CommandError(
                    f'Domain with name "{options["id"]}" could not be found.'
                )
            setattr(domain, options["kind"], options["new_limit"])
            try:
                domain.save()  # also validates minimum_ttl <= default_ttl <= MAXIMUM_TTL
            except ValidationError as e:
                raise CommandError(" ".join(e.messages))
            value = getattr(domain, options["kind"])
            kind = options["kind"].replace("_", " ")
            print(f"Updated {domain.name}: set {kind} to {value}.")
        else:
            raise CommandError(f'Unknown limit "{options["kind"]}" specified.')
