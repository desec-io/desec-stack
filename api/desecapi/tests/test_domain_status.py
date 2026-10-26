from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import serializers, status

from desecapi import tasks
from desecapi.models import DelegationCheck, Domain, User
from desecapi.models.domains import under_local_public_suffix_q
from desecapi.serializers import DomainStatusSerializer
from desecapi.tests.base import DomainOwnerTestCase
from desecapi.tests.test_delegation import result, secure
from desecapi.throttling import AccountScopedRatesThrottle, ScopedRatesThrottle
from desecapi.views import DomainViewSet

SecurityStatus = DelegationCheck.SecurityStatus
NameserverStatus = DelegationCheck.NameserverStatus


class DomainStatusSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )

    def setUp(self):
        super().setUp()
        self.domain = Domain.objects.create(name="example.com", owner=self.user)

    def record(self, **kwargs):
        return DelegationCheck.objects.record(self.domain, result(**kwargs))

    def status(self):
        self.domain.refresh_from_db()
        return DomainStatusSerializer(self.domain).data

    def test_never_checked(self):
        self.assertEqual(
            self.status(),
            {
                "secure_since": None,
                "checked": None,
                "nameserver_status": None,
                "security_status": None,
                "nameservers": [],
            },
        )

    def test_secure(self):
        check = self.record()
        data = self.status()
        self.assertEqual(data["nameserver_status"], "correctly_delegated")
        self.assertEqual(data["security_status"], "secure")
        self.assertEqual(data["nameservers"], ["ns1.example.net."])
        check.refresh_from_db()
        self.assertEqual(data["secure_since"], self.timestamp(check.created))
        self.assertEqual(data["checked"], self.timestamp(check.checked))

    @staticmethod
    def timestamp(value):
        return serializers.DateTimeField().to_representation(value)

    def test_failed_check_keeps_secure_since(self):
        """
        secure_since is error-immune (limits §3.1), so the field still says
        "secure" while the statuses honestly report today's failure.
        """
        self.record()
        before = self.status()["secure_since"]
        self.record(
            security_status=SecurityStatus.ERROR,
            nameserver_status=NameserverStatus.ERROR,
            nameservers=[],
        )
        data = self.status()
        self.assertEqual(data["secure_since"], before)
        self.assertIsNotNone(data["secure_since"])
        self.assertEqual(data["nameserver_status"], "error")
        self.assertEqual(data["security_status"], "error")

    def test_conclusive_outcomes_that_are_not_secure(self):
        cases = [
            (SecurityStatus.INSECURE, NameserverStatus.CORRECTLY_DELEGATED),
            (SecurityStatus.MISCONFIGURED, NameserverStatus.CORRECTLY_DELEGATED),
            (SecurityStatus.SECURE, NameserverStatus.OTHER_PROVIDER),
            (SecurityStatus.INSECURE, NameserverStatus.MULTI_PROVIDER),
        ]
        for security_status, nameserver_status in cases:
            with self.subTest(
                security_status=security_status, nameserver_status=nameserver_status
            ):
                self.record()  # secure first, so that clearing is observable
                self.record(
                    security_status=security_status,
                    nameserver_status=nameserver_status,
                    nameservers=["ns1.example.net.", "ns.other.example."],
                )
                data = self.status()
                self.assertIsNone(data["secure_since"])
                self.assertEqual(data["security_status"], security_status.name.lower())
                self.assertEqual(
                    data["nameserver_status"], nameserver_status.name.lower()
                )

    def test_not_delegated_reports_no_security_status(self):
        """
        Without a delegation, the check asks whether the parent is signed, so
        the stored value would describe the parent rather than this domain.
        """
        for security_status in SecurityStatus:
            with self.subTest(security_status=security_status):
                self.record(
                    security_status=security_status,
                    nameserver_status=NameserverStatus.NOT_DELEGATED,
                    nameservers=[],
                )
                data = self.status()
                self.assertEqual(data["nameserver_status"], "not_delegated")
                self.assertIsNone(data["security_status"])
                self.assertIsNone(data["secure_since"])

    def test_every_value_is_a_lowercase_name(self):
        for nameserver_status in NameserverStatus:
            for security_status in SecurityStatus:
                with self.subTest(
                    nameserver_status=nameserver_status,
                    security_status=security_status,
                ):
                    self.record(
                        security_status=security_status,
                        nameserver_status=nameserver_status,
                    )
                    data = self.status()
                    self.assertEqual(
                        data["nameserver_status"], nameserver_status.name.lower()
                    )
                    if nameserver_status != NameserverStatus.NOT_DELEGATED:
                        self.assertEqual(
                            data["security_status"], security_status.name.lower()
                        )


