from django.conf import settings
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework import serializers, status

from desecapi.models import DelegationCheck, Domain, User
from desecapi.models.domains import under_local_public_suffix_q
from desecapi.serializers import DomainStatusSerializer
from desecapi.tests.base import DomainOwnerTestCase
from desecapi.tests.test_delegation import result, secure

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
