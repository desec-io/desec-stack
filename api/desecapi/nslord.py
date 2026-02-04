import logging

from desecapi import knot, pdns
from desecapi.exceptions import KnotException

logger = logging.getLogger(__name__)


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