class UnderLocalPublicSuffixTestCase(TestCase):
    def test_property_agrees_with_query(self):
        user = User.objects.create_user(email="test@example.com", password="secret")
        suffix = next(iter(settings.LOCAL_PUBLIC_SUFFIXES))
        expected = {
            f"mine.{suffix}": True,
            f"sub.mine.{suffix}": True,
            suffix: False,
            f"not{suffix}": False,
            f"{suffix}.example.com": False,
            "example.com": False,
        }
        for name in expected:
            Domain.objects.create(name=name, owner=user)

        matched = set(
            Domain.objects.filter(under_local_public_suffix_q()).values_list(
                "name", flat=True
            )
        )
        for name, under in expected.items():
            with self.subTest(name=name):
                domain = Domain.objects.get(name=name)
                self.assertEqual(domain.is_under_local_public_suffix, under)
                self.assertEqual(name in matched, under)


class DomainStatusFieldTestCase(DomainOwnerTestCase):
    NUM_OWNED_DOMAINS = 5

    def test_list_includes_status(self):
        secure(self.my_domains[0])
        response = self.client.get(self.reverse("v1:domain-list"))
        self.assertStatus(response, status.HTTP_200_OK)
        statuses = {d["name"]: d["status"] for d in response.data}
        self.assertEqual(statuses[self.my_domains[0].name]["security_status"], "secure")
        self.assertIsNotNone(statuses[self.my_domains[0].name]["secure_since"])
        for domain in self.my_domains[1:]:
            self.assertIsNone(statuses[domain.name]["checked"])

    def test_list_does_not_query_checks_per_domain(self):
        for domain in self.my_domains:
            secure(domain)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.reverse("v1:domain-list"))
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.NUM_OWNED_DOMAINS)
        separate = [
            q["sql"]
            for q in queries.captured_queries
            if 'FROM "desecapi_delegationcheck"' in q["sql"]
        ]
        self.assertEqual(separate, [])

    def test_retrieve_includes_status(self):
        secure(self.my_domain)
        with self.assertRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)
        ):
            response = self.client.get(
                self.reverse("v1:domain-detail", name=self.my_domain.name)
            )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(
            response.data["status"]["nameserver_status"], "correctly_delegated"
        )

    def test_status_is_read_only(self):
        name = self.random_domain_name()
        with self.assertRequests(self.requests_desec_domain_creation(name)):
            response = self.client.post(
                self.reverse("v1:domain-list"),
                {"name": name, "status": {"secure_since": "2020-01-01T00:00:00Z"}},
                format="json",
            )
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["status"]["secure_since"])
        self.assertIsNone(Domain.objects.get(name=name).secure_delegation_since)


