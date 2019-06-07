import json
import re
import requests

from django.core.exceptions import SuspiciousOperation

from api import settings as api_settings
from desecapi.exceptions import PDNSException

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


def _pdns_request(method, *, server, path, body=None, acceptable_range=range(200, 300)):
    data = json.dumps(body) if body else None
    if data is not None and len(data) > api_settings.PDNS_MAX_BODY_SIZE:
        raise PDNSException(detail='Payload too large', status=413)

    r = requests.request(method, settings[server]['base_url'] + path, data=data, headers=settings[server]['headers'])
    if r.status_code not in acceptable_range:
        raise PDNSException(r)

    return r


def _pdns_post(server, path, body):
    return _pdns_request('post', server=server, path=path, body=body)


def _pdns_patch(server, path, body):
    return _pdns_request('patch', server=server, path=path, body=body)


def _pdns_get(server, path):
    return _pdns_request('get', server=server, path=path, acceptable_range=range(200, 400))  # FIXME range


def _pdns_put(server, path):
    return _pdns_request('put', server=server, path=path, acceptable_range=range(200, 500))  # FIXME range


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
    return [{k: key[k] for k in ('dnskey', 'ds', 'flags', 'keytype')}
            for key in r.json()
            if key['active'] and key['keytype'] in ['csk', 'ksk']]


def get_zone(domain):
    """
    Retrieves a dict representation of the zone from pdns
    """
    r = _pdns_get(NSLORD, '/zones/' + pdns_id(domain.name))

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
