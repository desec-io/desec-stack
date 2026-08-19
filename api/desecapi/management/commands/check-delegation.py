import itertools
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from desecapi import delegation, tasks, unbound
from desecapi.models import DelegationCheck, Domain, User
from desecapi.models.domains import under_local_public_suffix_q


# Domains are handled in batches, so that a bulk run neither loads the whole
# inventory into memory nor creates one pending future per domain up front.
BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Check whether domains are correctly delegated to us, and correctly secured."

    def add_arguments(self, parser):
        parser.add_argument(
            "domain-name",
            nargs="*",
            help="Domain name to check. Domains named here are always checked, "
            "even when they are under one of our own public suffixes.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Check all domains, except those under our own public suffixes "
            "unless --include-local is given.",
        )
        parser.add_argument(
            "--stale",
            type=int,
            metavar="SECONDS",
            help="Check domains that have not been checked for this many seconds, "
            "except those under our own public suffixes unless --include-local "
            "is given.",
        )
        parser.add_argument(
            "--user",
            metavar="ID_OR_EMAIL",
            help="Only check domains owned by this user, given as a UUID or an "
            "email address.",
        )
        parser.add_argument(
            "--include-local",
            action="store_true",
            help="When selecting domains in bulk, also check domains under %s."
            % ", ".join(sorted(settings.LOCAL_PUBLIC_SUFFIXES)),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print results without recording them.",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=4,
            metavar="N",
            help="Check up to this many domains at a time (default: 4). Checks "
            "wait on the network, so this is about how much load our resolver "
            "and the parents' nameservers see, not about CPU. With 0, hand the "
            "selected domains to the delegation workers instead of checking them "
            "here, one task per domain, so that an ad-hoc check never waits for a "
            "whole run to finish.",
        )

    @staticmethod
    def get_user(value):
        # An email address cannot be a UUID and vice versa, so the shape of the
        # value says which one it is.
        lookup = {"email": value} if "@" in value else {"pk": value}
        try:
            return User.objects.get(**lookup)
        except (User.DoesNotExist, ValidationError):
            raise CommandError(f"Unknown user: {value}")

    def get_domains(self, options):
        names = options["domain-name"]
        bulk = options["all"] or options["stale"] is not None
        if not names and not bulk:
            raise CommandError("Give at least one domain name, or --all, or --stale.")

        domains = Domain.objects.none()

        if names:
            domains = Domain.objects.filter(name__in=names)
            unknown = set(names) - set(domains.values_list("name", flat=True))
            if unknown:
                raise CommandError(f"Unknown domain(s): {', '.join(sorted(unknown))}")

        if bulk:
            selected = Domain.objects.all()
            if options["stale"] is not None:
                threshold = timezone.now() - timedelta(seconds=options["stale"])
                selected = selected.filter(
                    Q(current_delegation_check__isnull=True)
                    | Q(current_delegation_check__checked__lt=threshold)
                )
            if not options["include_local"]:
                # Every zone between these and the public root is one we host
                # and sign, so there is no delegation for the user to get wrong
                # and a check would only re-measure our own hosting.
                selected = selected.exclude(under_local_public_suffix_q())
            domains = domains | selected

        if options["user"] is not None:
            # A filter on whatever was selected, including domains named
            # explicitly -- unlike --include-local, which only widens the bulk
            # selection.
            domains = domains.filter(owner=self.get_user(options["user"]))

        # The current check is needed for recording the result, so fetch it
        # along with the domain instead of once per domain.
        return domains.select_related("current_delegation_check").order_by("name")

    def enqueue(self, options):
        # Workers re-check staleness when they get to a domain, so re-planning
        # a run whose backlog is still draining costs queries, not checks.
        max_age = options["stale"] or 0
        domains = self.get_domains(options).values_list("pk", flat=True)
        if options["dry_run"]:
            print(f"{domains.count()} domain(s) would be enqueued.")
        else:
            count = tasks.enqueue_checks(
                domains.iterator(chunk_size=BATCH_SIZE), tasks.BULK_QUEUE, max_age
            )
            print(f"{count} domain(s) enqueued.")

    def handle(self, *args, **options):
        if options["concurrency"] < 0:
            raise CommandError("--concurrency must not be negative.")

        if options["concurrency"] == 0:
            return self.enqueue(options)

        domains = self.get_domains(options).iterator(chunk_size=BATCH_SIZE)
        try:
            with ThreadPoolExecutor(max_workers=options["concurrency"]) as pool:
                for batch in itertools.batched(domains, BATCH_SIZE):
                    # Measuring happens in the pool, recording does not:
                    # delegation.check() touches no database, so keeping every
                    # ORM call on this thread spares us per-thread connections
                    # and their lifecycle. map() keeps the order, so results
                    # are still recorded and printed sorted by name.
                    results = pool.map(delegation.check, (d.name for d in batch))
                    for domain, result in zip(batch, results):
                        if not options["dry_run"]:
                            DelegationCheck.objects.record(domain, result)

                        print(
                            f"{domain.name} {result.security_status.name} "
                            f"{result.nameserver_status.name} "
                            f"{' '.join(result.nameservers) or '-'}"
                        )
        except unbound.UnboundException as e:
            # Our resolver is broken, so there is no point in continuing.
            raise CommandError(f"Resolver unavailable: {e}")
