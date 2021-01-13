from typing import List, Tuple

import pytest

from conftest import DeSECAPIV1Client, NSClient


def generate_params(dict_value_lists_by_type: dict) -> List[Tuple[str, str]]:
    return [
        (rr_type, value)
        for rr_type in dict_value_lists_by_type.keys()
        for value in dict_value_lists_by_type[rr_type]
    ]


VALID_RECORDS_CANONICAL = {
    'A': ['127.0.0.1', '127.0.0.2'],
    'AAAA': ['::1', '::2'],
    'AFSDB': ['2 turquoise.femto.edu.'],
    'APL': [
        # from RFC 3123 Sec. 4
        '1:192.168.32.0/21 !1:192.168.38.0/28',
        '1:192.168.42.0/26 1:192.168.42.64/26 1:192.168.42.128/25',
        '1:127.0.0.1/32 1:172.16.64.0/22',
        '1:224.0.0.0/4 2:ff00::/8',
    ],
    'CAA': [
        '128 issue "letsencrypt.org"', '128 iodef "mailto:desec@example.com"',
        '1 issue "letsencrypt.org"'
    ],
    'CERT': ['6 0 0 sadfdQ=='],
    'CNAME': ['example.com.'],
    'DHCID': ['aaaaaaaaaaaa', 'xxxx'],
    'DLV': [
        '39556 13 1 aabbccddeeff',
    ],
    'DS': [
        '39556 13 1 aabbccddeeff',
    ],
    'EUI48': ['aa-bb-cc-dd-ee-ff'],
    'EUI64': ['aa-bb-cc-dd-ee-ff-00-11'],
    'HINFO': ['"ARMv8-A" "Linux"'],
    'HTTPS': ['1 h3POOL.exaMPLe. alpn=h2,h3 echconfig="MTIzLi4uCg=="'],
    # 'IPSECKEY': ['12 0 2 . asdfdf==', '03 1 1 127.0.00.1 asdfdf==', '12 3 1 example.com. asdfdf==',],
    'KX': ['4 example.com.', '28 io.'],
    'LOC': [
        '23 12 59.000 N 42 22 48.500 W 65.00m 20.00m 10.00m 10.00m',
    ],
    'MX': ['10 example.com.', '20 1.1.1.1.'],
    'NAPTR': [
        '100 50 "s" "z3950+I2L+I2C" "" _z3950._tcp.gatech.edu.',
    ],
    'NS': ['ns1.example.com.'],
    'OPENPGPKEY': [
        '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',
    ],
    'PTR': ['example.com.', '*.example.com.'],
    'RP': ['hostmaster.example.com. .'],
    'SMIMEA': ['3 1 0 aabbccddeeff'],
    'SPF': [
        '"v=spf1 ip4:10.1" ".1.1 ip4:127" ".0.0.0/16 ip4:192.168.0.0/27 include:example.com -all"',
        '"v=spf1 include:example.com ~all"',
        '"v=spf1 ip4:10.1.1.1 ip4:127.0.0.0/16 ip4:192.168.0.0/27 include:example.com -all"',
        '"spf2.0/pra,mfrom ip6:2001:558:fe14:76:68:87:28:0/120 -all"',
    ],
    'SRV': ['0 0 0 .', '100 1 5061 example.com.'],
    'SSHFP': ['2 2 aabbcceeddff'],
    'SVCB': ['2 sVc2.example.NET. port=1234 echconfig="MjIyLi4uCg==" ipv6hint=2001:db8::2'],
    'TLSA': ['3 0 2 696b8f6b92a913560b23ef5720c378881faffe74432d04eb35db957c0a93987b47adf26abb5dac10ba482597ae16edb069b511bec3e26010d1927bf6392760dd 696b8f6b92a913560b23ef5720c378881faffe74432d04eb35db957c0a93987b47adf26abb5dac10ba482597ae16edb069b511bec3e26010d1927bf6392760dd',],
    'TXT': [
        '"foobar"',
        '"foo" "bar"',
        '"foo" "" "bar"',
        '"" "" "foo" "" "bar"',
        r'"new\010line"',
        r'"\000" "NUL byte yo"',
        f'"{"a" * 255}" "{"a" * 243}"',  # 500 byte total wire length
    ],
    'URI': ['10 1 "ftp://ftp1.example.com/public"'],
}


