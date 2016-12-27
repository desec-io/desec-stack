import requests
import json
from desecapi import settings


headers = {
    'User-Agent': 'desecapi',
    'X-API-Key': settings.POWERDNS_API_TOKEN,
}


def normalize_hostname(name):
    if '/' in name or '?' in name:
        raise Exception('Invalid hostname ' + name)
    return name if name.endswith('.') else name + '.'


def _pdns_post(url, body):
    r = requests.post(settings.POWERDNS_API + url, data=json.dumps(body), headers=headers)
    if r.status_code < 200 or r.status_code >= 300:
        raise Exception(r.text)
    return r


def _pdns_patch(url, body):
    r = requests.patch(settings.POWERDNS_API + url, data=json.dumps(body), headers=headers)
    if r.status_code < 200 or r.status_code >= 300:
        raise Exception(r.text)
    return r


def _pdns_get(url):
    r = requests.get(settings.POWERDNS_API + url, headers=headers)
    if (r.status_code < 200 or r.status_code >= 300) and r.status_code != 404:
        raise Exception(r.text)
    return r


def _delete_or_replace_rrset(name, type, value, ttl=60):
    """
    Return pdns API json to either replace or delete a record set, depending on value is empty or not.
    """
    if value != "":
        return \
            {
                "records": [
                    {
                        "type": type,
                        "name": name,
                        "disabled": False,
                        "content": value,
                    }
                ],
                "ttl": ttl,
                "changetype": "REPLACE",
                "type": type,
                "name": name,
            }
    else:
        return \
            {
                "changetype": "DELETE",
                "type": type,
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


def zone_exists(name):
    """
    Returns whether pdns knows a zone with the given name.
    """
    return _pdns_get('/zones/' + normalize_hostname(name)).status_code != 404


def set_dyn_records(name, a, aaaa):
    """
    Commands pdns to set the A and AAAA record for the zone with the given name to the given record values.
    Only supports one A, one AAAA record.
    If a or aaaa is None, pdns will be commanded to delete the record.
    """
    name = normalize_hostname(name)

    _pdns_patch('/zones/' + name, {
        "rrsets": [
            _delete_or_replace_rrset(name, 'a', a),
            _delete_or_replace_rrset(name, 'aaaa', aaaa),
        ]
    })
