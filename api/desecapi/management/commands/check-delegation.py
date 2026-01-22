from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from django.conf import settings
from django.core.cache import cache as django_cache
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
import dns.exception, dns.resolver

from desecapi.delegation import DelegationChecker
from desecapi.models import Domain


LOCK_KEY = "desecapi.check-delegation.lock"
LOCK_TTL = 60 * 60
SAVE_BATCH_SIZE = 500
MAX_RUN_SECONDS = 60 * 60


class Command(BaseCommand):
    help = "Check delegation status."

    def __init__(self, *args, **kwargs):
        self.checker = DelegationChecker()
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "domain-name",
            nargs="*",
            help="Domain name to check. If omitted, will check all domains not registered under a local public suffix.",
        )
        parser.add_argument(
            "--udp-retries",
            type=int,
            default=2,
            help="Number of UDP retries before falling back to TCP. Set to 0 to disable UDP.",
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=20,
            help="Number of worker threads to use.",
        )

    def run_check(self, options):
        self.checker.udp_retries = options["udp_retries"]
        threads = options["threads"]
        qs = Domain.objects
        if options["domain-name"]:
            qs = qs.filter(
                name__in=[name.rstrip(".") for name in options["domain-name"]]
            )
        if settings.DELEGATION_SECURE_RECHECK_INTERVAL is not None:
            cutoff = timezone.now() - settings.DELEGATION_SECURE_RECHECK_INTERVAL
            qs = qs.exclude(Q(is_secured=True) & Q(delegation_checked__gte=cutoff))
        domains = [domain for domain in qs.all() if not domain.is_locally_registrable]

        def worker(domain):
            try:
                update = self.checker.check_domain(domain)
            except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
                return ("timeout", domain, None)
            except dns.resolver.NoNameservers:
                return ("unresponsive", domain, None)
            return ("ok", domain, update)

        if threads <= 1:
            results = map(worker, domains)
        else:
            executor = ThreadPoolExecutor(max_workers=threads)
            futures = [executor.submit(worker, domain) for domain in domains]
            results = (future.result() for future in as_completed(futures))

        updates = []
        for status, domain, update in results:
            if status == "timeout":
                print(f"{domain.name} Timeout")
                continue
            if status == "unresponsive":
                print(f"{domain.name} Unresponsive")
                continue
            updates.append(update)
            if update["is_registered"] and update["is_delegated"] is not None:
                print(
                    f"{domain.owner.email} {domain.name} {update['has_all_nameservers']=} {update['is_secured']=}"
                )
            else:
                print(
                    f"{domain.owner.email} {domain.name} {update['is_registered']=} delegated=False"
                )
        if not updates:
            return
        for i in range(0, len(updates), SAVE_BATCH_SIZE):
            batch = updates[i : i + SAVE_BATCH_SIZE]
            objs = []
            for update in batch:
                domain = Domain(id=update["id"])
                domain.delegation_checked = update["delegation_checked"]
                domain.is_registered = update["is_registered"]
                domain.has_all_nameservers = update["has_all_nameservers"]
                domain.is_delegated = update["is_delegated"]
                domain.is_secured = update["is_secured"]
                objs.append(domain)
            Domain.objects.bulk_update(
                objs,
                [
                    "delegation_checked",
                    "is_registered",
                    "has_all_nameservers",
                    "is_delegated",
                    "is_secured",
                ],
            )

    def handle(self, *args, **options):
        lock_acquired = django_cache.add(LOCK_KEY, "1", timeout=LOCK_TTL)
        if not lock_acquired:
            raise CommandError("check-delegation is already running.")
        try:
            start = time.monotonic()
            self.run_check(options)
            elapsed = time.monotonic() - start
            self.stdout.write(f"check-delegation runtime: {elapsed:.2f}s")
            if elapsed > MAX_RUN_SECONDS:
                raise CommandError("check-delegation exceeded maximum runtime.")
        finally:
            if lock_acquired:
                django_cache.delete(LOCK_KEY)
