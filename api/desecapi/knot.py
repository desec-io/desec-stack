from functools import lru_cache
from hashlib import sha1
import socket
import select
import threading

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
    if not name:
        return None
    algorithm = _TSIG_ALGORITHM_MAP.get(name.lower())
    if algorithm is None:
        raise KnotException(f"Unsupported TSIG algorithm: {name}")
    return algorithm


@lru_cache(maxsize=1)
def _knot_host_ip():
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


def _send_update(update: dns.update.Update):
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
        raise KnotException(
            f"Knot update failed with rcode {dns.rcode.to_text(response.rcode())}"
        )


def _send_update_with_retry(
    update: dns.update.Update,
    *,
    attempts: int = 5,
    delay_seconds: float = 1.0,
    retry_rcodes: tuple[str, ...] = ("NOTAUTH", "SERVFAIL"),
):
    last_exc = None
    for attempt in range(attempts):
        try:
            _send_update(update)
            return
        except KnotException as exc:
            last_exc = exc
            if attempt < attempts - 1 and (
                any(code in str(exc) for code in retry_rcodes)
                or "timed out" in str(exc)
            ):
                _sleep(delay_seconds)
                continue
            raise
    if last_exc is not None:
        raise last_exc


def _catalog_member_subname(zone):
    zone = zone.rstrip(".") + "."
    return f"{sha1(zone.encode()).hexdigest()}.zones"


def _catalog_record_name(zone):
    return f"{_catalog_member_subname(zone)}.{settings.CATALOG_ZONE}".strip(".") + "."


def _new_update(zone):
    keyring, keyname, keyalgorithm = _update_keyring()
    return dns.update.Update(
        zone,
        keyring=keyring,
        keyname=keyname,
        keyalgorithm=keyalgorithm,
    )


def create_zone(name):
    catalog_update = _new_update(settings.CATALOG_ZONE)
    catalog_update.replace(_catalog_record_name(name), 0, "PTR", name.rstrip(".") + ".")
    try:
        _send_update_with_retry(catalog_update)
    except KnotException as exc:
        if "timed out" not in str(exc):
            raise
        if wait_for_zone(name, attempts=60, interval_seconds=0.5):
            return
        raise


def ensure_default_ns(name):
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    update = _new_update(name)
    apex = name.rstrip(".") + "."
    update.replace(apex, settings.DEFAULT_NS_TTL, "NS", *settings.DEFAULT_NS)
    _send_update_with_retry(update)


def import_csk_key(name, *, dnskey, private_key=None):
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    update = _new_update(name)
    apex = name.rstrip(".") + "."
    update.add(apex, settings.DEFAULT_NS_TTL, "DNSKEY", dnskey)
    try:
        key_rdata = dns.rdata.from_text(
            dns.rdataclass.IN, dns.rdatatype.DNSKEY, dnskey
        )
        cds_records = [
            dns.dnssec.make_ds(dns.name.from_text(name), key_rdata, algo).to_text()
            for algo in (2, 4)
        ]
        update.replace(apex, 0, "CDS", *cds_records)
    except Exception:
        pass
    _send_update_with_retry(update)


def wait_for_zone(name, *, attempts=20, interval_seconds=0.5) -> bool:
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
    if seconds <= 0:
        return
    select.select([], [], [], seconds)


def delete_zone(name):
    catalog_update = _new_update(settings.CATALOG_ZONE)
    catalog_update.delete(_catalog_record_name(name), "PTR")
    _send_update(catalog_update)


def update_rrsets(domain_name, additions, modifications, deletions):
    from desecapi.models import RR, RRset

    if not wait_for_zone(domain_name, attempts=10, interval_seconds=0.2):
        raise KnotException(f"Knot zone {domain_name} not ready for updates")

    update = _new_update(domain_name)
    has_changes = False

    for type_, subname in deletions:
        rrset_name = RRset.construct_name(subname, domain_name)
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
        if records:
            update.replace(rrset_name, ttl, type_, *records)
        else:
            update.delete(rrset_name, type_)
        has_changes = True

    if has_changes:
        update_done = {"error": None}

        def _apply_update():
            try:
                _send_update_with_retry(update, attempts=2, delay_seconds=0.2)
            except Exception as exc:
                update_done["error"] = exc

        thread = threading.Thread(target=_apply_update, daemon=True)
        thread.start()
        thread.join(timeout=settings.NSLORD_KNOT_TIMEOUT * 2)
        if thread.is_alive():
            if settings.DEBUG:
                return
            raise KnotException("Knot update timed out")
        if update_done["error"] is not None:
            raise update_done["error"]


def import_zonefile_rrsets(name, rrsets):
    if not wait_for_zone(name, attempts=60, interval_seconds=0.5):
        raise KnotException(f"Knot zone {name} not ready for updates")
    update = _new_update(name)
    for rrset in rrsets:
        if not rrset["records"]:
            continue
        update.replace(
            rrset["name"], rrset["ttl"], rrset["type"], *rrset["records"]
        )
    _send_update_with_retry(update)


def get_zonefile(domain) -> bytes:
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
