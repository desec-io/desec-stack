import json
import re
import socket
from hashlib import sha1

import requests
from django.conf import settings
from django.core.exceptions import SuspiciousOperation

from desecapi import metrics
from desecapi.exceptions import PDNSException, RequestEntityTooLarge

SUPPORTED_RRSET_TYPES = {
    # https://doc.powerdns.com/authoritative/appendices/types.html
    # "major" types
    "A",
    "AAAA",
    "AFSDB",
    "ALIAS",
    "APL",
    "CAA",
    "CERT",
    "CDNSKEY",
    "CDS",
    "CNAME",
    "CSYNC",
    "DNSKEY",
    "DNAME",
    "DS",
    "HINFO",
    "HTTPS",
    "KEY",
    "LOC",
    "MX",
    "NAPTR",
    "NS",
    "NSEC",
    "NSEC3",
    "NSEC3PARAM",
    "OPENPGPKEY",
    "PTR",
    "RP",
    "RRSIG",
    "SOA",
    "SPF",
    "SSHFP",
    "SRV",
    "SVCB",
    "TLSA",
    "SMIMEA",
    "TXT",
    "URI",
    # "additional" types, without obsolete ones
    "DHCID",
    "DLV",
    "EUI48",
    "EUI64",
    "IPSECKEY",
    "KX",
    "MINFO",
    "MR",
    "RKEY",
    "WKS",
    # https://doc.powerdns.com/authoritative/changelog/4.5.html#change-4.5.0-alpha1-New-Features
    "NID",
    "L32",
    "L64",
    "LP",
}

NSLORD = object()
NSMASTER = object()

_config = {
    NSLORD: {
        "base_url": settings.NSLORD_PDNS_API,
        "apikey": settings.NSLORD_PDNS_API_TOKEN,
    },
    NSMASTER: {
        "base_url": settings.NSMASTER_PDNS_API,
        "apikey": settings.NSMASTER_PDNS_API_TOKEN,
    },
}


def _pdns_request(
    method, *, server, path, data=None, accept="application/json", **kwargs
):
    if data is not None:
        data = json.dumps(data)
    if data is not None and len(data) > settings.PDNS_MAX_BODY_SIZE:
        raise RequestEntityTooLarge

    headers = {
        "Accept": accept,
        "User-Agent": "desecapi",
        "X-API-Key": _config[server]["apikey"],
    }
    r = requests.request(
        method, _config[server]["base_url"] + path, data=data, headers=headers
    )
    if r.status_code not in range(200, 300):
        metrics.get("desecapi_pdns_request_failure").labels(
            method, path, r.status_code
        ).inc()
        raise PDNSException(response=r)
    metrics.get("desecapi_pdns_request_success").labels(method, r.status_code).inc()
    return r


def _pdns_post(server, path, data, **kwargs):
    return _pdns_request("post", server=server, path=path, data=data, **kwargs)


def _pdns_patch(server, path, data, **kwargs):
    return _pdns_request("patch", server=server, path=path, data=data, **kwargs)


def _pdns_get(server, path, **kwargs):
    return _pdns_request("get", server=server, path=path, **kwargs)


def _pdns_put(server, path, **kwargs):
    return _pdns_request("put", server=server, path=path, **kwargs)


def _pdns_delete(server, path, **kwargs):
    return _pdns_request("delete", server=server, path=path, **kwargs)


def pdns_id(name):
    # See also pdns code, apiZoneNameToId() in ws-api.cc (with the exception of forward slash)
    if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
        raise SuspiciousOperation("Invalid hostname " + name)

    name = name.translate(str.maketrans({"/": "=2F", "_": "=5F"}))
    return name.rstrip(".") + "."


def get_keys(domain):
    """
    Retrieves a dict representation of the DNSSEC key information
    """
    r = _pdns_get(NSLORD, "/zones/%s/cryptokeys" % pdns_id(domain.name))
    metrics.get("desecapi_pdns_keys_fetched").inc()
    field_map = {
        "dnskey": "dnskey",
        "cds": "ds",
        "flags": "flags",  # deprecated
        "keytype": "keytype",  # deprecated
    }
    return [
        {v: key.get(k, []) for k, v in field_map.items()}
        for key in r.json()
        if key["published"]
    ]


