from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import status

from desecapi import tasks, unbound
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
        # Clients need to tell this apart from an MFA challenge
        self.assertEqual(response.data["code"], "domain_limit_exceeded")

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


class DelegationTriggerTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_domain_creation_enqueues_a_check_after_commit(self):
        name = self.random_domain_name()
        with (
            mock.patch(
                "desecapi.views.domains.enqueue_user_delegation_check"
            ) as enqueue,
            self.assertRequests(self.requests_desec_domain_creation(name)),
            self.captureOnCommitCallbacks(execute=True) as callbacks,
        ):
            response = self.client.post(self.reverse("v1:domain-list"), {"name": name})
            # Still inside the transaction: the worker is another process on the
            # same database, and must not go looking for a domain that is not
            # committed yet.
            enqueue.assert_not_called()

        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(callbacks), 1)
        enqueue.assert_called_once_with(self.owner)

    def test_hitting_the_limit_enqueues_a_check(self):
        self.owner.limit_domains = self.owner.domains.count()
        self.owner.save()
        with mock.patch(
            "desecapi.views.domains.enqueue_user_delegation_check"
        ) as enqueue:
            response = self.client.post(
                self.reverse("v1:domain-list"), {"name": self.random_domain_name()}
            )
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)
        enqueue.assert_called_once_with(self.owner)


class EnqueueTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )

    def setUp(self):
        cache.clear()

    def test_is_rate_limited_per_user(self):
        with mock.patch.object(tasks.plan_user_delegation_checks, "delay") as delay:
            self.assertTrue(tasks.enqueue_user_delegation_check(self.user))
            self.assertFalse(tasks.enqueue_user_delegation_check(self.user))
        delay.assert_called_once_with(str(self.user.pk), tasks.ADHOC_MAX_AGE)

    def test_other_users_are_unaffected(self):
        other = User.objects.create_user(email="other@example.com", password="secret")
        with mock.patch.object(tasks.plan_user_delegation_checks, "delay"):
            self.assertTrue(tasks.enqueue_user_delegation_check(self.user))
            self.assertTrue(tasks.enqueue_user_delegation_check(other))

    def test_survives_an_unavailable_broker(self):
        """
        Callers sit in the request path, where the response is what the client
        is owed and the check is a nicety.
        """
        with mock.patch.object(
            tasks.plan_user_delegation_checks,
            "delay",
            side_effect=OperationalError("broker down"),
        ):
            self.assertFalse(tasks.enqueue_user_delegation_check(self.user))

    def test_survives_an_unavailable_cache(self):
        with mock.patch(
            "desecapi.tasks.cache.add", side_effect=RuntimeError("memcached down")
        ):
            self.assertFalse(tasks.enqueue_user_delegation_check(self.user))


class PlanUserDelegationChecksTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )
        cls.local_suffix = next(iter(settings.LOCAL_PUBLIC_SUFFIXES))

    def setUp(self):
        cache.clear()

    def plan(self, **kwargs):
        """Returns the (domain_id, max_age, queue) triples enqueued, in order."""
        with mock.patch.object(
            tasks.check_domain_delegation, "apply_async"
        ) as enqueued:
            tasks.plan_user_delegation_checks(str(self.user.pk), **kwargs)
        return [
            (*call.args[0], call.kwargs["queue"]) for call in enqueued.call_args_list
        ]

    def planned(self, **kwargs):
        return {domain_id for domain_id, _, _ in self.plan(**kwargs)}

    def test_enqueues_on_the_adhoc_queue(self):
        """
        Not the bulk queue: an ad-hoc check queued behind a bulk run waits for
        it, which is the whole thing the split exists to avoid. The freshness
        bound travels with the task, because the worker re-checks it.
        """
        domain = Domain.objects.create(name="example.com", owner=self.user)
        self.assertEqual(
            self.plan(max_age=1234), [(domain.pk, 1234, tasks.ADHOC_QUEUE)]
        )

    def test_resolves_the_domain_list_when_it_runs(self):
        """
        The task is handed a user, never a list of domains: what was true at
        enqueue time need not be true when a worker gets there.
        """
        early = Domain.objects.create(name="early.example.com", owner=self.user)
        with mock.patch.object(tasks.plan_user_delegation_checks, "delay") as delay:
            tasks.enqueue_user_delegation_check(self.user)

        # Between enqueueing and running: one domain more, one domain fewer.
        late = Domain.objects.create(name="late.example.com", owner=self.user)
        early.delete()

        with mock.patch.object(
            tasks.check_domain_delegation, "apply_async"
        ) as enqueued:
            tasks.plan_user_delegation_checks(*delay.call_args.args)
        self.assertEqual(
            {call.args[0][0] for call in enqueued.call_args_list}, {late.pk}
        )

    def test_enqueues_least_recently_checked_first(self):
        """
        What makes repeated requests work through a backlog instead of
        replanning its head over and over. Never-checked domains come first.
        """
        never = Domain.objects.create(name="never.example.com", owner=self.user)
        checked = []
        for i in range(3):
            domain = Domain.objects.create(name=f"d{i}.example.com", owner=self.user)
            check = DelegationCheck.objects.record(
                domain, result(security_status=DelegationCheck.SecurityStatus.INSECURE)
            )
            # Set explicitly: `checked` is auto_now, so recording three checks in
            # a loop would order them by how fast the loop runs.
            DelegationCheck.objects.filter(pk=check.pk).update(
                checked=timezone.now() - timedelta(days=3 - i)
            )
            checked.append(domain)

        self.assertEqual(
            [domain_id for domain_id, _, _ in self.plan()],
            [never.pk, *(domain.pk for domain in checked)],
        )

    def test_skips_secure_and_locally_registrable_domains(self):
        secure(Domain.objects.create(name="secure.example.com", owner=self.user))
        Domain.objects.create(name=f"mine.{self.local_suffix}", owner=self.user)
        insecure = Domain.objects.create(name="insecure.example.com", owner=self.user)
        self.assertEqual(self.planned(), {insecure.pk})

    def test_skips_recently_checked_domains(self):
        fresh = Domain.objects.create(name="fresh.example.com", owner=self.user)
        DelegationCheck.objects.record(
            fresh, result(security_status=DelegationCheck.SecurityStatus.INSECURE)
        )
        self.assertEqual(self.planned(max_age=3600), set())
        self.assertEqual(self.planned(max_age=0), {fresh.pk})

    def test_is_capped(self):
        for i in range(tasks.MAX_ADHOC_DOMAINS + 5):
            Domain.objects.create(name=f"d{i}.example.com", owner=self.user)
        self.assertEqual(len(self.planned()), tasks.MAX_ADHOC_DOMAINS)

    def test_survives_a_deleted_user(self):
        user_id = str(self.user.pk)
        self.user.domains.all().delete()
        User.objects.filter(pk=user_id).delete()
        with mock.patch.object(
            tasks.check_domain_delegation, "apply_async"
        ) as enqueued:
            tasks.plan_user_delegation_checks(user_id)
        enqueued.assert_not_called()

    def test_survives_a_malformed_user_id(self):
        """A message from an incompatible producer is not an incident."""
        with mock.patch.object(
            tasks.check_domain_delegation, "apply_async"
        ) as enqueued:
            tasks.plan_user_delegation_checks("not-a-uuid")
        enqueued.assert_not_called()


class CheckDomainDelegationTaskTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="test@example.com", password="secret1234"
        )
        cls.domain = Domain.objects.create(name="example.com", owner=cls.user)

    def test_records_the_result(self):
        with mock.patch("desecapi.delegation.check", return_value=result()) as check:
            tasks.check_domain_delegation(self.domain.pk)
        check.assert_called_once_with(self.domain.name)
        self.domain.refresh_from_db()
        self.assertIsNotNone(self.domain.secure_delegation_since)

    def test_skips_a_recently_checked_domain(self):
        """A duplicate message costs a query, not a check."""
        secure(self.domain)
        with mock.patch("desecapi.delegation.check") as check:
            tasks.check_domain_delegation(self.domain.pk, 3600)
        check.assert_not_called()

    def test_skips_a_deleted_domain(self):
        pk = self.domain.pk
        self.domain.delete()
        with mock.patch("desecapi.delegation.check") as check:
            tasks.check_domain_delegation(pk)
        check.assert_not_called()

    def test_survives_an_unavailable_resolver(self):
        """
        Failing would mail admins once per domain in the backlog; the failure
        is counted where it happens.
        """
        with mock.patch(
            "desecapi.delegation.check",
            side_effect=unbound.UnboundControlException("down"),
        ):
            tasks.check_domain_delegation(self.domain.pk)
        self.domain.refresh_from_db()
        self.assertIsNone(self.domain.current_delegation_check)
