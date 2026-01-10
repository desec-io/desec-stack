from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cache
from socket import getaddrinfo
import time

from django.conf import settings
from django.core.cache import cache as django_cache
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
import dns.exception, dns.flags, dns.message, dns.name, dns.query, dns.resolver

from desecapi.models import Domain


LPS = {dns.name.from_text(lps) for lps in settings.LOCAL_PUBLIC_SUFFIXES}
SERVER = "8.8.8.8"
DNS_TIMEOUT = 5
LOCK_KEY = "desecapi.check-delegation.lock"
LOCK_TTL = 60 * 60
SAVE_BATCH_SIZE = 500
MAX_RUN_SECONDS = 60 * 60


@cache
def lookup(target):
    try:
        addrinfo = getaddrinfo(str(target), None)
    except OSError:
        addrinfo = []
    return {v[-1][0] for v in addrinfo}


class Command(BaseCommand):
    help = "Check delegation status."

    def __init__(self, *args, **kwargs):
        self.our_ns_set = {dns.name.from_text(ns) for ns in settings.DEFAULT_NS}
        self.our_ip_set = set.union(*(lookup(ns) for ns in self.our_ns_set))
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

    def handle_domain(self, domain):
        # Identify parent
        now = timezone.now()
        domain_name = dns.name.from_text(domain.name)
        parent = domain_name.parent()
        udp_retries = self.udp_retries
        resolver = dns.resolver.Resolver()
        while len(parent):
            query = dns.message.make_query(parent, dns.rdatatype.NS)
            res = self.query_with_fallback(query, SERVER, udp_retries)
            if res.answer:
                break
            parent = parent.parent()

        # Find delegation NS hostnames and IP addresses
        try:
            ns = res.find_rrset(res.answer, parent, dns.rdataclass.IN, dns.rdatatype.NS)
        except KeyError:
            raise dns.resolver.NoNameservers
        ipv4 = set()
        ipv6 = set()
        for rr in ns:
            ipv4 |= {ip for ip in lookup(rr.target) if "." in ip}
            ipv6 |= {ip for ip in lookup(rr.target) if "." not in ip}

        resolver.nameserver = list(ipv4) + list(ipv6)
        try:
            answer = self.resolve_with_fallback(resolver, domain_name, dns.rdatatype.NS)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return {
                "id": domain.id,
                "delegation_checked": now,
                "is_registered": False,
                "has_all_nameservers": None,
                "is_delegated": None,
                "is_secured": None,
            }
        update = {
            "id": domain.id,
            "delegation_checked": now,
            "is_registered": True,
        }

        # Compute overlap of delegation NS hostnames and IP addresses with ours
        ns_intersection = self.our_ns_set & {name.target for name in answer}
        update["has_all_nameservers"] = ns_intersection == self.our_ns_set

        ns_ip_intersection = self.our_ip_set & set.union(
            *(lookup(rr.target) for rr in answer)
        )
        # .is_delegated: None means "not delegated to deSEC", False means "partial", True means "fully"
        if not ns_ip_intersection:
            update["is_delegated"] = None
        else:
            update["is_delegated"] = ns_ip_intersection == self.our_ip_set

        # Find delegation DS records
        if ns_ip_intersection:
            query = dns.message.make_query(domain_name, dns.rdatatype.DS)
            res = self.query_with_fallback(query, SERVER, udp_retries)
            try:
                res.find_rrset(
                    res.answer, domain_name, dns.rdataclass.IN, dns.rdatatype.DS
                )
                has_ds = True
            except KeyError:
                has_ds = False
            # AD bit indicates the resolver validated the DS answer.
            authenticated = bool(res.flags & dns.flags.AD)
            update["is_secured"] = bool(has_ds and authenticated)
        else:
            update["is_secured"] = None
        return update

    def run_check(self, options):
        self.udp_retries = options["udp_retries"]
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
                update = self.handle_domain(domain)
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

    def query_with_fallback(self, query, server, udp_retries):
        if udp_retries <= 0:
            return dns.query.tcp(query, server, timeout=DNS_TIMEOUT)
        last_error = None
        for _ in range(udp_retries):
            try:
                return dns.query.udp(query, server, timeout=DNS_TIMEOUT)
            except Exception as ex:
                last_error = ex
        return dns.query.tcp(query, server, timeout=DNS_TIMEOUT)

    def resolve_with_fallback(self, resolver, name, rdtype):
        if self.udp_retries <= 0:
            return resolver.resolve(name, rdtype, tcp=True)
        last_error = None
        for _ in range(self.udp_retries):
            try:
                return resolver.resolve(name, rdtype, tcp=False)
            except Exception as ex:
                last_error = ex
        return resolver.resolve(name, rdtype, tcp=True)
