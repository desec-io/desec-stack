import requests
import json
from jq import jq
from desecapi import settings


headers_nslord = {
    'Accept': 'application/json',
    'User-Agent': 'desecapi',
    'X-API-Key': settings.NSLORD_PDNS_API_TOKEN,
}

headers_nsmaster = {
    'User-Agent': 'desecapi',
    'X-API-Key': settings.NSMASTER_PDNS_API_TOKEN,
}


def normalize_hostname(name):
    if '/' in name or '?' in name:
        raise Exception('Invalid hostname ' + name)
    return name if name.endswith('.') else name + '.'


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
            raise Exception(r1.text)

    # Delete from nsmaster as well
    r2 = requests.delete(settings.NSMASTER_PDNS_API + url, headers=headers_nsmaster)
    if r2.status_code < 200 or r2.status_code >= 300:
        # Deletion technically does not fail if the zone didn't exist in the first place
        if r2.status_code == 422 and 'Could not find domain' in r2.text:
            pass
        else:
            raise Exception(r2.text)

    return (r1, r2)


def _pdns_post(url, body):
    r = requests.post(settings.NSLORD_PDNS_API + url, data=json.dumps(body), headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 300:
        raise Exception(r.text)
    return r


def _pdns_patch(url, body):
    r = requests.patch(settings.NSLORD_PDNS_API + url, data=json.dumps(body), headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 300:
        raise Exception(r.text)
    return r


def _pdns_get(url):
    r = requests.get(settings.NSLORD_PDNS_API + url, headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 500:
        raise Exception(r.text)
    return r


def _pdns_put(url):
    r = requests.put(settings.NSLORD_PDNS_API + url, headers=headers_nslord)
    if r.status_code < 200 or r.status_code >= 500:
        raise Exception(r.text)
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


def create_zone(name, kind='NATIVE'):
    """
    Commands pdns to create a zone with the given name.
    """
    payload = {
        "name": normalize_hostname(name),
        "kind": kind.upper(),
        "masters": [],
        "nameservers": [
            "ns1.desec.io.",
            "ns2.desec.io."
        ]
    }
    _pdns_post('/zones', payload)


def delete_zone(name):
    """
    Commands pdns to delete a zone with the given name.
    """
    _pdns_delete('/zones/' + normalize_hostname(name))


def get_zone(name):
    """
    Retrieves a JSON representation of the zone from pdns
    """
    r = _pdns_get('/zones/' + normalize_hostname(name))

    return r.json()


def get_rrsets(name, subname = None, type = None):
    """
    Retrieves a JSON representation of the RRsets in a given zone, optionally restricting to a name and RRset type 
    """
    fullname = '.'.join(filter(None, [subname, name])) + '.'

    rrsets = get_zone(name)['rrsets']
    rrsets = [rrset for rrset in rrsets \
              if (subname == None or rrset['name'] == fullname) and (type == None or rrset['type'] == type) \
        ]

    # Make sure that if subname and type are given, we get one or none RRsets
    assert subname == None or type == None or len(rrsets) <= 1, \
            "pdns returned multiple RRsets of type %s for %s (zone: %s)" % (type, fullname, name)

    return jq("[.[] | {name: .name, records: [.records[] | .content], ttl: .ttl, type: .type}]").transform(rrsets)


def set_rrsets(name, rrsets):
    name = normalize_hostname(name)

    data = jq('{"rrsets": [ .[] | { "name": .name, "type": .type, "ttl": .ttl, "changetype": "REPLACE", "records": [ .records[] | { "content": ., "disabled": false } ] } ] }').transform(rrsets)
    _pdns_patch('/zones/' + name, data)


def zone_exists(name):
    """
    Returns whether pdns knows a zone with the given name.
    """
    reply = _pdns_get('/zones/' + normalize_hostname(name))
    if reply.status_code == 200:
        return True
    elif reply.status_code == 422 and 'Could not find domain' in reply.text:
        return False
    else:
        raise Exception(reply.text)


def notify_zone(name):
    """
    Commands pdns to notify the zone to the pdns slaves.
    """
    _pdns_put('/zones/%s/notify' % normalize_hostname(name))


def set_dyn_records(name, a, aaaa, acme_challenge=''):
    """
    Commands pdns to set the A and AAAA record for the zone with the given name to the given record values.
    Only supports one A, one AAAA record.
    If a or aaaa is empty, pdns will be commanded to delete the record.
    """
    name = normalize_hostname(name)

    _pdns_patch('/zones/' + name, {
        "rrsets": [
            _delete_or_replace_rrset(name, 'a', a),
            _delete_or_replace_rrset(name, 'aaaa', aaaa),
            _delete_or_replace_rrset('_acme-challenge.%s' % name, 'txt', '"%s"' % acme_challenge),
        ]
    })

    notify_zone(name)


def set_rrset(zone, name, rr_type, value):
    """
    Commands pdns to set or delete a record set for the zone with the given name.
    If value is empty, the rrset will be deleted.
    """
    zone = normalize_hostname(zone)
    name = normalize_hostname(name)

    _pdns_patch('/zones/' + zone, {
        "rrsets": [
            _delete_or_replace_rrset(name, rr_type, value),
        ]
    })
