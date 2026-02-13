"""Knot DNS backend helpers for catalog updates, DNSSEC, and transfers."""

from functools import lru_cache
from hashlib import sha1
import logging
import os
import socket
import select
import time

import dns.dnssec
import dns.message
import dns.name
import dns.query
import dns.rcode
import dns.rdtypes.ANY.DNSKEY
import dns.rdata
import dns.rdatatype
import dns.tsig
import dns.tsigkeyring
import dns.update
import dns.zone
import dns.exception
from django.conf import settings

from desecapi.exceptions import KnotException


DEFAULT_SOA_CONTENT = "get.desec.io. get.desec.io. 1 86400 3600 2419200 3600"

logger = logging.getLogger(__name__)

_TSIG_ALGORITHM_MAP = {
    "hmac-md5": dns.tsig.HMAC_MD5,
    "hmac-sha1": dns.tsig.HMAC_SHA1,
    "hmac-sha224": dns.tsig.HMAC_SHA224,
    "hmac-sha256": dns.tsig.HMAC_SHA256,
    "hmac-sha256-128": dns.tsig.HMAC_SHA256_128,
    "hmac-sha384": dns.tsig.HMAC_SHA384,
    "hmac-sha384-192": dns.tsig.HMAC_SHA384_192,
    "hmac-sha512": dns.tsig.HMAC_SHA512,
    "hmac-sha512-256": dns.tsig.HMAC_SHA512_256,
}


def _tsig_algorithm(name):
    """Return a dnspython TSIG algorithm constant for the configured name."""
    if not name:
        return None
    algorithm = _TSIG_ALGORITHM_MAP.get(name.lower())
    if algorithm is None:
        raise KnotException(f"Unsupported TSIG algorithm: {name}")
    return algorithm


@lru_cache(maxsize=1)
def _knot_host_ip():
    """Resolve NSLORD_KNOT_HOST to a concrete IP address (IPv4/IPv6)."""
    host = settings.NSLORD_KNOT_HOST
    try:
        dns.inet.af_for_address(host)
        return host
    except ValueError:
        pass
    addrinfo = []
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            addrinfo = socket.getaddrinfo(
                host, None, family=family, type=socket.SOCK_STREAM
            )
        except socket.gaierror:
            continue
        if addrinfo:
            break
    if not addrinfo:
        raise KnotException(f"Failed to resolve NSLORD_KNOT_HOST {host!r}")
    return addrinfo[0][4][0]


def _update_keyring():
    """Return TSIG keyring/name/algorithm tuple for dynamic updates."""
    key_name = settings.NSLORD_KNOT_UPDATE_KEY_NAME
    key_secret = settings.NSLORD_KNOT_UPDATE_KEY_SECRET
    if not key_name or not key_secret:
        return None, None, None
    keyring = dns.tsigkeyring.from_text({key_name: key_secret})
    return (
        keyring,
        dns.name.from_text(key_name),
        _tsig_algorithm(settings.NSLORD_KNOT_UPDATE_KEY_ALGORITHM),
    )


def _transfer_keyring():
    """Return TSIG keyring/name/algorithm tuple for AXFR/IXFR transfers."""
    key_name = settings.NSLORD_KNOT_TRANSFER_KEY_NAME
    key_secret = settings.NSLORD_KNOT_TRANSFER_KEY_SECRET
    if not key_name or not key_secret:
        key_name = settings.NSLORD_KNOT_UPDATE_KEY_NAME
        key_secret = settings.NSLORD_KNOT_UPDATE_KEY_SECRET
        key_algorithm = settings.NSLORD_KNOT_UPDATE_KEY_ALGORITHM
        if not key_name or not key_secret:
            return None, None, None
    else:
        key_algorithm = settings.NSLORD_KNOT_TRANSFER_KEY_ALGORITHM
    keyring = dns.tsigkeyring.from_text({key_name: key_secret})
    return (
        keyring,
        dns.name.from_text(key_name),
        _tsig_algorithm(key_algorithm),
    )


