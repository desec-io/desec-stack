from django.conf import settings
from django.core import management
from django.core.management import CommandError

from desecapi.models import Domain
from desecapi.tests.base import DomainOwnerTestCase


class FixAutoDelegationsCommandTest(DomainOwnerTestCase):
    FOREIGN_NS = "ns1.example.org."
    FOREIGN_DS = f"12345 13 2 {'ab' * 32}"

    @property
    def ds(self):
        return set(self.get_body_pdns_zone_retrieve_crypto_keys()[0]["cds"])

    def test_noop(self):
        # test implicit by absence of expected requests
        management.call_command("fix-auto-delegations", "--apply")

    def test_unknown_name(self):
        with self.assertRaises(CommandError):
            management.call_command("fix-auto-delegations", "unknown.example")

    def test_missing_delegation(self):
        name = f"sub.{self.my_domain.name}"
        self.create_domain(owner=self.owner, name=name)

        # Without --apply, nothing changes
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=name)
        ):
            management.call_command("fix-auto-delegations")
        self.assertFalse(self.my_domain.rrset_set.filter(subname="sub").exists())

        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=name),
            *self.requests_desec_rr_sets_update(name=self.my_domain.name),
        ):
            management.call_command("fix-auto-delegations", "--apply")
        self.assertRRsetDB(
            self.my_domain,
            subname="sub",
            type_="NS",
            rr_contents=set(settings.DEFAULT_NS),
        )
        self.assertRRsetDB(
            self.my_domain, subname="sub", type_="DS", rr_contents=self.ds
        )

        # Running again is a no-op
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=name)
        ):
            management.call_command("fix-auto-delegations", "--apply")

    def test_stale_delegation(self):
        self.create_rr_set(
            self.my_domain,
            settings.DEFAULT_NS,
            subname="gone",
            type="NS",
            ttl=3600,
        )
        self.create_rr_set(
            self.my_domain, [self.FOREIGN_DS], subname="gone", type="DS", ttl=300
        )

        with self.assertRequests(
            *self.requests_desec_rr_sets_update(name=self.my_domain.name)
        ):
            management.call_command("fix-auto-delegations", "--apply")
        self.assertFalse(self.my_domain.rrset_set.filter(subname="gone").exists())

    def test_stale_delegation_keeps_foreign_records(self):
        self.create_rr_set(
            self.my_domain,
            [*settings.DEFAULT_NS, self.FOREIGN_NS],
            subname="gone",
            type="NS",
            ttl=3600,
        )
        self.create_rr_set(
            self.my_domain, [self.FOREIGN_DS], subname="gone", type="DS", ttl=300
        )

        with self.assertRequests(
            *self.requests_desec_rr_sets_update(name=self.my_domain.name)
        ):
            management.call_command("fix-auto-delegations", "--apply")
        self.assertRRsetDB(
            self.my_domain, subname="gone", type_="NS", rr_contents={self.FOREIGN_NS}
        )
        self.assertRRsetDB(
            self.my_domain, subname="gone", type_="DS", rr_contents={self.FOREIGN_DS}
        )

    def test_names_limit_the_scope(self):
        in_scope = f"sub.{self.my_domain.name}"
        out_of_scope = f"sub.{self.my_domains[1].name}"
        for name in [in_scope, out_of_scope]:
            self.create_domain(owner=self.owner, name=name)

        # The given name is considered as a delegating domain ...
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=in_scope),
            *self.requests_desec_rr_sets_update(name=self.my_domain.name),
        ):
            management.call_command(
                "fix-auto-delegations", "--apply", self.my_domain.name
            )
        self.assertTrue(self.my_domain.rrset_set.filter(subname="sub").exists())
        self.assertFalse(self.my_domains[1].rrset_set.filter(subname="sub").exists())

        # ... and as a delegated one
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=out_of_scope),
            *self.requests_desec_rr_sets_update(name=self.my_domains[1].name),
        ):
            management.call_command("fix-auto-delegations", "--apply", out_of_scope)
        self.assertTrue(self.my_domains[1].rrset_set.filter(subname="sub").exists())

    def test_occluded_delegation(self):
        name = f"x.sub.{self.my_domain.name}"
        domain = Domain.objects.create(owner=self.owner, name=name)
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=name),
            *self.requests_desec_rr_sets_update(name=self.my_domain.name),
        ):
            management.call_command("fix-auto-delegations", "--apply")
        self.assertTrue(self.my_domain.rrset_set.filter(subname="x.sub").exists())

        # Once a domain in between exists, the delegation moves there
        middle = Domain.objects.create(
            owner=self.owner, name=f"sub.{self.my_domain.name}"
        )
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=middle.name),
            self.request_pdns_zone_retrieve_crypto_keys(name=domain.name),
            self.request_pdns_zone_retrieve_crypto_keys(name=domain.name),
            # one update for adding the delegation of the domain in between, one for
            # removing the delegation it takes over
            *self.requests_desec_rr_sets_update(name=self.my_domain.name),
            *self.requests_desec_rr_sets_update(name=self.my_domain.name),
            *self.requests_desec_rr_sets_update(name=middle.name),
            expect_order=False,
        ):
            management.call_command("fix-auto-delegations", "--apply")
        self.assertTrue(middle.rrset_set.filter(subname="x").exists())
        self.assertTrue(self.my_domain.rrset_set.filter(subname="sub").exists())
        self.assertFalse(self.my_domain.rrset_set.filter(subname="x.sub").exists())
