import logging

import dns.message
import dns.name
import dns.query
import dns.rdataclass
import dns.rdatatype
import dns.zone
from django.conf import settings

from desecapi import knot, pdns
from desecapi.exceptions import KnotException

logger = logging.getLogger(__name__)

_DNSSEC_TYPES = {
    "DNSKEY",
    "CDS",
    "CDNSKEY",
    "RRSIG",
    "NSEC",
    "NSEC3",
    "NSEC3PARAM",
}


def get_keys(domain):
    if getattr(domain, "nslord", None) == "knot":
        try:
            return knot.get_keys(domain)
        except KnotException:
            logger.warning(
                "Knot DNSKEY query failed for %s", domain.name, exc_info=True
            )
            return []
    return pdns.get_keys(domain)


def get_zonefile(domain) -> bytes:
    if getattr(domain, "nslord", None) == "knot":
        return knot.get_zonefile(domain)
    return pdns.get_zonefile(domain)


def get_zonefile_without_dnssec(domain) -> bytes:
    zonefile = get_zonefile(domain).decode()
    rrsets = zonefile_to_rrsets(domain.name, zonefile)
    return rrsets_to_zonefile(domain.name, rrsets).encode()


def zonefile_to_rrsets(domain_name: str, zonefile: str):
    zone = dns.zone.from_text(
        zonefile,
        origin=dns.name.from_text(domain_name),
        allow_include=False,
        check_origin=False,
        relativize=False,
    )
    rrsets = []
    for name, rdataset in zone.iterate_rdatasets():
        rtype = dns.rdatatype.to_text(rdataset.rdtype)
        if rtype in _DNSSEC_TYPES:
            continue
        rrsets.append(
            {
                "name": name.to_text(),
                "type": rtype,
                "ttl": rdataset.ttl,
                "records": [rdata.to_text() for rdata in rdataset],
            }
        )
    return rrsets


def rrsets_to_zonefile(domain_name: str, rrsets) -> str:
    lines = []
    for rrset in rrsets:
        name = rrset["name"]
        ttl = rrset["ttl"]
        rtype = rrset["type"]
        for record in rrset["records"]:
            lines.append(f"{name}\t{ttl}\tIN\t{rtype}\t{record}")
    return "\n".join(lines) + "\n"


def get_csk_private_key(domain):
    if getattr(domain, "nslord", None) == "knot":
        return domain.get_csk_private_key()
    private_key = pdns.get_csk_private_key(domain.name)
    return private_key or domain.get_csk_private_key()


def get_soa_serial(domain):
    name = domain.name.rstrip(".") + "."
    if getattr(domain, "nslord", None) == "knot":
        host = settings.NSLORD_KNOT_HOST
        port = settings.NSLORD_KNOT_PORT
        timeout = settings.NSLORD_KNOT_TIMEOUT
    else:
        host = "nslord"
        port = 53
        timeout = 5
    query = dns.message.make_query(name, dns.rdatatype.SOA)
    host = pdns.gethostbyname_cached(host)
    try:
        response = dns.query.tcp(query, host, port=port, timeout=timeout)
    except Exception:
        logger.warning("SOA serial query failed for %s", name, exc_info=True)
        return None
    rrset = response.get_rrset(
        dns.message.ANSWER,
        dns.name.from_text(name),
        dns.rdataclass.IN,
        dns.rdatatype.SOA,
    )
    if rrset is None:
        return None
    return rrset[0].serial