def get_zone(domain):
    """
    Retrieves a dict representation of the zone from pdns
    """
    r = _pdns_get(NSLORD, "/zones/" + pdns_id(domain.name))

    return r.json()


def get_zonefile(domain) -> bin:
    """
    Retrieves the zonefile (presentation format) of a given zone as binary string
    """
    r = _pdns_get(
        NSLORD, "/zones/" + pdns_id(domain.name) + "/export", accept="text/dns"
    )

    return r.content


def get_rrset_datas(domain):
    """
    Retrieves a dict representation of the RRsets in a given zone
    """
    return [
        {
            "domain": domain,
            "subname": rrset["name"][: -(len(domain.name) + 2)],
            "type": rrset["type"],
            "records": [record["content"] for record in rrset["records"]],
            "ttl": rrset["ttl"],
        }
        for rrset in get_zone(domain)["rrsets"]
    ]


def update_catalog(zone, delete=False):
    """
    Updates the catalog zone information (`settings.CATALOG_ZONE`) for the given zone.
    """
    content = _pdns_patch(
        NSMASTER,
        "/zones/" + pdns_id(settings.CATALOG_ZONE),
        {"rrsets": [construct_catalog_rrset(zone=zone, delete=delete)]},
    )
    metrics.get("desecapi_pdns_catalog_updated").inc()
    return content


def create_zone_lord(name):
    name = name.rstrip(".") + "."
    _pdns_post(
        NSLORD,
        "/zones?rrsets=false",
        {
            "name": name,
            "kind": "MASTER",
            "dnssec": True,
            "nsec3param": "1 0 0 -",
            "nameservers": settings.DEFAULT_NS,
            "rrsets": [
                {
                    "name": name,
                    "type": "SOA",
                    # SOA RRset TTL: 300 (used as TTL for negative replies including NSEC3 records)
                    "ttl": 300,
                    "records": [
                        {
                            # SOA refresh: 1 day (only needed for nslord --> nsmaster replication after RRSIG rotation)
                            # SOA retry = 1h
                            # SOA expire: 4 weeks (all signatures will have expired anyways)
                            # SOA minimum: 3600 (for CDS, CDNSKEY, DNSKEY, NSEC3PARAM)
                            "content": "get.desec.io. get.desec.io. 1 86400 3600 2419200 3600",
                            "disabled": False,
                        }
                    ],
                }
            ],
        },
    )


def create_zone_master(name):
    name = name.rstrip(".") + "."
    _pdns_post(
        NSMASTER,
        "/zones?rrsets=false",
        {
            "name": name,
            "kind": "SLAVE",
            "masters": [socket.gethostbyname("nslord")],
            "master_tsig_key_ids": ["default"],
        },
    )


def delete_zone(name, server):
    _pdns_delete(server, "/zones/" + pdns_id(name))


def delete_zone_lord(name):
    _pdns_delete(NSLORD, "/zones/" + pdns_id(name))


def delete_zone_master(name):
    _pdns_delete(NSMASTER, "/zones/" + pdns_id(name))


def update_zone(name, data):
    _pdns_patch(NSLORD, "/zones/" + pdns_id(name), data)


def axfr_to_master(zone):
    _pdns_put(NSMASTER, "/zones/%s/axfr-retrieve" % pdns_id(zone))


def construct_catalog_rrset(
    zone=None, delete=False, subname=None, qtype="PTR", rdata=None
):
    # subname can be generated from zone for convenience; exactly one needs to be given
    assert (zone is None) ^ (subname is None)
    # sanity check: one can't delete an rrset and give record data at the same time
    assert not (delete and rdata)

    if subname is None:
        zone = zone.rstrip(".") + "."
        m_unique = sha1(zone.encode()).hexdigest()
        subname = f"{m_unique}.zones"

    if rdata is None:
        rdata = zone

    return {
        "name": f"{subname}.{settings.CATALOG_ZONE}".strip(".") + ".",
        "type": qtype,
        "ttl": 0,  # as per the specification
        "changetype": "REPLACE",
        "records": [] if delete else [{"content": rdata, "disabled": False}],
    }


def get_serials():
    return {
        zone["name"]: zone["edited_serial"]
        for zone in _pdns_get(NSMASTER, "/zones").json()
    }