def _send_update(update: dns.update.Update) -> None:
    """Send a single DNS update to Knot and hard-fail on any error."""
    try:
        host = _knot_host_ip()
        response = dns.query.tcp(
            update,
            host,
            port=settings.NSLORD_KNOT_PORT,
            timeout=settings.NSLORD_KNOT_TIMEOUT,
        )
    except dns.exception.Timeout as exc:
        raise KnotException("Knot update timed out") from exc
    if response.rcode() != dns.rcode.NOERROR:
        zone = update.zone
        zone_text = zone.to_text() if hasattr(zone, "to_text") else str(zone)
        logger.warning(
            "Knot update failed for zone=%s rcode=%s",
            zone_text,
            dns.rcode.to_text(response.rcode()),
        )
        raise KnotException(
            f"Knot update failed with rcode {dns.rcode.to_text(response.rcode())}"
        )


def _catalog_member_subname(zone):
    """Return catalog member label for a zone name (stable hash)."""
    zone = zone.rstrip(".") + "."
    return f"{sha1(zone.encode()).hexdigest()}.zones"


def _catalog_record_name(zone):
    """Return the FQDN of the catalog member PTR record for a zone."""
    return f"{_catalog_member_subname(zone)}.{settings.CATALOG_ZONE}".strip(".") + "."


def _new_update(zone):
    """Create a dnspython Update with configured TSIG for a zone."""
    keyring, keyname, keyalgorithm = _update_keyring()
    return dns.update.Update(
        zone,
        keyring=keyring,
        keyname=keyname,
        keyalgorithm=keyalgorithm,
    )


def create_zone(name):
    """Create a zone via the catalog update and verify it becomes available."""
    catalog_update = _new_update(settings.CATALOG_ZONE)
    catalog_update.replace(_catalog_record_name(name), 0, "PTR", name.rstrip(".") + ".")
    try:
        _send_update(catalog_update)
    except KnotException as exc:
        if "timed out" not in str(exc):
            raise
        if wait_for_zone(name, attempts=60, interval_seconds=0.5):
            return
        raise


def ensure_default_ns(name):
    """Ensure default NS/SOA records exist for a zone and are visible."""
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    update = _new_update(name)
    apex = name.rstrip(".") + "."
    update.replace(apex, settings.DEFAULT_NS_TTL, "NS", *settings.DEFAULT_NS)
    update.replace(apex, settings.DEFAULT_NS_TTL, "SOA", DEFAULT_SOA_CONTENT)
    _send_update(update)
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")


def _write_bind_keypair(name, dnskey, private_key):
    """Write BIND-style DNSKEY + private key files for Knot import."""
    import_dir = settings.NSLORD_KNOT_IMPORT_DIR
    if not import_dir or not private_key:
        return None
    zone = name.rstrip(".")
    key_rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.DNSKEY, dnskey)
    key_tag = dns.dnssec.key_id(key_rdata)
    base = f"K{zone}.+{key_rdata.algorithm:03d}+{key_tag:05d}"
    zone_dir = os.path.join(import_dir, zone)
    os.makedirs(zone_dir, exist_ok=True)
    key_path = os.path.join(zone_dir, f"{base}.key")
    private_path = os.path.join(zone_dir, f"{base}.private")
    key_line = f"{zone}. IN DNSKEY {dnskey}\n"
    with open(key_path, "w", encoding="ascii") as handle:
        handle.write(key_line)
    private_content = private_key.rstrip("\n") + "\n"
    with open(private_path, "w", encoding="ascii") as handle:
        handle.write(private_content)
    with open(os.path.join(zone_dir, ".import"), "w", encoding="ascii") as handle:
        handle.write(str(key_tag))
    return key_tag


def _key_ready_path(name):
    """Return the path of the Knot CSK import readiness marker file."""
    import_dir = settings.NSLORD_KNOT_IMPORT_DIR
    if not import_dir:
        return None
    zone = name.rstrip(".")
    return os.path.join(import_dir, zone, ".ready")


def prepare_csk_key(name, *, dnskey, private_key=None):
    """Prepare a CSK keypair for Knot import without triggering any update."""
    if not private_key:
        return
    _write_bind_keypair(name, dnskey, private_key)


