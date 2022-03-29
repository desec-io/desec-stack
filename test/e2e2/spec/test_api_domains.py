import time

import pytest
from conftest import DeSECAPIV1Client, NSLordClient, random_domainname, FaketimeShift


def test_create(api_user: DeSECAPIV1Client):
    assert len(api_user.domain_list()) == 0
    assert api_user.domain_create(random_domainname()).status_code == 201
    assert len(api_user.domain_list()) == 1
    assert NSLordClient.query(api_user.domain, 'SOA')[0].serial >= int(time.time())


def test_get(api_user_domain: DeSECAPIV1Client):
    domain = api_user_domain.get(f"/domains/{api_user_domain.domain}/").json()
    assert {rr.to_text() for rr in NSLordClient.query(api_user_domain.domain, 'CDS')} == set(domain['keys'][0]['ds'])
    assert domain['name'] == api_user_domain.domain


def test_modify(api_user_domain: DeSECAPIV1Client):
    old_serial = NSLordClient.query(api_user_domain.domain, 'SOA')[0].serial
    api_user_domain.rr_set_create(api_user_domain.domain, 'A', ['127.0.0.1'])
    assert NSLordClient.query(api_user_domain.domain, 'SOA')[0].serial > old_serial


def test_rrsig_rollover(api_user_domain: DeSECAPIV1Client):
    old_serial = NSLordClient.query(api_user_domain.domain, 'SOA')[0].serial
    with FaketimeShift(days=7):
        assert NSLordClient.query(api_user_domain.domain, 'SOA')[0].serial > old_serial


def test_destroy(api_user_domain: DeSECAPIV1Client):
    n = len(api_user_domain.domain_list())
    assert api_user_domain.domain_destroy(api_user_domain.domain).status_code == 204
    assert len(api_user_domain.domain_list()) == n - 1


@pytest.mark.skip  # TODO currently broken
def test_recreate(api_user_domain: DeSECAPIV1Client):
    name = api_user_domain.domain
    old_serial = NSLordClient.query(name, 'SOA')[0].serial
    assert api_user_domain.domain_destroy(name).status_code == 204
    assert api_user_domain.domain_create(name).status_code == 201
    assert NSLordClient.query(name, 'SOA')[0].serial > old_serial