VALID_RECORDS_NON_CANONICAL = {
    'A': ['127.0.0.3'],
    'AAAA': ['0000::0000:0003'],
    'AFSDB': ['03 turquoise.FEMTO.edu.'],
    'APL': ['2:FF00:0:0:0:0::/8 !1:192.168.38.0/28'],
    'CAA': ['0128 "issue" "letsencrypt.org"'],
    'CERT': ['06 00 00 sadfee=='],
    'CNAME': ['EXAMPLE.TEST.'],
    'DHCID': ['aa aaa  aaaa a a a', 'xxxx'],
    'DLV': [
        '6454 8 2 5CBA665A006F6487625C6218522F09BD3673C25FA10F25CB18459AA1 0DF1F520',
        '6454 8 2 5C BA665A006F6487625C6218522F09BD3673C25FA10F25CB18459AA1 0DF1F520',
    ],
    'DS': [
        '6454 8 2 5CBA665A006F6487625C6218522F09BD3673C25FA10F25CB18459AA1 0DF1F520',
        '6454 8 2 5C BA665A006F6487625C6218522F09BD3673C25FA10F25CB18459AA1 0DF1F520',
    ],
    'EUI48': ['AA-BB-CC-DD-EE-F1'],
    'EUI64': ['AA-BB-CC-DD-EE-FF-00-12'],
    'HINFO': ['cpu os'],
    'HTTPS': [
        # from https://tools.ietf.org/html/draft-ietf-dnsop-svcb-https-02#section-10.3, with echconfig base64'd
        '1 . alpn=h3',
        '0 pool.svc.example.',
        '1 h3pool.example. alpn=h2,h3 echconfig="MTIzLi4uCg=="',
        '2 .      alpn=h2 echconfig="YWJjLi4uCg=="',
        # made-up (not from RFC)
        '1 pool.svc.example. no-default-alpn port=1234 ipv4hint=192.168.123.1',
        '2 . echconfig=... key65333=ex1 key65444=ex2 mandatory=key65444,echconfig',  # see #section-7
    ],
    # 'IPSECKEY': ['12 0 2 . asdfdf==', '03 1 1 127.0.00.1 asdfdf==', '12 3 1 example.com. asdfdf==',],
    'KX': ['012 example.TEST.'],
    'LOC': [
        '023 012 59 N 042 022 48.500 W 65.00m 20.00m 10.00m 10.00m',
    ],
    'MX': ['10 010.1.1.1.'],
    'NAPTR': [
        '100  50  "s"  "z3950+I2L+I2C"     ""  _z3950._tcp.gatech.edu.',
    ],
    'NS': ['EXaMPLE.COM.'],
    'OPENPGPKEY': [
        'mG8EXtVIsRMFK4EEAC==',
        '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',
    ],
    'PTR': ['EXAMPLE.TEST.'],
    'RP': ['hostmaster.EXAMPLE.com. .'],
    'SMIMEA': ['3 01 0 aabbccDDeeff'],
    'SPF': [],
    'SRV': ['100 01 5061 example.com.'],
    'SSHFP': ['02 2 aabbcceeddff'],
    'SVCB': [
        '0 svc4-baz.example.net.',
        '1 . key65333=...',
        '2 svc2.example.net. echconfig="MjIyLi4uCg==" ipv6hint=2001:db8::2 port=1234',
    ],
    'TLSA': ['003 00 002 696B8F6B92A913560b23ef5720c378881faffe74432d04eb35db957c0a93987b47adf26abb5dac10ba482597ae16edb069b511bec3e26010d1927bf6392760dd',],
    'TXT': [
        f'"{"a" * 498}"',
        '"' + 124 * '🧥' + '==="',  # 501 byte total length
        '"🧥 👚 👕 👖 👔 👗 👙 👘 👠 👡 👢 👞 👟 🥾 🥿  🧦 🧤 🧣 🎩 🧢 👒 🎓 ⛑ 👑 👝 👛 👜 💼 🎒 "',
        '"🧥 👚 👕 👖 👔 👗 👙 👘 👠 👡 👢 👞 👟 🥾 🥿  🧦 🧤 🧣 🎩 🧢 👒 🎓 ⛑ 👑 👝 👛 👜 💼 🎒 👓 🕶 🥽 🥼 🌂 🧵"',
    ],
    'URI': ['10 01 "ftp://ftp1.example.test/public"',],
}