def wait_for_csk_key_ready(name):
    """Wait for Knot to signal completion of CSK import via .ready file."""
    ready_path = _key_ready_path(name)
    if not ready_path:
        return
    timeout = settings.NSLORD_KNOT_KEY_READY_TIMEOUT
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(ready_path):
            return
        _sleep(0.2)
    raise KnotException(f"Knot key import not ready for {name} after {timeout} seconds")


def _dnskey_present(name, dnskey):
    """Check whether a specific DNSKEY RR appears in the zone."""
    query = dns.message.make_query(name, dns.rdatatype.DNSKEY, want_dnssec=True)
    response = dns.query.tcp(
        query,
        _knot_host_ip(),
        port=settings.NSLORD_KNOT_PORT,
        timeout=settings.NSLORD_KNOT_TIMEOUT,
    )
    for rrset in response.answer:
        if rrset.rdtype != dns.rdatatype.DNSKEY:
            continue
        for rdata in rrset:
            if rdata.to_text() == dnskey:
                return True
    return False


def _wait_for_dnskey(name, dnskey, *, attempts: int = 20, delay_seconds: float = 0.2):
    """Poll for the presence of a DNSKEY RR, with bounded retries."""
    for _ in range(attempts):
        if _dnskey_present(name, dnskey):
            return True
        if delay_seconds:
            _sleep(delay_seconds)
    return False


def _dnskey_set(name):
    """Return the set of DNSKEY RR text values in the zone."""
    query = dns.message.make_query(name, dns.rdatatype.DNSKEY, want_dnssec=True)
    response = dns.query.tcp(
        query,
        _knot_host_ip(),
        port=settings.NSLORD_KNOT_PORT,
        timeout=settings.NSLORD_KNOT_TIMEOUT,
    )
    keys = set()
    for rrset in response.answer:
        if rrset.rdtype != dns.rdatatype.DNSKEY:
            continue
        for rdata in rrset:
            keys.add(rdata.to_text())
    return keys


def _wait_for_dnskey_set(
    name, expected, *, attempts: int = 60, delay_seconds: float = 0.5
):
    """Poll until the DNSKEY RRset equals the expected set."""
    for _ in range(attempts):
        if _dnskey_set(name) == expected:
            return True
        if delay_seconds:
            _sleep(delay_seconds)
    return False


def import_csk_key(name, *, dnskey, private_key=None):
    """Import a CSK into Knot and optionally verify visibility."""
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    if private_key:
        try:
            key_tag = _write_bind_keypair(name, dnskey, private_key)
            if key_tag is not None:
                logger.info(
                    "Knot CSK import prepared for %s (keytag %d)", name, key_tag
                )
        except Exception:
            logger.warning("Knot CSK import failed for %s", name, exc_info=True)
    update = _new_update(name)
    apex = name.rstrip(".") + "."
    has_changes = False
    update.replace(apex, settings.DEFAULT_NS_TTL, "DNSKEY", dnskey)
    has_changes = True
    try:
        key_rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.DNSKEY, dnskey)
        cds_records = [
            dns.dnssec.make_ds(dns.name.from_text(name), key_rdata, algo).to_text()
            for algo in (2, 4)
        ]
        for record in cds_records:
            update.add(apex, settings.DEFAULT_NS_TTL, "CDS", record)
        has_changes = True
    except Exception:
        pass
    if has_changes:
        _send_update(update)
    if private_key:
        if not _wait_for_dnskey(name, dnskey):
            logger.warning("Knot CSK DNSKEY not visible after import for %s", name)
        expected = {dnskey}
        if not _wait_for_dnskey_set(name, expected):
            logger.warning(
                "Knot CSK DNSKEY set not stabilized for %s: %s",
                name,
                _dnskey_set(name),
            )


def wait_for_zone(name, *, attempts=20, interval_seconds=0.5) -> bool:
    """Poll for zone availability by querying SOA from Knot."""
    query = dns.message.make_query(name, dns.rdatatype.SOA)
    query_timeout = min(settings.NSLORD_KNOT_TIMEOUT, 1.0)

    for _ in range(attempts):
        response = None
        try:
            response = dns.query.tcp(
                query,
                _knot_host_ip(),
                port=settings.NSLORD_KNOT_PORT,
                timeout=query_timeout,
            )
        except Exception:
            response = None
        if response and any(
            rrset.rdtype == dns.rdatatype.SOA for rrset in response.answer
        ):
            return True
        if interval_seconds:
            _sleep(interval_seconds)

    return False


