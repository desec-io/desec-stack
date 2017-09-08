import requests
import json
from desecapi import settings
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


def _delete_or_replace_rrset(name, rr_type, value, ttl=60):
    """
    Return pdns API json to either replace or delete a record set, depending on whether value is empty or not.
    """
    if value:
        return \
            {
                "records": [
                    {
                        "type": rr_type,
                        "name": name,
                        "disabled": False,
                        "content": value,
                    }
                ],
                "ttl": ttl,
                "changetype": "REPLACE",
                "type": rr_type,
                "name": name,
            }
    else:
        return \
            {
                "changetype": "DELETE",
                "type": rr_type,
                "name": name
            }


def create_zone(domain, kind='NATIVE'):
    """
    Commands pdns to create a zone with the given name.
    """
    name = domain.name
    if not name.endswith('.'):
        name += '.'

    payload = {
        "name": name,
        "kind": kind.upper(),
        "masters": [],
        "nameservers": [
            "ns1.desec.io.",
            "ns2.desec.io."
        ]
    }
    _pdns_post('/zones', payload)

    # Don't forget to import automatically generated RRsets (specifically, NS)
    domain.sync_from_pdns()

def delete_zone(domain):
    """
    Commands pdns to delete a zone with the given name.
    """
    _pdns_delete('/zones/' + domain.pdns_id)


def get_keys(domain):
    """
    Retrieves a JSON representation of the DNSSEC key information
    """
    try:
        r = _pdns_get('/zones/%s/cryptokeys' % domain.pdns_id)
        keys = [{k: key[k] for k in ('dnskey', 'ds', 'flags', 'keytype')}
                for key in r.json() if key['active'] and key['keytype'] in ['csk', 'ksk']]
    except:
        keys = []

    return keys


def get_zone(domain):
    """
    Retrieves a JSON representation of the zone from pdns
    """
    r = _pdns_get('/zones/' + domain.pdns_id)

    return r.json()


def get_rrsets(domain):
    """
    Retrieves a JSON representation of the RRsets in a given zone, optionally restricting to a name and RRset type 
    """
    return [{'domain': domain,
             'subname': rrset['name'][:-(len(domain.name) + 2)],
             'type': rrset['type'],
             'records_data': [{'content': record['content']}
                              for record in rrset['records']],
             'ttl': rrset['ttl']}
            for rrset in get_zone(domain)['rrsets']]


def set_rrset(rrset):
    return set_rrsets(rrset.domain, [rrset])


def set_rrsets(domain, rrsets):
    data = {'rrsets':
        [{'name': rrset.name, 'type': rrset.type, 'ttl': rrset.ttl,
          'changetype': 'REPLACE',
          'records': [{'content': record.content, 'disabled': False}
                      for record in rrset.records.all()]
          }
         for rrset in rrsets]
    }
    _pdns_patch('/zones/' + domain.pdns_id, data)


def notify_zone(domain):
    """
    Commands pdns to notify the zone to the pdns slaves.
    """
    _pdns_put('/zones/%s/notify' % domain.pdns_id)


def set_dyn_records(domain):
    """
    Commands pdns to set the A and AAAA record for the zone with the given name to the given record values.
    Only supports one A, one AAAA record.
    If a or aaaa is empty, pdns will be commanded to delete the record.
    """
    _pdns_patch('/zones/' + domain.pdns_id, {
        "rrsets": [
            _delete_or_replace_rrset(domain.name + '.', 'a', domain.arecord),
            _delete_or_replace_rrset(domain.name + '.', 'aaaa', domain.aaaarecord),
            _delete_or_replace_rrset('_acme-challenge.%s.' % domain.name, 'txt', '"%s"' % domain.acme_challenge),
        ]
    })

    # Don't forget to import the updated RRsets
    domain.sync_from_pdns()

    notify_zone(domain)


def set_rrset_in_parent(domain, rr_type, value):
    """
    Commands pdns to set or delete a record set for the zone with the given name.
    If value is empty, the rrset will be deleted.
    """
    parent_id = domain.pdns_id.split('.', 1)[1]

    _pdns_patch('/zones/' + parent_id, {
        "rrsets": [
            _delete_or_replace_rrset(domain.name + '.', rr_type, value),
        ]
    })