INVALID_RECORDS = {
    'A': ['127.0.0.999', '127.000.0.01', '127.0.0.256', '::1', 'foobar', '10.0.1', '10!'],
    'AAAA': ['::g', '1:1:1:1:1:1:1:1:', '1:1:1:1:1:1:1:1:1'],
    'AFSDB': ['example.com.', '1 1', '1 de'],
    'APL': [
        '0:192.168.32.0/21 !1:192.168.38.0/28',
        '1:192.168.32.0/21 !!1:192.168.38.0/28',
        '1:192.168.32.0/33',
        '18:12345/2',
        '1:127.0.0.1',
        '2:::/129',
    ],
    'CAA': ['43235 issue "letsencrypt.org"'],
    'CERT': ['6 0 sadfdd=='],
    'CNAME': ['example.com', '10 example.com.'],
    'DHCID': ['x', 'xx', 'xxx'],
    'DLV': ['-34 13 1 aabbccddeeff'],
    'DS': ['-34 13 1 aabbccddeeff'],
    'EUI48': ['aa-bb-ccdd-ee-ff', 'AA-BB-CC-DD-EE-GG'],
    'EUI64': ['aa-bb-cc-dd-ee-ff-gg-11', 'AA-BB-C C-DD-EE-FF-00-11'],
    'HINFO': ['"ARMv8-A"', f'"a" "{"b" * 256}"'],
    'HTTPS': [
        # from https://tools.ietf.org/html/draft-ietf-dnsop-svcb-https-02#section-10.3, with echconfig base64'd
        '1 h3pool alpn=h2,h3 echconfig="MTIzLi4uCg=="',
        # made-up (not from RFC)
        '0 pool.svc.example. no-default-alpn port=1234 ipv4hint=192.168.123.1',  # no keys in alias mode
        '1 pool.svc.example. no-default-alpn port=1234 ipv4hint=192.168.123.1 ipv4hint=192.168.123.2',  # dup
    ],
    # 'IPSECKEY': [],
    'KX': ['-1 example.com', '10 example.com'],
    'LOC': ['23 12 61.000 N 42 22 48.500 W 65.00m 20.00m 10.00m 10.00m', 'foo', '1.1.1.1'],
    'MX': ['10 example.com', 'example.com.', '-5 asdf.', '65537 asdf.'],
    'NAPTR': ['100  50  "s"  "z3950+I2L+I2C"     ""  _z3950._tcp.gatech.edu',
              '100  50  "s"     ""  _z3950._tcp.gatech.edu.',
              '100  50  3 2  "z3950+I2L+I2C"     ""  _z3950._tcp.gatech.edu.'],
    'NS': ['ns1.example.com', '127.0.0.1'],
    'OPENPGPKEY': ['1 2 3'],
    'PTR': ['"example.com."', '10 *.example.com.'],
    'RP': ['hostmaster.example.com.', '10 foo.'],
    'SMIMEA': ['3 1 0 aGVsbG8gd29ybGQh', 'x 0 0 aabbccddeeff'],
    'SPF': ['"v=spf1', 'v=spf1 include:example.com ~all'],
    'SRV': ['0 0 0 0', '100 5061 example.com.'],
    'SSHFP': ['aabbcceeddff'],
    'SVCB': [
        '0 svc4-baz.example.net. keys=val',
        '1 not.fully.qualified key65333=...',
        '2 duplicate.key. echconfig="MjIyLi4uCg==" echconfig="MjIyLi4uCg=="',
    ],
    'TLSA': ['3 1 1 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'],
    'TXT': [
        'foob"ar',
        'v=spf1 include:example.com ~all',
        '"foo\nbar"',
        '"\x00" "illegal hex representation"',
    ],
    'URI': ['"1" "2" "3"'],
}
INVALID_RECORDS_PARAMS = [(rr_type, value) for rr_type in INVALID_RECORDS.keys() for value in INVALID_RECORDS[rr_type]]


def test_soundness():
    assert INVALID_RECORDS.keys() == VALID_RECORDS_CANONICAL.keys() == VALID_RECORDS_NON_CANONICAL.keys()


@pytest.mark.parametrize("rr_type,value", generate_params(VALID_RECORDS_CANONICAL))
def test_create_valid_canonical(api_user_domain: DeSECAPIV1Client, ns_lord: NSClient, rr_type: str, value: str):
    assert api_user_domain.rr_set_create(api_user_domain.domains[0], rr_type, [value], subname="a").status_code == 201
    assert ns_lord.query(f"a.{api_user_domain.domains[0]}", rr_type) == {value}


@pytest.mark.parametrize("rr_type,value", generate_params(VALID_RECORDS_NON_CANONICAL))
def test_create_valid_non_canonical(api_user_domain: DeSECAPIV1Client, ns_lord: NSClient, rr_type: str, value: str):
    assert api_user_domain.rr_set_create(api_user_domain.domains[0], rr_type, [value], subname="a").status_code == 201
    assert len(ns_lord.query(f"a.{api_user_domain.domains[0]}", rr_type)) == 1


@pytest.mark.parametrize("rr_type,value", INVALID_RECORDS_PARAMS)
def test_create_invalid(api_user_domain: DeSECAPIV1Client, rr_type: str, value: str):
    assert api_user_domain.rr_set_create(api_user_domain.domains[0], rr_type, [value]).status_code == 400