def _sleep(seconds: float) -> None:
    """Sleep without blocking signals in some environments."""
    if seconds <= 0:
        return
    select.select([], [], [], seconds)


def delete_zone(name):
    """Delete a zone from the catalog."""
    catalog_update = _new_update(settings.CATALOG_ZONE)
    catalog_update.delete(_catalog_record_name(name), "PTR")
    _send_update(catalog_update)


def update_rrsets(
    domain_name, additions, modifications, deletions, deleted_records=None
):
    """Apply RRset changes via a single update attempt and surface errors."""
    from desecapi.models import RR, RRset

    if not wait_for_zone(domain_name, attempts=10, interval_seconds=0.2):
        raise KnotException(f"Knot zone {domain_name} not ready for updates")

    update = _new_update(domain_name)
    has_changes = False
    deleted_records = deleted_records or {}

    for type_, subname in deletions:
        rrset_name = RRset.construct_name(subname, domain_name)
        if type_ == "DNSKEY":
            records = deleted_records.get((type_, subname), set())
            if records:
                update.delete(rrset_name, type_, *records)
                has_changes = True
            continue
        update.delete(rrset_name, type_)
        has_changes = True

    for type_, subname in (additions | modifications) - deletions:
        rrset_name = RRset.construct_name(subname, domain_name)
        ttl = RRset.objects.values_list("ttl", flat=True).get(
            domain__name=domain_name, type=type_, subname=subname
        )
        records = [
            rr.content
            for rr in RR.objects.filter(
                rrset__domain__name=domain_name,
                rrset__type=type_,
                rrset__subname=subname,
            )
        ]
        if type_ == "DNSKEY":
            removed = deleted_records.get((type_, subname), set())
            if removed:
                update.delete(rrset_name, type_, *removed)
                has_changes = True
            if records:
                update.add(rrset_name, ttl, type_, *records)
                has_changes = True
            continue
        if records:
            update.replace(rrset_name, ttl, type_, *records)
        else:
            update.delete(rrset_name, type_)
        has_changes = True

    if has_changes:
        _send_update(update)


def import_zonefile_rrsets(name, rrsets):
    """Import RRsets from a zonefile with one update attempt."""
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    record_count = 0
    type_set = set()
    update = _new_update(name)
    for rrset in rrsets:
        if not rrset["records"]:
            continue
        record_count += len(rrset["records"])
        type_set.add(rrset["type"])
        ttl = min(rrset["ttl"], settings.DEFAULT_NS_TTL)
        update.replace(rrset["name"], ttl, rrset["type"], *rrset["records"])
    type_list = sorted(type_set)
    type_preview = ",".join(type_list[:10])
    if len(type_list) > 10:
        type_preview = f"{type_preview},...(+{len(type_list) - 10})"
    logger.info(
        "Knot import zonefile %s: rrsets=%d records=%d types=%s",
        name,
        len(rrsets),
        record_count,
        type_preview,
    )
    _send_update(update)


def ensure_soa_serial_min(
    name, serial: int, *, attempts: int = 5, delay_seconds: float = 0.2
):
    """Ensure SOA serial is at least the given value by issuing updates."""
    query = dns.message.make_query(name, dns.rdatatype.SOA)
    for attempt in range(1, attempts + 1):
        response = dns.query.tcp(
            query,
            _knot_host_ip(),
            port=settings.NSLORD_KNOT_PORT,
            timeout=settings.NSLORD_KNOT_TIMEOUT,
        )
        rrset = response.get_rrset(
            dns.message.ANSWER,
            dns.name.from_text(name),
            dns.rdataclass.IN,
            dns.rdatatype.SOA,
        )
        if rrset is None:
            logger.info("Knot SOA not found for %s while enforcing serial", name)
            return
        rdata = rrset[0]
        if rdata.serial >= serial:
            if attempt > 1:
                logger.info(
                    "Knot SOA serial for %s satisfied after %d attempts: %d >= %d",
                    name,
                    attempt,
                    rdata.serial,
                    serial,
                )
            return
        update = _new_update(name)
        apex = name.rstrip(".") + "."
        soa_text = (
            f"{rdata.mname.to_text()} {rdata.rname.to_text()} "
            f"{serial} {rdata.refresh} {rdata.retry} {rdata.expire} {rdata.minimum}"
        )
        logger.info(
            "Knot SOA serial for %s below minimum: %d < %d (attempt %d/%d)",
            name,
            rdata.serial,
            serial,
            attempt,
            attempts,
        )
        update.replace(apex, rrset.ttl, "SOA", soa_text)
        _send_update(update)
        if delay_seconds:
            _sleep(delay_seconds)
    raise KnotException(f"Knot SOA serial for {name} still below {serial}")


