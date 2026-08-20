from django.conf import settings
from django.core import management
from django.db.models import Min

from desecapi.models import Domain, RRset
from desecapi.tests.base import DomainOwnerTestCase


class LimitCommandTest(DomainOwnerTestCase):
    def test_update_domains(self):
        management.call_command("limit", "domains", self.owner.email, "123")
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.limit_domains, 123)
        management.call_command("limit", "domains", self.owner.email, 567)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.limit_domains, 567)
        management.call_command(
            "limit", "domains", self.owner.email, "1"
        )  # below the actual number of domains
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.limit_domains, 1)
        # did not delete domains below limit:
        self.assertEqual(Domain.objects.filter(owner_id=self.owner.id).count(), 2)

    def test_update_minimum_ttl(self):
        management.call_command("limit", "minimum_ttl", self.my_domain.name, "123")
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 123)
        management.call_command("limit", "minimum_ttl", self.my_domain.name, 567)
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 567)
        management.call_command("limit", "default_ttl", self.my_domain.name, "10000")
        management.call_command(
            "limit", "minimum_ttl", self.my_domain.name, "10000"
        )  # above the currently used ttl
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 10000)
        # did not change existing TTLs in violation of minimum TTL:
        self.assertLess(
            RRset.objects.filter(domain_id=self.my_domain.id).aggregate(Min("ttl"))[
                "ttl__min"
            ],
            10000,
        )

    def test_update_default_ttl(self):
        management.call_command("limit", "default_ttl", self.my_domain.name, "1234")
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.default_ttl, 1234)
        # did not touch the minimum TTL:
        self.assertEqual(self.my_domain.minimum_ttl, settings.MINIMUM_TTL_DEFAULT)

    def test_update_ttl_bounds(self):
        for kind, value in [
            ("default_ttl", self.my_domain.minimum_ttl - 1),
            ("default_ttl", settings.MAXIMUM_TTL + 1),
            ("minimum_ttl", self.my_domain.default_ttl + 1),
        ]:
            with self.subTest(kind=kind, value=value):
                with self.assertRaises(management.CommandError):
                    management.call_command(
                        "limit", kind, self.my_domain.name, str(value)
                    )
                self.my_domain.refresh_from_db()
                self.assertEqual(
                    self.my_domain.minimum_ttl, settings.MINIMUM_TTL_DEFAULT
                )
                self.assertEqual(self.my_domain.default_ttl, settings.DEFAULT_TTL)

    def test_update_unknown_kind(self):
        with self.assertRaises(management.CommandError):
            management.call_command("limit", "ttl", self.my_domain.name, "123")
