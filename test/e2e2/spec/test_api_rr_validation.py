from time import sleep
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
        'mG8EXtVIsRMFK4EEACIDAwQSZPNqE4tS xLFJYhX+uabSgMrhOqUizJhkLx82',  # key incomplete due to 500 byte limit
    ],
    'PTR': ['example.com.', '*.example.com.'],
    'RP': ['hostmaster.example.com. .'],
    # 'SMIMEA': ['3 1 0 aabbccddeeff'],
    'SPF': [
        '"v=spf1 ip4:10.1" ".1.1 ip4:127" ".0.0.0/16 ip4:192.168.0.0/27 include:example.com -all"',
        '"v=spf1 include:example.com ~all"',
        '"v=spf1 ip4:10.1.1.1 ip4:127.0.0.0/16 ip4:192.168.0.0/27 include:example.com -all"',
        '"spf2.0/pra,mfrom ip6:2001:558:fe14:76:68:87:28:0/120 -all"',
    ],
    'SRV': ['0 0 0 .', '100 1 5061 example.com.'],
    'SSHFP': ['2 2 aabbcceeddff'],
    'TLSA': ['3 1 1 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',],
    'TXT': [
        '"foobar"',
        '"foo" "bar"',
        '"foo" "" "bar"',
        '"" "" "foo" "" "bar"',
        '"new\\010line"',
        f'"{"a" * 255}" "{"a" * 243}"',  # 500 byte total wire length
    ],
    'URI': ['10 1 "ftp://ftp1.example.com/public"'],
}


VALID_RECORDS_NON_CANONICAL = {
    'A': ['127.0.0.3'],
    'AAAA': ['0000::0000:0003'],
    'AFSDB': ['03 turquoise.FEMTO.edu.'],
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
        'mG8EXtVIsRMFK4EEACIDAwQSZPNqE4tSxLFJYhX+uabSgMrhOqUizJhkLx82',  # key incomplete due to 500 byte limit
    ],
    'PTR': ['EXAMPLE.TEST.'],
    'RP': ['hostmaster.EXAMPLE.com. .'],
    # 'SMIMEA': ['3 01 0 aabbccDDeeff'],
    'SPF': [],
    'SRV': ['100 01 5061 example.com.'],
    'SSHFP': ['02 2 aabbcceeddff'],
    'TLSA': ['3 0001 1 000AAAAAAABBAAAAAAAAAAAAAAAAAAAAAAAA',],
    'TXT': [
        f'"{"a" * 498}"',
        '"🧥 👚 👕 👖 👔 👗 👙 👘 👠 👡 👢 👞 👟 🥾 🥿  🧦 🧤 🧣 🎩 🧢 👒 🎓 ⛑ 👑 👝 👛 👜 💼 🎒 "',
        '"🧥 👚 👕 👖 👔 👗 👙 👘 👠 👡 👢 👞 👟 🥾 🥿  🧦 🧤 🧣 🎩 🧢 👒 🎓 ⛑ 👑 👝 👛 👜 💼 🎒 👓 🕶 🥽 🥼 🌂 🧵"',
    ],
    'URI': ['10 01 "ftp://ftp1.example.test/public"',],
}


INVALID_RECORDS = {
    'A': ['127.0.0.999', '127.000.0.01', '127.0.0.256', '::1', 'foobar', '10.0.1', '10!'],
    'AAAA': ['::g', '1:1:1:1:1:1:1:1:', '1:1:1:1:1:1:1:1:1'],
    'AFSDB': ['example.com.', '1 1', '1 de'],
    'CAA': ['43235 issue "letsencrypt.org"'],
    'CERT': ['6 0 sadfdd=='],
    'CNAME': ['example.com', '10 example.com.'],
    'DHCID': ['x', 'xx', 'xxx'],
    'DLV': ['-34 13 1 aabbccddeeff'],
    'DS': ['-34 13 1 aabbccddeeff'],
    'EUI48': ['aa-bb-ccdd-ee-ff', 'AA-BB-CC-DD-EE-GG'],
    'EUI64': ['aa-bb-cc-dd-ee-ff-gg-11', 'AA-BB-C C-DD-EE-FF-00-11'],
    'HINFO': ['"ARMv8-A"', f'"a" "{"b" * 256}"'],
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
    # 'SMIMEA': ['3 1 0 aGVsbG8gd29ybGQh', 'x 0 0 aabbccddeeff'],
    'SPF': ['"v=spf1', 'v=spf1 include:example.com ~all'],
    'SRV': ['0 0 0 0', '100 5061 example.com.'],
    'SSHFP': ['aabbcceeddff'],
    'TLSA': ['3 1 1 AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'],
    'TXT': [
        'foob"ar',
        'v=spf1 include:example.com ~all',
        '"foo\nbar"',
        '"' + 124 * '🧥' + '==="',  # 501 byte total length
        '"\x00" "NUL byte yo"',
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
