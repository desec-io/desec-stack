import requests
import json
import random
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


def _pdns_delete(url):
    # We first delete the zone from nslord, the main authoritative source of our DNS data.
    # However, we do not want to wait for the zone to expire on the slave ("nsmaster").
    # We thus issue a second delete request on nsmaster to delete the zone there immediately.
    r1 = requests.delete(settings.NSLORD_PDNS_API + url, headers=headers_nslord)
    if r1.status_code < 200 or r1.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r1.status_code == 422 and 'Could not find domain' in r1.text:
            pass
        else:
            raise PdnsException(r1)

    # Delete from nsmaster as well
    r2 = requests.delete(settings.NSMASTER_PDNS_API + url, headers=headers_nsmaster)
    if r2.status_code < 200 or r2.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r2.status_code == 422 and 'Could not find domain' in r2.text:
            pass
        else:
            raise PdnsException(r2)

    return (r1, r2)


def _pdns_post(url, body):
    r = requests.post(settings.NSLORD_PDNS_API + url, data=json.dumps(body), headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 300:
        raise PdnsException(r)
    return r


def _pdns_patch(url, body):
    r = requests.patch(settings.NSLORD_PDNS_API + url, data=json.dumps(body), headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 300:
        raise PdnsException(r)
    return r


def _pdns_get(url):
    r = requests.get(settings.NSLORD_PDNS_API + url, headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 400:
        raise PdnsException(r)
    return r


def _pdns_put(url):
    r = requests.put(settings.NSLORD_PDNS_API + url, headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 500:
        raise PdnsException(r)
    return r


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
    _pdns_delete('/zones/' + domain.pdns_id)


def get_keys(domain):
    """
    Retrieves a dict representation of the DNSSEC key information
    """
    try:
        r = _pdns_get('/zones/%s/cryptokeys' % domain.pdns_id)
        return [{k: key[k] for k in ('dnskey', 'ds', 'flags', 'keytype')}
                for key in r.json()
                if key['active'] and key['keytype'] in ['csk', 'ksk']]
    except PdnsException as e:
        if e.status_code in [400, 404]:
            return []
        raise e


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
    data = {'rrsets':
        [{'name': rrset.name, 'type': rrset.type, 'ttl': rrset.ttl,
          'changetype': 'REPLACE',
          'records': [{'content': record.content, 'disabled': False}
                      for record in rrset.records.all()]
          }
         for rrset in rrsets]
    }
    _pdns_patch('/zones/' + domain.pdns_id, data)

    if notify:
        notify_zone(domain)


def notify_zone(domain):
    """
    Commands pdns to notify the zone to the pdns slaves.
    """
    _pdns_put('/zones/%s/notify' % domain.pdns_id)
