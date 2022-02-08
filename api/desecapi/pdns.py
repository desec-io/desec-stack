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
    'A', 'AAAA', 'AFSDB', 'ALIAS', 'APL', 'CAA', 'CERT', 'CDNSKEY', 'CDS', 'CNAME', 'CSYNC', 'DNSKEY', 'DNAME', 'DS',
    'HINFO', 'HTTPS', 'KEY', 'LOC', 'MX', 'NAPTR', 'NS', 'NSEC', 'NSEC3', 'NSEC3PARAM', 'OPENPGPKEY', 'PTR', 'RP',
    'RRSIG', 'SOA', 'SPF', 'SSHFP', 'SRV', 'SVCB', 'TLSA', 'SMIMEA', 'TXT', 'URI',

    # "additional" types, without obsolete ones
    'DHCID', 'DLV', 'EUI48', 'EUI64', 'IPSECKEY', 'KX', 'MINFO', 'MR', 'RKEY', 'WKS',

    # https://doc.powerdns.com/authoritative/changelog/4.5.html#change-4.5.0-alpha1-New-Features
    'NID', 'L32', 'L64', 'LP'
}

NSLORD = object()
NSMASTER = object()

_config = {
    NSLORD: {
        'base_url': settings.NSLORD_PDNS_API,
        'headers': {
            'Accept': 'application/json',
            'User-Agent': 'desecapi',
            'X-API-Key': settings.NSLORD_PDNS_API_TOKEN,
        }
    },
    NSMASTER: {
        'base_url': settings.NSMASTER_PDNS_API,
        'headers': {
            'Accept': 'application/json',
            'User-Agent': 'desecapi',
            'X-API-Key': settings.NSMASTER_PDNS_API_TOKEN,
        }
    }

}


def _pdns_request(method, *, server, path, data=None):
    if data is not None:
        data = json.dumps(data)
    if data is not None and len(data) > settings.PDNS_MAX_BODY_SIZE:
        raise RequestEntityTooLarge

    r = requests.request(method, _config[server]['base_url'] + path, data=data, headers=_config[server]['headers'])
    if r.status_code not in range(200, 300):
        raise PDNSException(response=r)
    metrics.get('desecapi_pdns_request_success').labels(method, r.status_code).inc()
    return r


def _pdns_post(server, path, data):
    return _pdns_request('post', server=server, path=path, data=data)


def _pdns_patch(server, path, data):
    return _pdns_request('patch', server=server, path=path, data=data)


def _pdns_get(server, path):
    return _pdns_request('get', server=server, path=path)


def _pdns_put(server, path):
    return _pdns_request('put', server=server, path=path)


def _pdns_delete(server, path):
    return _pdns_request('delete', server=server, path=path)


def pdns_id(name):
    # See also pdns code, apiZoneNameToId() in ws-api.cc (with the exception of forward slash)
    if not re.match(r'^[a-zA-Z0-9_.-]+$', name):
        raise SuspiciousOperation('Invalid hostname ' + name)

    name = name.translate(str.maketrans({'/': '=2F', '_': '=5F'}))
    return name.rstrip('.') + '.'


def get_keys(domain):
    """
    Retrieves a dict representation of the DNSSEC key information
    """
    r = _pdns_get(NSLORD, '/zones/%s/cryptokeys' % pdns_id(domain.name))
    metrics.get('desecapi_pdns_keys_fetched').inc()
    field_map = {
        'dnskey': 'dnskey',
        'cds': 'ds',
        'flags': 'flags',  # deprecated
        'keytype': 'keytype',  # deprecated
    }
    return [{v: key.get(k, []) for k, v in field_map.items()} for key in r.json() if key['published']]


def get_zone(domain):
    """
    Retrieves a dict representation of the zone from pdns
    """
    r = _pdns_get(NSLORD, '/zones/' + pdns_id(domain.name))

    return r.json()


def create_zone(name):
    """Creates a zone at nsmaster with the given name and sets it up for replication from nslord"""
    _pdns_post(
        NSMASTER, '/zones?rrsets=false',
        {
            'name': name + '.',
            'kind': 'SLAVE',
            'masters': [socket.gethostbyname('nslord')],
            'master_tsig_key_ids': ['default'],
        }
    )


def delete_zone(name):
    """Removes a zone from nsmaster"""
    _pdns_delete(NSMASTER, '/zones/' + pdns_id(name))


def get_rrset_datas(domain):
    """
    Retrieves a dict representation of the RRsets in a given zone
    """
    return [{'domain': domain,
             'subname': rrset['name'][:-(len(domain.name) + 2)],
             'type': rrset['type'],
             'records': [record['content'] for record in rrset['records']],
             'ttl': rrset['ttl']}
            for rrset in get_zone(domain)['rrsets']]


def create_cryptokey(name):
    """
    Creates a new cryptokey with pdns' default settings for the given domain name.
    It is published immediately!
    """
    _pdns_post(
        NSLORD,
        f'/zones/{pdns_id(name)}/cryptokeys',
        {
            'keytype': 'csk',
            'published': True,
            'active': True,
        }
    )


def update_catalog(name, delete):
    _pdns_patch(
        NSMASTER, '/zones/' + pdns_id(settings.CATALOG_ZONE),
        {
            'rrsets': [construct_catalog_rrset(zone=name, delete=delete)]
        }
    )
    metrics.get('desecapi_pdns_catalog_updated').inc()


def catalog_add(name):
    """Adds the given name to the catalog zone on nsmaster"""
    update_catalog(name, delete=False)


def catalog_remove(name):
    """Removes the given name from the catalog zone on nsmaster"""
    update_catalog(name, delete=True)


def construct_catalog_rrset(zone=None, delete=False, subname=None, qtype='PTR', rdata=None):
    # subname can be generated from zone for convenience; exactly one needs to be given
    assert (zone is None) ^ (subname is None)
    # sanity check: one can't delete an rrset and give record data at the same time
    assert not (delete and rdata)

    if subname is None:
        zone = zone.rstrip('.') + '.'
        m_unique = sha1(zone.encode()).hexdigest()
        subname = f'{m_unique}.zones'

    if rdata is None:
        rdata = zone

    return {
        'name': f'{subname}.{settings.CATALOG_ZONE}'.strip('.') + '.',
        'type': qtype,
        'ttl': 0,  # as per the specification
        'changetype': 'REPLACE',
        'records': [] if delete else [{'content': rdata, 'disabled': False}],
    }


def get_serials():
    return {zone['name']: zone['edited_serial'] for zone in _pdns_get(NSMASTER, '/zones').json()}


def trigger_axfr(name):
    """Instructs nsmaster to AXFR nslord for the given domain name"""
    _pdns_put(NSMASTER, '/zones/%s/axfr-retrieve' % pdns_id(name))