def get_zonefile(domain) -> bytes:
    """Fetch an AXFR and render a filtered zonefile payload."""
    keyring, keyname, keyalgorithm = _transfer_keyring()
    zone_name = domain.name.rstrip(".") + "."
    xfr = dns.query.xfr(
        _knot_host_ip(),
        zone_name,
        port=settings.NSLORD_KNOT_PORT,
        timeout=settings.NSLORD_KNOT_TIMEOUT,
        keyring=keyring,
        keyname=keyname,
        keyalgorithm=keyalgorithm,
        relativize=False,
    )
    zone = dns.zone.from_xfr(xfr, relativize=False)
    if zone is None:
        raise KnotException("Knot AXFR returned no data")

    from desecapi.models import RR_SET_TYPES_AUTOMATIC

    excluded_types = (RR_SET_TYPES_AUTOMATIC - {"SOA"}) | {
        "DNSKEY",
        "CDS",
        "CDNSKEY",
    }
    lines = []
    for name, rdataset in zone.iterate_rdatasets():
        rtype = dns.rdatatype.to_text(rdataset.rdtype)
        if rtype in excluded_types:
            continue
        for rdata in rdataset:
            lines.append(
                f"{name.to_text()}\t{rdataset.ttl}\tIN\t{rtype}\t{rdata.to_text()}"
            )
    return ("\n".join(lines) + "\n").encode()


def get_keys(domain):
    """Return DNSKEYs for a domain, including DS records where applicable."""
    query = dns.message.make_query(domain.name, dns.rdatatype.DNSKEY, want_dnssec=True)
    response = dns.query.tcp(
        query,
        _knot_host_ip(),
        port=settings.NSLORD_KNOT_PORT,
        timeout=settings.NSLORD_KNOT_TIMEOUT,
    )
    if response.rcode() != dns.rcode.NOERROR:
        raise KnotException(
            f"Knot DNSKEY query failed with rcode {dns.rcode.to_text(response.rcode())}"
        )
    cds_set = None
    try:
        cds_query = dns.message.make_query(domain.name, dns.rdatatype.CDS)
        cds_response = dns.query.tcp(
            cds_query,
            _knot_host_ip(),
            port=settings.NSLORD_KNOT_PORT,
            timeout=settings.NSLORD_KNOT_TIMEOUT,
        )
        if cds_response.rcode() == dns.rcode.NOERROR:
            cds_set = {
                rdata.to_text()
                for rrset in cds_response.answer
                if rrset.rdtype == dns.rdatatype.CDS
                for rdata in rrset
            }
    except Exception:
        cds_set = None
    keys = []
    for rrset in response.answer:
        if rrset.rdtype != dns.rdatatype.DNSKEY:
            continue
        for rdata in rrset:
            key_text = rdata.to_text()
            name = dns.name.from_text(domain.name)
            key_is_sep = rdata.flags & dns.rdtypes.ANY.DNSKEY.SEP
            keys.append(
                {
                    "dnskey": key_text,
                    "ds": (
                        [
                            dns.dnssec.make_ds(name, rdata, algo).to_text()
                            for algo in (2, 4)
                        ]
                        if key_is_sep
                        else []
                    ),
                    "flags": rdata.flags,
                    "keytype": None,
                }
            )
    if cds_set:
        for key in keys:
            if key["ds"]:
                key["ds"] = [ds for ds in key["ds"] if ds in cds_set]
    keys.sort(key=lambda key: (key["flags"] & dns.rdtypes.ANY.DNSKEY.SEP) == 0)
    return keys
