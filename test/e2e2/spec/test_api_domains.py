import datetime
import os

import time

import pytest
from conftest import DeSECAPIV1Client, NSLordClient, random_domainname, FaketimeShift

example_zonefile = """
@ 300 IN SOA get.desec.io. get.desec.io. 2021114126 86400 3600 2419200 3600
@ 300 IN RRSIG SOA 13 3 300 20220324000000 20220303000000 8312 @ XcZOyVwrEMjp1RGi+5rjk82hYbpzRPIm 5Nx8H4p5wlsCSViAOE9WKIv4TC6xH44l AY4CFBbb2e3iui/bzwQnoQ==
@ 3600 IN DNSKEY 257 3 13 q4/6eDL5bHn2hF7mbtpzGdUvIgaU2GE0 +BsPVYivqPYZrZlk/aAPpHpeUa/5giLM KhI4QPPy1uv2F6jw9RgPLw==
@ 3600 IN RRSIG DNSKEY 13 3 3600 20220324000000 20220303000000 8312 @ 9X44LeBCpmmrO3mJp2P6GFLenAeOLxhX 1ta2ACMTVwPVaHlz3rG4dgzseTp//YHz +DJSc7P3W9cCDkg5X4Q43g==
@ 3600 IN CDS 8312 13 2 bca8973bae3e58e697f0558ef55d3df835e6dd443c46ab5778904f186341c0d8
@ 3600 IN CDS 8312 13 4 c5fd0f288522d0e7eeaf7ddbbbb1d956a8cd7d1eba6e6f12ebe0926ed560ccfca480f6022bacff98c1767c61281466c5
@ 3600 IN RRSIG CDS 13 3 3600 20220324000000 20220303000000 8312 @ MIGwQf72bq55bQlGMSB5WSKV6iFoELKM 82IBLqU5kNgSHGOVhxAuGL8H/dktLgxY uQEXO0NFRIODq+8zmIovYg==
@ 60 IN A 83.219.1.24
@ 60 IN RRSIG A 13 3 60 20220324000000 20220303000000 8312 @ WrjVe9hYjmZNG5nysOEbAOp24DLPJ/9k xucV/5T4wXYXyzeJCxqV3DQ9B7fj6HZX zP8EJeZ9xxsqL9M6myN3vQ==
@ 3600 IN CDNSKEY 257 3 13 q4/6eDL5bHn2hF7mbtpzGdUvIgaU2GE0 +BsPVYivqPYZrZlk/aAPpHpeUa/5giLM KhI4QPPy1uv2F6jw9RgPLw==
@ 3600 IN RRSIG CDNSKEY 13 3 3600 20220324000000 20220303000000 8312 @ yRRuPINa9fAuwtdYL0Ggy5IuLDJMuSS1 ydc9WjnUR6uLPM0TGVOvwRk32ItoSOcJ bSfRZshxI/u27kc19eEQAw==
@ 86400 IN NS ns1.example.
@ 86400 IN NS ns2.example.
@ 3600 IN RRSIG NS 13 3 3600 20220324000000 20220303000000 8312 @ mQSIpFAaOZMQpvq9DGJvXKCTuwcH+VyS HZ4EAKiXN50+w6g6+Ogik8GwmrMBG7/4 tC9mxMOIsBn/86GPR8eYzg==
@ 3600 IN NSEC3PARAM 1 0 0 -
@ 3600 IN RRSIG NSEC3PARAM 13 3 3600 20220324000000 20220303000000 8312 @ bePOvsK3Npl1GsKRBDtdipKIOVaz9JJX Ka/ccAHZPp8GSwDQFmyBt0l1JWJvGzT0 L+wVQMCsk/rpxrWsUanwdg==
p6gfsf6t5tvesh74gd38o43u26q8kqes 300 IN NSEC3 1 0 0 - p6gfsf6t5tvesh74gd38o43u26q8kqes A NS SOA RRSIG DNSKEY NSEC3PARAM CDS CDNSKEY
p6gfsf6t5tvesh74gd38o43u26q8kqes 300 IN RRSIG NSEC3 13 4 300 20220324000000 20220303000000 8312 @ b3ZfxXKLJrOGVTAqmQeEZSjbT7iYKtyM M6Wl6HilgjYTzWPvpiwpFSrETWWP5A19 wKRmT4Nh6nnbTDalUvXLsQ==
"""


def test_create(api_user: DeSECAPIV1Client):
    assert len(api_user.domain_list()) == 0
    assert api_user.domain_create(random_domainname()).status_code == 201
    assert len(api_user.domain_list()) == 1
    weeks_since_epoch = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).days // 7
    assert NSLordClient.query(api_user.domain, 'SOA')[0].serial == \
           int(f'{datetime.date.today().year:4n}{datetime.date.today().month:02n}{weeks_since_epoch + 1:4n}')


def test_create_and_import(api_user: DeSECAPIV1Client):
    assert len(api_user.domain_list()) == 0
    assert api_user.domain_create(random_domainname(), example_zonefile).status_code == 201
    assert len(api_user.domain_list()) == 1
    api_user.assert_rrsets({
        ('', 'NS'): (
            int(os.environ["DESECSTACK_NSLORD_DEFAULT_TTL"]),
            {f"{name}." for name in os.environ["DESECSTACK_NS"].split(" ")}
        ),
        ('', 'A'): (
            max(60, int(os.environ["DESECSTACK_MINIMUM_TTL_DEFAULT"])),
            {'83.219.1.24'}
        ),
    })
    api_user.assert_rrsets({
        ('', 'RRSIG'): (None, None),
        ('', 'NSEC3PARAM'): (None, None),
        ('', 'CDS'): (None, None),
        ('', 'DNSKEY'): (None, None),
    }, via_dns=False)
    assert NSLordClient.query(api_user.domain, 'NSEC3PARAM')[0].to_text() == '1 0 0 -'


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
