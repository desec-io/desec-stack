from django.core.management import BaseCommand, CommandError

from desecapi.models import Domain, User


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
        parser.add_argument(
            "new_limit",
            help='New value for the limit. For "domains", the special value '
            '"auto" hands the account back to the limit computed from its '
            'securely delegated domains; for "ttl", "auto" unsets the '
            "domain's minimum TTL so that the global default applies.",
        )

    def handle(self, *args, **options):
        if options["kind"] == "domains":
            try:
                user = User.objects.get(email=options["id"])
            except User.DoesNotExist:
                raise CommandError(
                    f'User with email address "{options["id"]}" could not be found.'
                )
            auto = str(options["new_limit"]).lower() == "auto"
            user.limit_domains = None if auto else options["new_limit"]
            user.save()
            value = (
                f"auto (currently {user.effective_limit_domains})"
                if auto
                else str(user.effective_limit_domains)
            )
            print(f"Updated {user.email}: set max number of domains to {value}.")
        elif options["kind"] == "ttl":
            try:
                domain = Domain.objects.get(name=options["id"])
            except Domain.DoesNotExist:
                raise CommandError(
                    f'Domain with name "{options["id"]}" could not be found.'
                )
            if str(options["new_limit"]).lower() == "auto":
                domain.minimum_ttl = None
            else:
                try:
                    domain.minimum_ttl = int(options["new_limit"])
                except ValueError:
                    raise CommandError(
                        f'Invalid TTL limit "{options["new_limit"]}" specified.'
                    )
            domain.save()
            print(f"Updated {domain.name}: set minimum TTL to {domain.minimum_ttl}.")
        else:
            raise CommandError(f'Unknown limit "{options["kind"]}" specified.')
