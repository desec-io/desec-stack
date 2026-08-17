from django.conf import settings
from django.core import management
from django.core.management import CommandError
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

    def test_update_domains_auto(self):
        """Hands an account whose limit support has pinned back to the rule."""
        management.call_command("limit", "domains", self.owner.email, "123")
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.limit_domains, 123)

        for spelling in ["auto", "AUTO"]:
            management.call_command("limit", "domains", self.owner.email, spelling)
            self.owner.refresh_from_db()
            self.assertIsNone(self.owner.limit_domains)
            # No secure domains yet, so the computed limit is at its floor.
            self.assertEqual(
                self.owner.effective_limit_domains,
                settings.DOMAIN_LIMIT_INSECURE_HEADROOM,
            )
            # ... and pinning it again still works.
            management.call_command("limit", "domains", self.owner.email, "123")

    def test_update_minimum_ttl(self):
        management.call_command("limit", "ttl", self.my_domain.name, "123")
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 123)
        management.call_command("limit", "ttl", self.my_domain.name, 567)
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 567)
        management.call_command(
            "limit", "ttl", self.my_domain.name, "10000"
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

    def test_update_minimum_ttl_auto(self):
        management.call_command("limit", "ttl", self.my_domain.name, "auto")
        self.my_domain.refresh_from_db()
        self.assertIsNone(self.my_domain.minimum_ttl)
        self.assertEqual(
            self.my_domain.effective_minimum_ttl, settings.MINIMUM_TTL_DEFAULT
        )

        management.call_command("limit", "ttl", self.my_domain.name, "123")
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 123)

    def test_update_minimum_ttl_invalid(self):
        management.call_command("limit", "ttl", self.my_domain.name, "123")
        with self.assertRaises(CommandError):
            management.call_command("limit", "ttl", self.my_domain.name, "not a number")
        self.my_domain.refresh_from_db()
        self.assertEqual(self.my_domain.minimum_ttl, 123)
