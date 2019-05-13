import json
import random
import socket

import requests

from api import settings as api_settings
from desecapi.exceptions import PdnsException

NSLORD = object()
NSMASTER = object()

settings = {
    NSLORD: {
        'base_url': api_settings.NSLORD_PDNS_API,
        'headers': {
            'Accept': 'application/json',
            'User-Agent': 'desecapi',
            'X-API-Key': api_settings.NSLORD_PDNS_API_TOKEN,
        }
    },
    NSMASTER: {
        'base_url': api_settings.NSMASTER_PDNS_API,
        'headers': {
            'Accept': 'application/json',
            'User-Agent': 'desecapi',
            'X-API-Key': api_settings.NSMASTER_PDNS_API_TOKEN,
        }
    }

}


def _pdns_delete_zone(domain):
    path = '/zones/' + domain.pdns_id

    # We first delete the zone from nslord, the main authoritative source of our DNS data.
    # However, we do not want to wait for the zone to expire on the slave ("nsmaster").
    # We thus issue a second delete request on nsmaster to delete the zone there immediately.
    r1 = requests.delete(settings[NSLORD]['base_url'] + path, headers=settings[NSLORD]['headers'])
    if r1.status_code < 200 or r1.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r1.status_code == 422 and 'Could not find domain' in r1.text:
            pass
        else:
            raise PdnsException(r1)

    # Delete from nsmaster as well
    r2 = requests.delete(settings[NSMASTER]['base_url'] + path, headers=settings[NSMASTER]['headers'])
    if r2.status_code < 200 or r2.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r2.status_code == 422 and 'Could not find domain' in r2.text:
            pass
        else:
            raise PdnsException(r2)

    return r1, r2


def _pdns_request(method, *, server, path, body=None, acceptable_range=range(200, 300)):
    data = json.dumps(body) if body else None
    if data is not None and len(data) > api_settings.PDNS_MAX_BODY_SIZE:
        raise PdnsException(detail='Payload too large', status=413)

    r = requests.request(method, settings[server]['base_url'] + path, data=data, headers=settings[server]['headers'])
    if r.status_code not in acceptable_range:
        raise PdnsException(r)

    return r


def _pdns_post(server, path, body):
    return _pdns_request('post', server=server, path=path, body=body)


def _pdns_patch(server, path, body):
    return _pdns_request('patch', server=server, path=path, body=body)


def _pdns_get(server, path):
    return _pdns_request('get', server=server, path=path, acceptable_range=range(200, 400))


def _pdns_put(server, path):
    return _pdns_request('put', server=server, path=path, acceptable_range=range(200, 500))


def create_zone(domain, nameservers):
    """
    Commands pdns to create a zone with the given name and nameservers.
    """
    name = domain.name
    if not name.endswith('.'):
        name += '.'

    salt = '%016x' % random.randrange(16**16)
    payload = {'name': name, 'kind': 'MASTER', 'dnssec': True,
               'nsec3param': '1 0 127 %s' % salt, 'nameservers': nameservers}
    _pdns_post(NSLORD, '/zones', payload)

    payload = {'name': name, 'kind': 'SLAVE', 'masters': [socket.gethostbyname('nslord')]}
    _pdns_post(NSMASTER, '/zones', payload)

    axfr_zone(domain)


def delete_zone(domain):
    """
    Commands pdns to delete a zone with the given name.
    """
    return _pdns_delete_zone(domain)


def get_keys(domain):
    """
    Retrieves a dict representation of the DNSSEC key information
    """
    r = _pdns_get(NSLORD, '/zones/%s/cryptokeys' % domain.pdns_id)
    return [{k: key[k] for k in ('dnskey', 'ds', 'flags', 'keytype')}
            for key in r.json()
            if key['active'] and key['keytype'] in ['csk', 'ksk']]


def get_zone(domain):
    """
    Retrieves a dict representation of the zone from pdns
    """
    r = _pdns_get(NSLORD, '/zones/' + domain.pdns_id)

    return r.json()


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


def set_rrsets(domain, rrsets, axfr=True):
    data = {
        'rrsets':
        [
            {
                'name': rrset.name, 'type': rrset.type, 'ttl': rrset.ttl,
                'changetype': 'REPLACE',
                'records': [
                    {'content': record.content, 'disabled': False}
                    for record in rrset.records.all()
                ]
            }
            for rrset in rrsets
        ]
    }
    _pdns_patch(NSLORD, '/zones/' + domain.pdns_id, data)

    if axfr:
        axfr_zone(domain)


def axfr_zone(domain):
    """
    Commands nsmaster to retrieve the zone from nslord.
    """
    _pdns_put(NSMASTER, '/zones/%s/axfr-retrieve' % domain.pdns_id)
