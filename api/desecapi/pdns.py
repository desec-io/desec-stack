import json
import random

import requests

from api import settings
from desecapi.exceptions import PdnsException

headers_nslord = {
    'Accept': 'application/json',
    'User-Agent': 'desecapi',
    'X-API-Key': settings.NSLORD_PDNS_API_TOKEN,
}

headers_nsmaster = {
    'User-Agent': 'desecapi',
    'X-API-Key': settings.NSMASTER_PDNS_API_TOKEN,
}


def _pdns_delete_zone(domain):
    path = '/zones/' + domain.pdns_id

    # We first delete the zone from nslord, the main authoritative source of our DNS data.
    # However, we do not want to wait for the zone to expire on the slave ("nsmaster").
    # We thus issue a second delete request on nsmaster to delete the zone there immediately.
    r1 = requests.delete(settings.NSLORD_PDNS_API + path, headers=headers_nslord)
    if r1.status_code < 200 or r1.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r1.status_code == 422 and 'Could not find domain' in r1.text:
            pass
        else:
            raise PdnsException(r1)

    # Delete from nsmaster as well
    r2 = requests.delete(settings.NSMASTER_PDNS_API + path, headers=headers_nsmaster)
    if r2.status_code < 200 or r2.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r2.status_code == 422 and 'Could not find domain' in r2.text:
            pass
        else:
            raise PdnsException(r2)

    return r1, r2


def _pdns_request(method, path, body=None, acceptable_range=range(200, 300)):
    data = json.dumps(body) if body else None
    if data is not None and len(data) > settings.PDNS_MAX_BODY_SIZE:
        raise PdnsException(detail='Payload too large', status=413)

    r = requests.request(method, settings.NSLORD_PDNS_API + path, data=data, headers=headers_nslord)
    if r.status_code not in acceptable_range:
        raise PdnsException(r)

    return r


def _pdns_post(path, body):
    return _pdns_request('post', path, body)


def _pdns_patch(path, body):
    return _pdns_request('patch', path, body)


def _pdns_get(path):
    return _pdns_request('get', path, acceptable_range=range(200, 400))


def _pdns_put(path):
    return _pdns_request('put', path, acceptable_range=range(200, 500))


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
    _pdns_post('/zones', payload)

    notify_zone(domain)


def delete_zone(domain):
    """
    Commands pdns to delete a zone with the given name.
    """
    return _pdns_delete_zone(domain)


def get_keys(domain):
    """
    Retrieves a dict representation of the DNSSEC key information
    """
    r = _pdns_get('/zones/%s/cryptokeys' % domain.pdns_id)
    return [{k: key[k] for k in ('dnskey', 'ds', 'flags', 'keytype')}
            for key in r.json()
            if key['active'] and key['keytype'] in ['csk', 'ksk']]


def get_zone(domain):
    """
    Retrieves a dict representation of the zone from pdns
    """
    r = _pdns_get('/zones/' + domain.pdns_id)

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


def set_rrsets(domain, rrsets, notify=True):
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
    _pdns_patch('/zones/' + domain.pdns_id, data)

    if notify:
        notify_zone(domain)


def notify_zone(domain):
    """
    Commands pdns to notify the zone to the pdns slaves.
    """
    _pdns_put('/zones/%s/notify' % domain.pdns_id)
