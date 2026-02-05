import logging

import dns.name
import dns.zone

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
            lines.append(f\"{name}\\t{ttl}\\tIN\\t{rtype}\\t{record}\")
    return \"\\n\".join(lines) + \"\\n\"


def get_csk_private_key(domain):
    if getattr(domain, "nslord", None) == "knot":
        return domain.get_csk_private_key()
    private_key = pdns.get_csk_private_key(domain.name)
    return private_key or domain.get_csk_private_key()
