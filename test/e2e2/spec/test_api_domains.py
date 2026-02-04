import os
import time

import pytest

from conftest import (
    DeSECAPIV1Client,
    random_domainname,
    FaketimeShift,
)

DEFAULT_TTL = int(os.environ['DESECSTACK_NSLORD_DEFAULT_TTL'])

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


def ttl(value, min_ttl=int(os.environ['DESECSTACK_MINIMUM_TTL_DEFAULT'])):
    return max(min_ttl, min(86400, value))


def test_create(
    api_user: DeSECAPIV1Client,
    nslord_param: str | None,
    assert_all_nslord,
):
    assert len(api_user.domain_list()) == 0
    assert api_user.domain_create(
        random_domainname(), nslord=nslord_param
    ).status_code == 201
    assert len(api_user.domain_list()) == 1
    assert_all_nslord(
        assertion=lambda query: query(api_user.domain, 'SOA')[0].serial >= int(time.time()),
        retry_on=(AssertionError, TypeError),
    )


def test_create_import_export(
    api_user: DeSECAPIV1Client,
    nslord_param: str | None,
    assert_all_nslord,
):
    assert len(api_user.domain_list()) == 0
    domainname = random_domainname()
    assert (
        api_user.domain_create(domainname, example_zonefile, nslord=nslord_param).status_code
        == 201
    )
    assert len(api_user.domain_list()) == 1
    api_user.assert_rrsets({
        ('', 'NS'): (
            DEFAULT_TTL,
            {f"{name}." for name in os.environ["DESECSTACK_NS"].split(" ")}
        ),
        ('', 'A'): (
            ttl(60),
            {'83.219.1.24'}
        ),
    })
    api_user.assert_rrsets({
        ('', 'RRSIG'): (None, None),
        ('', 'NSEC3PARAM'): (None, None),
        ('', 'CDS'): (None, None),
        ('', 'DNSKEY'): (None, None),
        ('', 'SOA'): (None, None),
    }, via_dns=False)
    assert_all_nslord(
        assertion=lambda query: query(api_user.domain, 'NSEC3PARAM')[0].to_text() == '1 0 0 -',
        retry_on=(AssertionError, TypeError),
    )
    _, zonefile = api_user.get(f"/domains/{api_user.domain}/zonefile").content.decode().split("\n", 1)
    assert {l.strip() for l in zonefile.strip().split('\n') if 'SOA' not in l} == \
           {f"{domainname}.	{ttl(60)}	IN	A	83.219.1.24"} | \
           {
                f"{domainname}.	{DEFAULT_TTL}	IN	NS	{name}."
                for name in os.environ["DESECSTACK_NS"].split(" ")
           }


def test_get(api_user_domain: DeSECAPIV1Client, assert_all_nslord):
    domain = api_user_domain.get(f"/domains/{api_user_domain.domain}/").json()
    assert_all_nslord(
        assertion=lambda query: {rr.to_text() for rr in query(api_user_domain.domain, 'CDS')} == set(domain['keys'][0]['ds']),
        retry_on=(AssertionError, TypeError),
    )
    assert domain['name'] == api_user_domain.domain


def test_modify(api_user_domain: DeSECAPIV1Client, nslord_query, assert_all_nslord):
    old_serial = nslord_query(api_user_domain.domain, 'SOA')[0].serial
    api_user_domain.rr_set_create(api_user_domain.domain, 'A', ['127.0.0.1'])
    assert_all_nslord(
        assertion=lambda query: query(api_user_domain.domain, 'SOA')[0].serial > old_serial,
        retry_on=(AssertionError, TypeError),
    )


def test_rrsig_rollover(api_user_domain: DeSECAPIV1Client, nslord_query):
    old_serial = nslord_query(api_user_domain.domain, 'SOA')[0].serial
    with FaketimeShift(days=7):
        # TODO deploy faketime in desec-ns and nsmaster then use assert_all_ns
        assert nslord_query(api_user_domain.domain, 'SOA')[0].serial > old_serial


def test_destroy(api_user_domain: DeSECAPIV1Client):
    n = len(api_user_domain.domain_list())
    assert api_user_domain.domain_destroy(api_user_domain.domain).status_code == 204
    assert len(api_user_domain.domain_list()) == n - 1


@pytest.mark.skip  # TODO currently broken
def test_recreate(
    api_user_domain: DeSECAPIV1Client,
    nslord_param: str | None,
    nslord_query,
    assert_all_nslord,
):
    name = api_user_domain.domain
    old_serial = nslord_query(name, 'SOA')[0].serial
    assert api_user_domain.domain_destroy(name).status_code == 204
    assert api_user_domain.domain_create(name, nslord=nslord_param).status_code == 201
    assert_all_nslord(
        assertion=lambda query: query(name, 'SOA')[0].serial > old_serial,
        retry_on=(AssertionError, TypeError),
    )


def test_export(api_user_domain: DeSECAPIV1Client):
    """Check export of fresh domain (only contains NS and SOA RRs)"""
    for content_type in ['text/dns', 'application/json']:
        _, zonefile = api_user_domain.get(f"/domains/{api_user_domain.domain}/zonefile", headers={'Accept': content_type}).content.decode().split("\n", 1)
        assert {l.strip() for l in zonefile.strip().split('\n') if 'SOA' not in l} == \
               {
                    f"{api_user_domain.domain}.	{DEFAULT_TTL}	IN	NS	{name}."
                    for name in os.environ["DESECSTACK_NS"].split(" ")
               }
