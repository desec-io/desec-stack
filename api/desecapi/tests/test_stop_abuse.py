from django.core import management

from api import settings
from desecapi import models
from desecapi.tests.base import DomainOwnerTestCase


class StopAbuseCommandTest(DomainOwnerTestCase):

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()
        cls.create_rr_set(cls.my_domains[1], ['127.0.0.1', '127.0.1.1'], type='A', ttl=123)
        cls.create_rr_set(cls.other_domains[1], ['40.1.1.1', '40.2.2.2'], type='A', ttl=456)
        for d in cls.my_domains + cls.other_domains:
            cls.create_rr_set(d, ['ns1.example.', 'ns2.example.'], type='NS', ttl=456)
            cls.create_rr_set(d, ['ns1.example.', 'ns2.example.'], type='NS', ttl=456, subname='subname')
            cls.create_rr_set(d, ['"foo"'], type='TXT', ttl=456)

    def test_noop(self):
        # test implicit by absence assertPdnsRequests
        management.call_command('stop-abuse')

    def test_remove_rrsets_by_domain_name(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_domain.name)):
            management.call_command('stop-abuse', self.my_domain)
        self.assertEqual(models.RRset.objects.filter(domain__name=self.my_domain.name).count(), 1)  # only NS left
        self.assertEqual(
            set(models.RR.objects.filter(rrset__domain__name=self.my_domain.name).values_list('content', flat=True)),
            set(settings.DEFAULT_NS),
        )

    def test_remove_rrsets_by_email(self):
        with self.assertPdnsRequests(
            *[self.requests_desec_rr_sets_update(name=d.name) for d in self.my_domains],
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.owner.email)
        self.assertEqual(models.RRset.objects.filter(domain__name=self.my_domain.name).count(), 1)  # only NS left
        self.assertEqual(
            set(models.RR.objects.filter(rrset__domain__name=self.my_domain.name).values_list('content', flat=True)),
            set(settings.DEFAULT_NS),
        )

    def test_disable_user_by_domain_name(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_domain.name)):
            management.call_command('stop-abuse', self.my_domain)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.is_active, False)

    def test_disable_user_by_email(self):
        with self.assertPdnsRequests(
            *[self.requests_desec_rr_sets_update(name=d.name) for d in self.my_domains],
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.owner.email)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.is_active, False)

    def test_keep_other_owned_domains_name(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_domain.name)):
            management.call_command('stop-abuse', self.my_domain)
        self.assertGreater(models.RRset.objects.filter(domain__name=self.my_domains[1].name).count(), 1)

    def test_dont_keep_other_owned_domains_email(self):
        with self.assertPdnsRequests(
            *[self.requests_desec_rr_sets_update(name=d.name) for d in self.my_domains],
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.owner.email)
        self.assertEqual(models.RRset.objects.filter(domain__name=self.my_domains[1].name).count(), 1)

    def test_only_disable_owner(self):
        with self.assertPdnsRequests(
            self.requests_desec_rr_sets_update(name=self.my_domains[0].name),
            self.requests_desec_rr_sets_update(name=self.my_domains[1].name),
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.my_domain, self.owner.email)
        self.my_domain.owner.refresh_from_db()
        self.other_domain.owner.refresh_from_db()
        self.assertEqual(self.my_domain.owner.is_active, False)
        self.assertEqual(self.other_domain.owner.is_active, True)

    def test_disable_owners_by_domain_name(self):
        with self.assertPdnsRequests(
            self.requests_desec_rr_sets_update(name=self.my_domain.name),
            self.requests_desec_rr_sets_update(name=self.other_domain.name),
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.my_domain, self.other_domain)
        self.my_domain.owner.refresh_from_db()
        self.other_domain.owner.refresh_from_db()
        self.assertEqual(self.my_domain.owner.is_active, False)
        self.assertEqual(self.other_domain.owner.is_active, False)

    def test_disable_owners_by_email(self):
        with self.assertPdnsRequests(
            *[self.requests_desec_rr_sets_update(name=d.name) for d in self.my_domains + self.other_domains],
            expect_order=False,
        ):
            management.call_command('stop-abuse', self.owner.email, *[d.owner.email for d in self.other_domains])
        self.my_domain.owner.refresh_from_db()
        self.other_domain.owner.refresh_from_db()
        self.assertEqual(self.my_domain.owner.is_active, False)
        self.assertEqual(self.other_domain.owner.is_active, False)

