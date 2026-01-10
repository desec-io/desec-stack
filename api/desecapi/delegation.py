from functools import cache
from socket import getaddrinfo

from django.conf import settings
from django.utils import timezone
import dns.exception, dns.flags, dns.message, dns.name, dns.query, dns.resolver


SERVER = "8.8.8.8"
DNS_TIMEOUT = 5


@cache
def lookup(target):
    try:
        addrinfo = getaddrinfo(str(target), None)
    except OSError:
        addrinfo = []
    return {v[-1][0] for v in addrinfo}


class DelegationChecker:
    def __init__(self, udp_retries=2, server=SERVER):
        self.udp_retries = udp_retries
        self.server = server
        self.our_ns_set = {dns.name.from_text(ns) for ns in settings.DEFAULT_NS}
        self.our_ip_set = set.union(*(lookup(ns) for ns in self.our_ns_set))

    def query_with_fallback(self, query):
        if self.udp_retries <= 0:
            return dns.query.tcp(query, self.server, timeout=DNS_TIMEOUT)
        last_error = None
        for _ in range(self.udp_retries):
            try:
                return dns.query.udp(query, self.server, timeout=DNS_TIMEOUT)
            except Exception as ex:
                last_error = ex
        return dns.query.tcp(query, self.server, timeout=DNS_TIMEOUT)

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

    def check_domain(self, domain):
        # Identify parent
        now = timezone.now()
        domain_name = dns.name.from_text(domain.name)
        parent = domain_name.parent()
        resolver = dns.resolver.Resolver()
        while len(parent):
            query = dns.message.make_query(parent, dns.rdatatype.NS)
            res = self.query_with_fallback(query)
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

        # Find delegation DS records and check validator-authenticated result
        if ns_ip_intersection:
            query = dns.message.make_query(domain_name, dns.rdatatype.DS)
            res = self.query_with_fallback(query)
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
