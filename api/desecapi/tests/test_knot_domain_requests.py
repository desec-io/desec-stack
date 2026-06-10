import dns.rdatatype

from desecapi.models import Domain
from desecapi.tests.base import KnotDesecTestCase


class KnotDomainQueryTestCase(KnotDesecTestCase):
    def setUp(self):
        super().setUp()
        self.domain = Domain.objects.create(
            owner=self.user,
            name=self.random_domain_name(),
            nslord=Domain.NSLord.KNOT,
        )

    def test_keys_uses_dnskey_query(self):
        _ = self.domain.keys
        self.assertEqual(len(self._knot_queries), 1)
        query = self._knot_queries[0]
        self.assertEqual(query.question[0].rdtype, dns.rdatatype.DNSKEY)

    def test_zonefile_uses_axfr(self):
        _ = self.domain.zonefile
        self.assertEqual(len(self._knot_xfr_calls), 1)
        _, zone = self._knot_xfr_calls[0]
        self.assertEqual(zone.rstrip("."), self.domain.name.rstrip("."))
