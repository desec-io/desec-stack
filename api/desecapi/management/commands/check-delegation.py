from functools import cache
from socket import getaddrinfo

from django.conf import settings
from django.core.management import BaseCommand
import dns.exception, dns.message, dns.name, dns.query, dns.resolver

from desecapi.models import Domain


LPS = {dns.name.from_text(lps) for lps in settings.LOCAL_PUBLIC_SUFFIXES}
SERVER = "8.8.8.8"


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
        self.resolver = dns.resolver.Resolver()
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "domain-name",
            nargs="*",
            help="Domain name to check. If omitted, will check all domains not registered under a local public suffix.",
        )

    def handle_domain(self, domain):
        # Identify parent
        domain_name = dns.name.from_text(domain.name)
        parent = domain_name.parent()
        while len(parent):
            query = dns.message.make_query(parent, dns.rdatatype.NS)
            try:
                res = dns.query.udp(query, SERVER, timeout=5)
            except:
                res = dns.query.tcp(query, SERVER, timeout=5)
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

        self.resolver.nameserver = list(ipv4) + list(ipv6)
        try:
            answer = dns.resolver.resolve(domain_name, dns.rdatatype.NS)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            domain.is_registered = False
            return
        domain.is_registered = True

        # Compute overlap of delegation NS hostnames and IP addresses with ours
        ns_intersection = self.our_ns_set & {name.target for name in answer}
        domain.has_all_nameservers = ns_intersection == self.our_ns_set

        ns_ip_intersection = self.our_ip_set & set.union(
            *(lookup(rr.target) for rr in answer)
        )
        # .is_delegated: None means "not delegated to deSEC", False means "partial", True means "fully"
        if not ns_ip_intersection:
            domain.is_delegated = None
        else:
            domain.is_delegated = ns_ip_intersection == self.our_ip_set

        # Find delegation DS records
        if ns_ip_intersection:
            query = dns.message.make_query(domain_name, dns.rdatatype.DS)
            try:
                res = dns.query.udp(query, "8.8.8.8", timeout=5)
            except:
                res = dns.query.tcp(query, "8.8.8.8", timeout=5)
            try:
                ds = res.find_rrset(
                    res.answer, domain_name, dns.rdataclass.IN, dns.rdatatype.DS
                )
            except KeyError:
                ds = set()
            ds = {rr.to_text() for rr in ds}

            # Compute overlap of delegation DS records with ours
            our_ds_set = set()
            for key in domain.keys:
                # Only digest type 2 is mandatory to implement; delegation only fully set up if present
                our_ds_set |= {
                    ds.lower() for ds in key["ds"] if ds.split(" ")[2] == "2"
                }
            ds_intersection = our_ds_set & ds
            # .is_secured: None means "not secured with deSEC", False means "partial", True means "fully"
            if not ds_intersection:
                domain.is_secured = None
            else:
                domain.is_secured = ds_intersection == our_ds_set

    def handle(self, *args, **options):
        qs = Domain.objects
        if options["domain-name"]:
            qs = qs.filter(
                name__in=[name.rstrip(".") for name in options["domain-name"]]
            )
        for domain in qs.all():
            if domain.is_locally_registrable:
                continue

            try:
                self.handle_domain(domain)
            except (dns.exception.Timeout, dns.resolver.LifetimeTimeout):
                print(f"{domain.name} Timeout")
                continue
            except dns.resolver.NoNameservers:
                print(f"{domain.name} Unresponsive")
                continue
            if domain.is_registered and domain.is_delegated is not None:
                print(
                    f"{domain.owner.email} {domain.name} {domain.has_all_nameservers=} {domain.is_secured=}"
                )
            else:
                print(
                    f"{domain.owner.email} {domain.name} {domain.is_registered=} delegated=False"
                )
