from django.conf import settings
from django.utils import timezone

from desecapi.models import RRset, RR, Domain
from desecapi.pdns_change_tracker import KnotChangeTracker
from desecapi.tests.base import KnotDesecTestCase


class KnotChangeTrackerTestCase(KnotDesecTestCase):
    empty_domain = None
    simple_domain = None
    full_domain = None

    def setUp(self):
        super().setUp()
        self.empty_domain = Domain.objects.create(
            owner=self.user, name=self.random_domain_name(), nslord=Domain.NSLord.KNOT
        )
        self.simple_domain = Domain.objects.create(
            owner=self.user, name=self.random_domain_name(), nslord=Domain.NSLord.KNOT
        )
        self.full_domain = Domain.objects.create(
            owner=self.user, name=self.random_domain_name(), nslord=Domain.NSLord.KNOT
        )

    def test_rrset_does_not_exist_exception(self):
        tracker = KnotChangeTracker()
        tracker.__enter__()
        tracker._rr_set_updated(RRset(domain=self.empty_domain, subname="", type="A"))
        with self.assertRaises(ValueError):
            tracker.__exit__(None, None, None)


class RRTestCase(KnotChangeTrackerTestCase):
    """
    Base-class for checking change tracker behavior for all create, update, and delete operations of the RR model.
    """

    NUM_OWNED_DOMAINS = 3

    SUBNAME = "my_rr_set"
    TYPE = "A"
    TTL = 334
    CONTENT_VALUES = ["2.130.250.238", "170.95.95.252", "128.238.1.5"]
    ALT_CONTENT_VALUES = ["190.169.34.46", "216.228.24.25", "151.138.61.173"]

    def setUp(self):
        super().setUp()

        rr_set_data = dict(subname=self.SUBNAME, type=self.TYPE, ttl=self.TTL)
        self.empty_rr_set = RRset.objects.create(
            domain=self.empty_domain, **rr_set_data
        )
        self.simple_rr_set = RRset.objects.create(
            domain=self.simple_domain, **rr_set_data
        )
        self.full_rr_set = RRset.objects.create(domain=self.full_domain, **rr_set_data)

        RR.objects.create(rrset=self.simple_rr_set, content=self.CONTENT_VALUES[0])
        for content in self.CONTENT_VALUES:
            RR.objects.create(rrset=self.full_rr_set, content=content)

    def assertKnotEmptyRRSetUpdate(self):
        return self.assertKnotZoneUpdate(self.empty_domain.name, [self.empty_rr_set])

    def assertKnotSimpleRRSetUpdate(self):
        return self.assertKnotZoneUpdate(self.simple_domain.name, [self.simple_rr_set])

    def assertKnotFullRRSetUpdate(self):
        return self.assertKnotZoneUpdate(self.full_domain.name, [self.full_rr_set])

    def test_create_in_empty_rr_set(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            RR(content=self.CONTENT_VALUES[0], rrset=self.empty_rr_set).save()

    def test_create_in_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            RR(content=self.CONTENT_VALUES[1], rrset=self.simple_rr_set).save()

    def test_create_in_full_rr_set(self):
        for content in self.ALT_CONTENT_VALUES:
            with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
                RR(content=content, rrset=self.full_rr_set).save()

    def test_create_multiple_in_empty_rr_set(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            for content in self.ALT_CONTENT_VALUES:
                RR(content=content, rrset=self.empty_rr_set).save()

    def test_create_multiple_in_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            for content in self.ALT_CONTENT_VALUES:
                RR(content=content, rrset=self.simple_rr_set).save()

    def test_create_multiple_in_full_rr_set(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for content in self.ALT_CONTENT_VALUES:
                RR(content=content, rrset=self.full_rr_set).save()

    def test_update_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            rr = self.simple_rr_set.records.all()[0]
            rr.content = self.CONTENT_VALUES[1]
            rr.save()

    def test_update_full_rr_set_partially(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            rr = self.full_rr_set.records.all()[0]
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()

    def test_update_full_rr_set_completely(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for i, rr in enumerate(self.full_rr_set.records.all()):
                rr.content = self.ALT_CONTENT_VALUES[i]
                rr.save()

    def test_delete_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            self.simple_rr_set.records.all()[0].delete()

    def test_delete_full_rr_set_partially(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for rr in self.full_rr_set.records.all()[1:2]:
                rr.delete()

    def test_delete_full_rr_set_completely(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for rr in self.full_rr_set.records.all():
                rr.delete()

    def test_create_delete_empty_rr_set(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            new_rr = RR.objects.create(
                rrset=self.empty_rr_set, content=self.ALT_CONTENT_VALUES[0]
            )
            RR.objects.create(
                rrset=self.empty_rr_set, content=self.ALT_CONTENT_VALUES[1]
            )
            new_rr.delete()

    def test_create_delete_simple_rr_set_1(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            new_rr = RR.objects.create(
                rrset=self.simple_rr_set, content=self.ALT_CONTENT_VALUES[0]
            )
            RR.objects.create(
                rrset=self.simple_rr_set, content=self.ALT_CONTENT_VALUES[1]
            )
            new_rr.delete()

    def test_create_delete_simple_rr_set_2(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            self.simple_rr_set.records.all()[0].delete()
            RR.objects.create(
                rrset=self.simple_rr_set, content=self.ALT_CONTENT_VALUES[0]
            )

    def test_create_delete_simple_rr_set_3(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            self.simple_rr_set.records.all()[0].delete()
            for content in self.ALT_CONTENT_VALUES:
                RR.objects.create(rrset=self.simple_rr_set, content=content)

    def test_create_delete_full_rr_set_full_replacement(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for rr in self.full_rr_set.records.all():
                rr.delete()
            for content in self.CONTENT_VALUES:
                RR.objects.create(rrset=self.full_rr_set, content=content)

    def test_create_delete_full_rr_set_partial_replacement(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            self.full_rr_set.records.all()[1].delete()
            for content in self.ALT_CONTENT_VALUES[1:]:
                RR.objects.create(rrset=self.full_rr_set, content=content)

    def test_create_update_empty_rr_set_1(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            rr = RR.objects.create(
                rrset=self.empty_rr_set, content=self.CONTENT_VALUES[0]
            )
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()

    def test_create_update_empty_rr_set_2(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            for content, alt_content in zip(
                self.CONTENT_VALUES, self.ALT_CONTENT_VALUES
            ):
                rr = RR.objects.create(rrset=self.empty_rr_set, content=content)
                rr.content = alt_content
                rr.save()

    def test_create_update_empty_rr_set_3(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            rr = RR.objects.create(
                rrset=self.empty_rr_set, content=self.ALT_CONTENT_VALUES[0]
            )
            RR.objects.create(
                rrset=self.empty_rr_set, content=self.ALT_CONTENT_VALUES[1]
            )
            rr.content = self.CONTENT_VALUES[0]
            rr.save()

    def test_create_update_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            rr = self.simple_rr_set.records.all()[0]
            RR.objects.create(
                rrset=self.simple_rr_set, content=self.ALT_CONTENT_VALUES[0]
            )
            rr.content = self.ALT_CONTENT_VALUES[1]
            rr.save()

    def test_create_update_full_rr_set(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            for i, rr in enumerate(self.full_rr_set.records.all()):
                rr.content = self.ALT_CONTENT_VALUES[i]
                rr.save()
            RR.objects.create(rrset=self.full_rr_set, content=self.CONTENT_VALUES[0])

    def test_update_delete_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            rr = self.simple_rr_set.records.all()[0]
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()
            rr.delete()

    def test_update_delete_full_rr_set(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            rr = self.full_rr_set.records.all()[0]
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()
            rr.delete()
            self.full_rr_set.records.all()[1].delete()
            rr = self.full_rr_set.records.all()[0]
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()

    def test_create_update_delete_empty_rr_set_1(self):
        rr = RR.objects.create(rrset=self.empty_rr_set, content=self.CONTENT_VALUES[0])
        rr.content = self.ALT_CONTENT_VALUES[0]
        rr.save()
        rr.delete()

    def test_create_update_delete_empty_rr_set_2(self):
        with self.assertKnotEmptyRRSetUpdate(), KnotChangeTracker():
            RR.objects.create(rrset=self.empty_rr_set, content=self.CONTENT_VALUES[0])
            rr = RR.objects.create(
                rrset=self.empty_rr_set, content=self.CONTENT_VALUES[1]
            )
            rr.content = self.ALT_CONTENT_VALUES[1]
            rr.save()
            RR.objects.create(rrset=self.empty_rr_set, content=self.CONTENT_VALUES[2])
            rr.delete()

    def test_create_update_delete_simple_rr_set(self):
        with self.assertKnotSimpleRRSetUpdate(), KnotChangeTracker():
            self.simple_rr_set.records.all()[0].delete()
            RR.objects.create(rrset=self.simple_rr_set, content=self.CONTENT_VALUES[0])
            rr = RR.objects.create(
                rrset=self.simple_rr_set, content=self.CONTENT_VALUES[1]
            )
            rr.content = self.ALT_CONTENT_VALUES[1]
            rr.save()

    def test_create_update_delete_full_rr_set(self):
        with self.assertKnotFullRRSetUpdate(), KnotChangeTracker():
            self.full_rr_set.records.all()[1].delete()
            rr = self.full_rr_set.records.all()[1]
            rr.content = self.ALT_CONTENT_VALUES[0]
            rr.save()
            RR.objects.create(
                rrset=self.full_rr_set, content=self.ALT_CONTENT_VALUES[1]
            )


class AAAARRTestCase(RRTestCase):
    SUBNAME = "*.foobar"
    TYPE = "AAAA"
    TTL = 12
    CONTENT_VALUES = [
        "2001:fb24:45fd:d51:7937:b375:9cf3:5c62",
        "2001:ed06:5ebc:9d:87a:ce9f:1ceb:996",
        "2001:aa22:60e8:cec5:5650:9ff9:9a1b:b588",
        "2001:3ca:d710:52c2:9748:eec6:2e20:af0b",
        "2001:9c6e:8417:3c06:dd1c:44f1:a35f:ffad",
        "2001:f67a:5847:8dc0:edc3:56f3:a067:f80e",
        "2001:4e21:bda6:a509:e777:91c6:2dc1:394",
        "2001:9930:b062:c38f:99f6:ce12:bb04:f7c6",
        "2001:bb5e:921:b17f:7c9b:afb6:9933:cc79",
        "2001:a861:7139:e21e:11e4:8782:242b:e2a2",
        "2001:eaa:ff53:c819:93e:437c:ccc8:330c",
        "2001:6a88:fb92:5b43:984b:b729:393b:f173",
    ]
    ALT_CONTENT_VALUES = [
        "2001:2d03:6247:3494:b92e:d4a:2827:e2d",
        "2001:4b37:19d6:b66e:1aa1:db0f:98b5:d065",
        "2001:dbf1:e401:ace2:bc99:eb22:6e12:ec81",
        "2001:fa92:3564:7c3f:9995:2068:58bf:2a45",
        "2001:4c2c:c671:9f0c:600e:4eb6:672e:48c7",
        "2001:5d09:a6f7:594b:afa4:318a:6eda:3ec6",
        "2001:f33a:407c:f4e6:f886:dce2:6d08:d8ae",
        "2001:43c8:378d:7d37:92eb:fb0c:26b1:4998",
        "2001:7293:88c5:5405:fd1:7334:bb55:be20",
        "2001:c4b7:ae76:a9a2:ffb5:ba30:6874:a416",
        "2001:175f:7880:ef82:b65a:a472:14c9:a495",
        "2001:8c35:1566:4f53:c26a:c54:2c9f:1463",
    ]


class TXTRRTestCase(RRTestCase):
    SUBNAME = "_acme_challenge"
    TYPE = "TXT"
    TTL = 876
    CONTENT_VALUES = [
        '"The quick brown fox jumps over the lazy dog"',
        '"main( ) {printf(\\"hello, world\\010\\");}"',
        '"“红色联合”对“四·二八兵团”总部大楼的攻击已持续了两天"',
    ]
    ALT_CONTENT_VALUES = [
        '"🧥 👚 👕 👖 👔 👗 👙 👘 👠 👡 👢 👞 👟 🥾 🥿 🧦 🧤 🧣 🎩 🧢 👒 🎓 ⛑ 👑 👝 👛 👜 💼 🎒 👓 🕶 🥽 🥼 🌂 🧵"',
        '"v=spf1 ip4:192.0.2.0/24 ip4:198.51.100.123 a -all"',
        '"https://en.wikipedia.org/wiki/Domain_Name_System"',
    ]


class RRSetTestCase(KnotChangeTrackerTestCase):
    TEST_DATA = {
        ("A", "_asdf", 123): ["1.2.3.4", "5.5.5.5"],
        ("TXT", "test", 455): ['"ASDF"', '"foobar"', '"92847"'],
        ("A", "foo", 1010): ["1.2.3.4", "5.5.4.5"],
        ("AAAA", "*", 100023): ["::1", "::2", "::3", "::4"],
    }

    ADDITIONAL_TEST_DATA = {
        ("A", "zekdi", 99): [
            "134.48.204.28",
            "151.85.162.150",
            "5.174.133.123",
            "96.37.218.195",
            "106.18.66.163",
            "51.75.149.213",
            "9.105.0.185",
            "32.198.60.88",
            "93.141.131.151",
            "6.133.10.124",
        ],
        ("A", "knebq", 82): ["218.154.60.184"],
    }

    @classmethod
    def _create_rr_sets(cls, data, domain):
        rr_sets = []
        rrs = {}
        for (type_, subname, ttl), rr_contents in data.items():
            rr_set = RRset(domain=domain, subname=subname, type=type_, ttl=ttl)
            rr_sets.append(rr_set)
            rrs[(type_, subname)] = this_rrs = []
            rr_set.save()
            for content in rr_contents:
                rr = RR(content=content, rrset=rr_set)
                this_rrs.append(rr)
                rr.save()
        return rr_sets, rrs

    def setUp(self):
        super().setUp()
        self.rr_sets, self.rrs = self._create_rr_sets(self.TEST_DATA, self.full_domain)

    def test_empty_domain_create_single_empty(self):
        with KnotChangeTracker():
            RRset.objects.create(domain=self.empty_domain, subname="", ttl=60, type="A")

    def test_empty_domain_create_single_meaty(self):
        with (
            self.assertKnotZoneUpdate(
                self.empty_domain.name, self.empty_domain.rrset_set
            ),
            KnotChangeTracker(),
        ):
            self._create_rr_sets(self.ADDITIONAL_TEST_DATA, self.empty_domain)

    def test_full_domain_create_single_empty(self):
        with KnotChangeTracker():
            RRset.objects.create(domain=self.full_domain, subname="", ttl=60, type="A")

    def test_empty_domain_create_many_empty(self):
        with KnotChangeTracker():
            empty_test_data = {key: [] for key, value in self.TEST_DATA.items()}
            self._create_rr_sets(empty_test_data, self.empty_domain)

    def test_empty_domain_create_many_meaty(self):
        with (
            self.assertKnotZoneUpdate(
                self.empty_domain.name, self.empty_domain.rrset_set
            ),
            KnotChangeTracker(),
        ):
            self._create_rr_sets(self.TEST_DATA, self.empty_domain)

    def test_empty_domain_delete(self):
        with KnotChangeTracker():
            self._create_rr_sets(self.TEST_DATA, self.empty_domain)
            for rr_set in self.empty_domain.rrset_set.all():
                rr_set.delete()

    def test_full_domain_delete_single(self):
        index = (self.rr_sets[0].type, self.rr_sets[0].subname, self.rr_sets[0].ttl)
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, {index: []}),
            KnotChangeTracker(),
        ):
            self.rr_sets[0].delete()

    def test_full_domain_delete_multiple(self):
        data = self.TEST_DATA
        empty_data = {key: [] for key, value in data.items()}
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, empty_data),
            KnotChangeTracker(),
        ):
            for type_, subname, _ in data.keys():
                self.full_domain.rrset_set.get(subname=subname, type=type_).delete()

    def test_update_ttl(self):
        new_ttl = 765
        data = {
            (type_, subname, new_ttl): records
            for (type_, subname, _), records in self.TEST_DATA.items()
        }
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, data),
            KnotChangeTracker(),
        ):
            for rr_set in self.full_domain.rrset_set.all():
                rr_set.ttl = new_ttl
                rr_set.save()

    def test_full_domain_create_delete(self):
        data = self.TEST_DATA
        empty_data = {key: [] for key in data.keys()}
        expected_data = dict(self.ADDITIONAL_TEST_DATA)
        expected_data.update(empty_data)
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, expected_data),
            KnotChangeTracker(),
        ):
            self._create_rr_sets(self.ADDITIONAL_TEST_DATA, self.full_domain)
            for type_, subname, _ in data.keys():
                self.full_domain.rrset_set.get(subname=subname, type=type_).delete()


class CommonRRSetTestCase(RRSetTestCase):
    def test_mixed_operations(self):
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, self.ADDITIONAL_TEST_DATA),
            KnotChangeTracker(),
        ):
            self._create_rr_sets(self.ADDITIONAL_TEST_DATA, self.full_domain)

        rr_sets = [
            RRset.objects.get(type=type_, subname=subname)
            for (type_, subname, _) in self.ADDITIONAL_TEST_DATA.keys()
        ]
        with (
            self.assertKnotZoneUpdate(self.full_domain.name, rr_sets),
            KnotChangeTracker(),
        ):
            for rr_set in rr_sets:
                rr_set.ttl = 1
                rr_set.save()

        data = {}
        for key in [("A", "_asdf", 123), ("AAAA", "*", 100023), ("A", "foo", 1010)]:
            data[key] = self.TEST_DATA[key].copy()

        with (
            self.assertKnotZoneUpdate(self.full_domain.name, data),
            KnotChangeTracker(),
        ):
            data[("A", "_asdf", 123)].append("9.9.9.9")
            rr_set = RRset.objects.get(
                domain=self.full_domain, type="A", subname="_asdf"
            )
            RR(content="9.9.9.9", rrset=rr_set).save()

            data[("AAAA", "*", 100023)].append("::9")
            rr_set = RRset.objects.get(
                domain=self.full_domain, type="AAAA", subname="*"
            )
            RR(content="::9", rrset=rr_set).save()

            data[("A", "foo", 1010)] = []
            RRset.objects.get(domain=self.full_domain, type="A", subname="foo").delete()


class UncommonRRSetTestCase(RRSetTestCase):
    TEST_DATA = {
        ("SPF", "baz", 444): [
            '"v=spf1 ip4:192.0.2.0/24 ip4:198.51.100.123 a -all"',
            '"v=spf1 a mx ip4:192.0.2.0 -all"',
        ],
        (
            "OPENPGPKEY",
            "00d8d3f11739d2f3537099982b4674c29fc59a8fda350fca1379613a._openpgpkey",
            78000,
        ): [
            "mQENBFnVAMgBCADWXo3I9Vig02zCR8WzGVN4FUrexZh9OdVSjOeSSmXPH6V5"
            "+sWRfgSvtUp77IWQtZU810EI4GgcEzg30SEdLBSYZAt/lRWSpcQWnql4LvPg"
            "oMqU+/+WUxFdnbIDGCMEwWzF2NtQwl4r/ot/q5SHoaA4AGtDarjA1pbTBxza"
            "/xh6VRQLl5vhWRXKslh/Tm4NEBD16Z9gZ1CQ7YlAU5Mg5Io4ghOnxWZCGJHV"
            "5BVQTrzzozyILny3e48dIwXJKgcFt/DhE+L9JTrO4cYtkG49k7a5biMiYhKh"
            "LK3nvi5diyPyHYQfUaD5jO5Rfcgwk7L4LFinVmNllqL1mgoxadpgPE8xABEB"
            "AAG0MUpvaGFubmVzIFdlYmVyIChPTkxZLVRFU1QpIDxqb2hhbm5lc0B3ZWJl"
            "cmRucy5kZT6JATgEEwECACIFAlnVAMgCGwMGCwkIBwMCBhUIAgkKCwQWAgMB"
            "Ah4BAheAAAoJEOvytPeP0jpogccH/1IQNza/JPiQRFLWwzz1mxOSgRgubkOw"
            "+XgXAtvIGHQOF6/ZadQ8rNrMb3D+dS4bTkwpFemY59Bm3n12Ve2Wv2AdN8nK"
            "1KLClA9cP8380CT53+zygV+mGfoRBLRO0i4QmW3mI6yg7T2E+U20j/i9IT1K"
            "ATg4oIIgLn2bSpxRtuSp6aJ2q91Y/lne7Af7KbKq/MirEDeSPrjMYxK9D74E"
            "ABLs4Ab4Rebg3sUga037yTOCYDpRv2xkyARoXMWYlRqME/in7aBtfo/fduJG"
            "qu2RlND4inQmV75V+s4/x9u+7UlyFIMbWX2rtdWHsO/t4sCP1hhTZxz7kvK7"
            "1ZqLj9hVjdW5AQ0EWdUAyAEIAKxTR0AcpiDm4r4Zt/qGD9P9jasNR0qkoHjr"
            "9tmkaW34Lx7wNTDbSYQwn+WFzoT1rxbpge+IpjMn5KabHc0vh13vO1zdxvc0"
            "LSydhjMI1Gfey+rsQxhT4p5TbvKpsWiNykSNryl1LRgRvcWMnxvYfxdyqIF2"
            "3+3pgMipXlfJHX4SoAuPn4Bra84y0ziljrptWf4U78+QonX9dwwZ/SCrSPfQ"
            "rGwpQcHSbbxZvxmgxeweHuAEhUGVuwkFsNBSk4NSi+7Y1p0/oD7tEM17WjnO"
            "NuoGCFh1anTS7+LE0f3Mp0A74GeJvnkgdnPHJwcZpBf5Jf1/6Nw/tJpYiP9v"
            "Fu1nF9EAEQEAAYkBHwQYAQIACQUCWdUAyAIbDAAKCRDr8rT3j9I6aDZrB/9j"
            "2sgCohhDBr/Yzxlg3OmRwnvJlHjs//57XV99ssWAg142HxMQt87s/AXpIuKH"
            "tupEAClN/knrmKubO3JUkoi3zCDkFkSgrH2Mos75KQbspUtmzwVeGiYSNqyG"
            "pEzh5UWYuigYx1/a5pf3EhXCVVybIJwxDEo6sKZwYe6CRe5fQpY6eqZNKjkl"
            "4xDogTMpsrty3snjZHOsQYlTlFWFsm1KA43Mnaj7Pfn35+8bBeNSgiS8R+EL"
            "f66Ymcl9YHWHHTXjs+DvsrimYbs1GXOyuu3tHfKlZH19ZevXbycpp4UFWsOk"
            "Sxsb3CZRnPxuz+NjZrOk3UNI6RxlaeuAQOBEow50"
        ],
        ("PTR", "foo", 1010): ["1.example.com.", "2.example.com."],
        ("SRV", "*", 100023): [
            "10 60 5060 1.example.com.",
            "20 60 5060 2.example.com.",
            "30 60 5060 3.example.com.",
        ],
        ("TLSA", "_443._tcp.www", 89): [
            "3 0 1 221C1A9866C32A45E44F55F611303242082A01C1B5C3027C8C7AD1324DE0AC38"
        ],
    }


class DomainTestCase(KnotChangeTrackerTestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_domain = None
        self.simple_domain = None
        self.empty_domain = None
        self.domains = []

    def setUp(self):
        super().setUp()
        self.empty_domain = Domain.objects.create(
            name=self.random_domain_name(),
            owner=self.user,
            nslord=Domain.NSLord.KNOT,
        )
        self.simple_domain = Domain.objects.create(
            name=self.random_domain_name(),
            owner=self.user,
            nslord=Domain.NSLord.KNOT,
        )
        self.full_domain = Domain.objects.create(
            name=self.random_domain_name(),
            owner=self.user,
            nslord=Domain.NSLord.KNOT,
        )
        self.domains = [self.empty_domain, self.simple_domain, self.full_domain]

        simple_rr_set = RRset.objects.create(
            domain=self.simple_domain, type="AAAA", subname="", ttl=42
        )
        RR.objects.create(content="::1", rrset=simple_rr_set)
        RR.objects.create(content="::2", rrset=simple_rr_set)

        rr_set_1 = RRset.objects.create(
            domain=self.full_domain, type="A", subname="*", ttl=1337
        )
        for content in [self.random_ip(4) for _ in range(10)]:
            RR.objects.create(content=content, rrset=rr_set_1)
        rr_set_2 = RRset.objects.create(
            domain=self.full_domain, type="AAAA", subname="", ttl=60
        )
        for content in [self.random_ip(6) for _ in range(15)]:
            RR.objects.create(content=content, rrset=rr_set_2)

    def test_create(self):
        name = self.random_domain_name()
        with (
            self.assertKnotUpdates(
                [
                    (settings.CATALOG_ZONE, None),
                    (
                        name,
                        {
                            ("NS", "", settings.DEFAULT_NS_TTL): settings.DEFAULT_NS,
                            ("SOA", "", settings.DEFAULT_NS_TTL): [
                                "get.desec.io. get.desec.io. 1 86400 3600 2419200 3600"
                            ],
                        },
                    ),
                ]
            ),
            self.assertRequests(self.requests_desec_domain_creation_knot(name=name)),
            KnotChangeTracker(),
        ):
            Domain.objects.create(name=name, owner=self.user, nslord=Domain.NSLord.KNOT)

    def test_update_domain(self):
        for domain in self.domains:
            with KnotChangeTracker():
                domain.owner = self.admin
                domain.published = timezone.now()
                domain.save()

    def test_update_empty_domain_name(self):
        new_name = self.random_domain_name()
        with KnotChangeTracker():  # no exception, no requests
            self.empty_domain.name = new_name
            self.empty_domain.save()

    def test_delete_single(self):
        for domain in self.domains:
            with (
                self.assertKnotUpdates([(settings.CATALOG_ZONE, None)]),
                self.assertRequests(self.requests_desec_domain_deletion_knot(domain)),
                KnotChangeTracker(),
            ):
                domain.delete()

    def test_delete_multiple(self):
        with (
            self.assertKnotUpdates(
                [(settings.CATALOG_ZONE, None) for _ in self.domains],
                expect_order=False,
            ),
            self.assertRequests(
                [
                    self.requests_desec_domain_deletion_knot(domain)
                    for domain in reversed(self.domains)
                ],
                expect_order=False,
            ),
            KnotChangeTracker(),
        ):
            for domain in self.domains:
                domain.delete()

    def test_create_delete(self):
        with KnotChangeTracker():
            d = Domain.objects.create(
                name=self.random_domain_name(),
                owner=self.user,
                nslord=Domain.NSLord.KNOT,
            )
            d.delete()

    def test_delete_create_empty_domain(self):
        with KnotChangeTracker():
            name = self.empty_domain.name
            self.empty_domain.delete()
            self.empty_domain = Domain.objects.create(
                name=name, owner=self.user, nslord=Domain.NSLord.KNOT
            )

    def test_delete_create_full_domain(self):
        name = self.full_domain.name
        expected_deletes = {
            (rr_set.type, rr_set.subname, rr_set.ttl): []
            for rr_set in self.full_domain.rrset_set.all()
        }
        with self.assertKnotZoneUpdate(name, expected_deletes), KnotChangeTracker():
            self.full_domain.delete()
            self.full_domain = Domain.objects.create(
                name=name, owner=self.user, nslord=Domain.NSLord.KNOT
            )