@mock.patch.object(tasks.check_domain_delegation, "apply_async")
class DomainStatusEndpointTestCase(DomainOwnerTestCase):
    NUM_OWNED_DOMAINS = 5

    def setUp(self):
        super().setUp()
        cache.clear()  # throttle histories

    def url(self, domain=None):
        return self.reverse("v1:domain-status", name=(domain or self.my_domain).name)

    def record(self, domain=None, age=None, **kwargs):
        domain = domain or self.my_domain
        check = DelegationCheck.objects.record(domain, result(**kwargs))
        if age is not None:
            DelegationCheck.objects.filter(pk=check.pk).update(
                checked=timezone.now() - timedelta(seconds=age)
            )
        return check

    def record_insecure(self, domain=None, age=300):
        return self.record(domain, age=age, security_status=SecurityStatus.INSECURE)

    def status_of(self, domain=None):
        domain = Domain.objects.get(pk=(domain or self.my_domain).pk)
        return DomainStatusSerializer(domain).data

    def assertChecked(self, response, apply_async, domain=None):
        domain = domain or self.my_domain
        self.assertStatus(response, status.HTTP_202_ACCEPTED)
        apply_async.assert_called_once_with((domain.pk, 0), queue=tasks.ADHOC_QUEUE)
        apply_async.reset_mock()

    def assertNotChecked(self, response, apply_async, domain=None):
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.status_of(domain))
        self.assertNotIn("requested", response.data)
        apply_async.assert_not_called()

    def test_get_returns_status_without_asking_pdns(self, apply_async):
        self.record()
        with self.assertRequests():
            response = self.client.get(self.url())
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, self.status_of())
        self.assertEqual(response.data["security_status"], "secure")
        apply_async.assert_not_called()

    def test_post_checks_an_unchecked_domain(self, apply_async):
        before = timezone.now()
        response = self.client.post(self.url())
        self.assertChecked(response, apply_async)
        self.assertIsNone(response.data["checked"])
        requested = serializers.DateTimeField().to_internal_value(
            response.data["requested"]
        )
        self.assertTrue(before <= requested <= timezone.now())

    def test_post_checks_a_stale_insecure_domain(self, apply_async):
        self.record_insecure(age=tasks.STATUS_CHECK_MIN_AGE + 1)
        response = self.client.post(self.url())
        self.assertChecked(response, apply_async)
        self.assertEqual(response.data["security_status"], "insecure")

    def test_post_answers_from_a_fresh_check(self, apply_async):
        self.record_insecure(age=tasks.STATUS_CHECK_MIN_AGE - 10)
        self.assertNotChecked(self.client.post(self.url()), apply_async)

    def test_post_does_not_recheck_a_secure_domain(self, apply_async):
        self.record(age=86400)
        self.assertNotChecked(self.client.post(self.url()), apply_async)

    def test_post_does_not_recheck_a_secure_domain_whose_check_failed(
        self, apply_async
    ):
        self.record()
        self.record(
            age=86400,
            security_status=SecurityStatus.ERROR,
            nameserver_status=NameserverStatus.ERROR,
            nameservers=[],
        )
        self.assertNotChecked(self.client.post(self.url()), apply_async)

    def test_post_does_not_check_a_local_domain(self, apply_async):
        suffix = next(iter(settings.LOCAL_PUBLIC_SUFFIXES))
        for name in [f"mine.{suffix}", f"sub.mine.{suffix}"]:
            with self.subTest(name=name):
                domain = self.create_domain(name=name, owner=self.owner)
                self.assertNotChecked(
                    self.client.post(self.url(domain)), apply_async, domain
                )

    def test_foreign_domain(self, apply_async):
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url(self.other_domain))
                self.assertStatus(response, status.HTTP_404_NOT_FOUND)
        apply_async.assert_not_called()

    def test_post_requires_perm_create_domain(self, apply_async):
        token = self.create_token(owner=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.plain)
        response = self.client.post(self.url())
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)
        apply_async.assert_not_called()

        response = self.client.get(self.url())
        self.assertStatus(response, status.HTTP_200_OK)

    def test_post_with_broker_down(self, apply_async):
        apply_async.side_effect = OperationalError("broker down")
        response = self.client.post(self.url())
        self.assertStatus(response, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_other_methods_not_allowed(self, apply_async):
        for method in (self.client.put, self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                response = method(self.url(), {}, format="json")
                self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)
        apply_async.assert_not_called()

    @contextmanager
    def throttle_settings(self, per_domain, per_account):
        # Views bind their throttle classes at import, when the test settings
        # have disabled scoped throttling, so they are patched in here.
        rates = {
            "dns_api_cheap": ["1000/min"],
            "dns_api_per_domain_status_check": per_domain,
            "dns_api_status_check": per_account,
        }
        throttle_classes = [ScopedRatesThrottle, AccountScopedRatesThrottle]
        with (
            mock.patch.object(DomainViewSet, "throttle_classes", throttle_classes),
            self.settings(
                REST_FRAMEWORK={
                    **settings.REST_FRAMEWORK,
                    "DEFAULT_THROTTLE_RATES": rates,
                }
            ),
        ):
            yield

    def test_throttle_per_domain(self, apply_async):
        domain_a, domain_b = self.my_domains[:2]
        with self.throttle_settings(["1/min"], ["100/h"]):
            self.assertChecked(
                self.client.post(self.url(domain_a)), apply_async, domain_a
            )
            response = self.client.post(self.url(domain_a))
            self.assertStatus(response, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("Retry-After", response)
            # Another domain has its own budget, and reading is not limited.
            self.assertChecked(
                self.client.post(self.url(domain_b)), apply_async, domain_b
            )
            self.assertStatus(self.client.get(self.url(domain_a)), status.HTTP_200_OK)
        apply_async.assert_not_called()

    def test_throttle_per_account(self, apply_async):
        with self.throttle_settings(["100/min"], ["3/h"]):
            for domain in self.my_domains[:3]:
                self.assertChecked(
                    self.client.post(self.url(domain)), apply_async, domain
                )
            response = self.client.post(self.url(self.my_domains[3]))
            self.assertStatus(response, status.HTTP_429_TOO_MANY_REQUESTS)
        apply_async.assert_not_called()

    def test_forbidden_requests_do_not_use_up_the_budget(self, apply_async):
        token = self.create_token(owner=self.owner)
        with self.throttle_settings(["1/min"], ["1/h"]):
            self.client.credentials(HTTP_AUTHORIZATION="Token " + token.plain)
            for _ in range(3):
                response = self.client.post(self.url())
                self.assertStatus(response, status.HTTP_403_FORBIDDEN)
            self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.plain)
            self.assertChecked(self.client.post(self.url()), apply_async)
