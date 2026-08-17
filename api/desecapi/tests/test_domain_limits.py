from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status

from desecapi.models import DelegationCheck, Domain, User
from desecapi.serializers import UserSerializer
from desecapi.tests.base import DomainOwnerTestCase
from desecapi.tests.test_delegation import result, secure


class SecureDomainCountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )
        cls.local_suffix = next(iter(settings.LOCAL_PUBLIC_SUFFIXES))

    def test_counts_only_secure_domains(self):
        secure(Domain.objects.create(name="secure.example.com", owner=self.user))
        Domain.objects.create(name="unchecked.example.com", owner=self.user)
        insecure = Domain.objects.create(name="insecure.example.com", owner=self.user)
        DelegationCheck.objects.record(
            insecure,
            result(security_status=DelegationCheck.SecurityStatus.INSECURE),
        )
        self.assertEqual(self.user.secure_domain_count, 1)

    def test_domains_under_a_local_suffix_count_unmeasured(self):
        """
        Every zone between them and the public root is one we host and sign, so
        they are secure by construction -- no check needed, and none is run for
        them. That holds at any depth, not just for immediate children.
        """
        local = Domain.objects.create(name=f"mine.{self.local_suffix}", owner=self.user)
        deep = Domain.objects.create(
            name=f"sub.mine.{self.local_suffix}", owner=self.user
        )
        self.assertIsNone(local.secure_delegation_since)
        self.assertIsNone(deep.secure_delegation_since)
        self.assertEqual(self.user.secure_domain_count, 2)

        # Measuring them anyway (`check-delegation --include-local`) must not
        # count them twice.
        secure(local)
        secure(deep)
        self.assertEqual(self.user.secure_domain_count, 2)

    def test_other_users_domains_do_not_count(self):
        other = User.objects.create_user(email="other@example.com", password="secret")
        secure(Domain.objects.create(name="theirs.example.com", owner=other))
        self.assertEqual(self.user.secure_domain_count, 0)


class EffectiveLimitTestCase(TestCase):
    @staticmethod
    def limit_for(s, s_external=None, limit_domains=None):
        """
        s = all securely delegated domains, s_external = the non-local ones.
        They default to being the same, i.e. to a user with no dedyn.io domains.
        """
        user = User(limit_domains=limit_domains)
        counts = {
            "secure_domain_count": s,
            "secure_external_domain_count": s if s_external is None else s_external,
        }
        with mock.patch.multiple(
            User,
            **{
                name: mock.PropertyMock(return_value=value)
                for name, value in counts.items()
            },
        ):
            return user.effective_limit_domains

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=1)
    def test_formula(self):
        # s + max(default, round(sqrt(s))). Every additional secure domain
        # raises the limit, by one or two -- never by zero.
        expected = {
            0: 1,
            1: 2,
            2: 3,
            3: 5,
            4: 6,
            5: 7,
            6: 8,
            7: 10,
            9: 12,
            12: 15,
            13: 17,
            16: 20,
            20: 24,
            21: 26,
            25: 30,
            30: 35,
            50: 57,
            100: 110,
        }
        for s, limit in expected.items():
            with self.subTest(s=s):
                self.assertEqual(self.limit_for(s), limit)

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=1)
    def test_limit_is_monotone_in_small_steps(self):
        limits = [self.limit_for(s) for s in range(101)]
        for s, (before, after) in enumerate(zip(limits, limits[1:])):
            with self.subTest(s=s):
                self.assertIn(after - before, (1, 2))

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=15)
    def test_default_is_a_floor_under_the_headroom(self):
        # It floors the headroom, not the limit, so secure domains are added on
        # top of it rather than absorbed by it.
        self.assertEqual(self.limit_for(0), 15)
        self.assertEqual(self.limit_for(10), 25)  # round(sqrt(10)) = 3 < 15
        self.assertEqual(self.limit_for(13), 28)
        self.assertEqual(self.limit_for(256), 272)  # ... until 16 > 15

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=1)
    def test_locally_registrable_domains_pay_for_their_own_slot(self):
        """They are secure, so they must not crowd out quota earned elsewhere."""
        self.assertEqual(self.limit_for(3, s_external=3), 5)  # 3 external
        self.assertEqual(self.limit_for(5, s_external=3), 7)  # ... plus 2 local

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=15)
    def test_locally_registrable_domains_earn_no_headroom(self):
        for n in range(1, 40):
            with self.subTest(n=n):
                # A user holding n domains, all locally registrable: each pays
                # for its own slot, and the headroom stays at the floor.
                limit = self.limit_for(n, s_external=0)
                self.assertEqual(limit, n + 15)
                self.assertEqual(limit - self.limit_for(n - 1, s_external=0), 1)

    def test_explicit_limit_wins(self):
        self.assertEqual(self.limit_for(100, limit_domains=3), 3)
        self.assertEqual(self.limit_for(0, limit_domains=0), 0)


class DomainLimitEnforcementTestCase(DomainOwnerTestCase):
    """The owner starts with NUM_OWNED_DOMAINS (2) non-local domains."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.owner.limit_domains = None
        self.owner.save()

    def post_domain(self):
        name = self.random_domain_name()
        with self.assertRequests(self.requests_desec_domain_creation(name)):
            return self.client.post(self.reverse("v1:domain-list"), {"name": name})

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=2)
    def test_securing_domains_raises_the_limit(self):
        self.assertEqual(self.owner.effective_limit_domains, 2)
        response = self.client.post(
            self.reverse("v1:domain-list"), {"name": self.random_domain_name()}
        )
        self.assertContains(
            response, "Domain limit", status_code=status.HTTP_403_FORBIDDEN
        )

        # Two secure domains pay for their own slots, and the headroom floor
        # of 2 sits on top: 2 + max(2, round(sqrt(2))) = 4.
        for domain in self.my_domains:
            secure(domain)
        self.assertEqual(self.owner.effective_limit_domains, 4)
        self.assertStatus(self.post_domain(), status.HTTP_201_CREATED)

    @override_settings(DOMAIN_LIMIT_INSECURE_HEADROOM=2)
    def test_explicit_limit_is_not_overridden(self):
        for domain in self.my_domains:
            secure(domain)
        self.owner.limit_domains = 2
        self.owner.save()
        response = self.client.post(
            self.reverse("v1:domain-list"), {"name": self.random_domain_name()}
        )
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)


class UserSerializerTestCase(TestCase):
    def test_reports_the_effective_limit(self):
        """
        Clients see the limit that is enforced, never the null that means
        "computed" internally.
        """
        user = User.objects.create_user(email="test@example.com", password="secret1234")
        secure(Domain.objects.create(name="secure.example.com", owner=user))

        data = UserSerializer(user).data
        self.assertEqual(data["secure_domains"], 1)
        self.assertEqual(data["limit_domains"], user.effective_limit_domains)
        self.assertIsNotNone(data["limit_domains"])

        for field in ("limit_domains", "secure_domains"):
            self.assertTrue(UserSerializer().fields[field].read_only)
