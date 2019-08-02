from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.reverse import reverse
from rest_framework.versioning import NamespaceVersioning

from desecapi import models
from desecapi.emails import send_account_lock_email
from desecapi.tests.base import DesecTestCase


class RegistrationTestCase(DesecTestCase):

    def assertRegistration(self, remote_addr='', status=201, **kwargs):
        url = reverse('v1:register')
        post_kwargs = {}
        if remote_addr:
            post_kwargs['REMOTE_ADDR'] = remote_addr
        response = self.client.post(url, kwargs, **post_kwargs)
        self.assertStatus(response, status)
        return response


class SingleRegistrationTestCase(RegistrationTestCase):

    def setUp(self):
        super().setUp()
        email = self.random_username()
        self.assertRegistration(
            email=email,
            password=self.random_password(),
            remote_addr="1.3.3.7",
        )
        self.user = models.User.objects.get(email=email)

    def test_registration_successful(self):
        self.assertEqual(self.user.registration_remote_ip, "1.3.3.7")

    def test_token_email(self):
        self.assertEqual(len(mail.outbox), 1 if not self.user.locked else 2)
        self.assertTrue(self.user.get_or_create_first_token() in mail.outbox[-1].body)

    def test_send_captcha_email_manually(self):
        # TODO see if this can be replaced by a method of self.client
        r = RequestFactory().request(HTTP_HOST=settings.ALLOWED_HOSTS[0])
        r.version = 'v1'
        r.versioning_scheme = NamespaceVersioning()
        # end TODO

        mail.outbox = []
        send_account_lock_email(r, self.user)
        self.assertEqual(len(mail.outbox), 1)


class MultipleRegistrationTestCase(RegistrationTestCase):

    def _registrations(self):
        return []

    def setUp(self):
        super().setUp()
        self.users = []
        for (ip, hours_ago, email_host) in self._registrations():
            email = self.random_username(email_host)
            ip = ip or self.random_ip()
            self.assertRegistration(
                email=email,
                password=self.random_password(),
                dyn=True,
                remote_addr=ip,
            )
            user = models.User.objects.get(email=email)
            self.assertEqual(user.registration_remote_ip, ip)
            user.created = timezone.now() - timedelta(hours=hours_ago)
            user.save()
            self.users.append(user)


class MultipleRegistrationSameIPShortTime(MultipleRegistrationTestCase):

    NUM_REGISTRATIONS = 3

    def _registrations(self):
        return [('1.3.3.7', 0, None) for _ in range(self.NUM_REGISTRATIONS)]

    def test_is_locked(self):
        self.assertIsNone(self.users[0].locked)
        for i in range(1, self.NUM_REGISTRATIONS):
            self.assertIsNotNone(self.users[i].locked)


class MultipleRegistrationDifferentIPShortTime(MultipleRegistrationTestCase):

    NUM_REGISTRATIONS = 10

    def _registrations(self):
        return [('1.3.3.%s' % i, 0, None) for i in range(self.NUM_REGISTRATIONS)]

    def test_is_not_locked(self):
        for user in self.users:
            self.assertIsNone(user.locked)


class MultipleRegistrationSameIPLongTime(MultipleRegistrationTestCase):

    NUM_REGISTRATIONS = 10

    def _registrations(self):
        return [
            ('1.3.3.7', settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS, None)
            for _ in range(self.NUM_REGISTRATIONS)
        ]

    def test_is_not_locked(self):
        for user in self.users:
            self.assertIsNone(user.locked)


class MultipleRegistrationSameEmailHostShortTime(MultipleRegistrationTestCase):

    NUM_REGISTRATIONS = settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT + 3

    def _registrations(self):
        host = self.random_domain_name()
        return [
            (None, 0, host)
            for _ in range(self.NUM_REGISTRATIONS)
        ]

    def test_is_locked(self):
        for i in range(self.NUM_REGISTRATIONS):
            if i < settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT:
                self.assertIsNone(self.users[i].locked)
            else:
                self.assertIsNotNone(self.users[i].locked)


class MultipleRegistrationsSameEmailHostLongTime(MultipleRegistrationTestCase):

    NUM_REGISTRATIONS = settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT + 3

    def _registrations(self):
        host = self.random_domain_name()
        return [
            (self.random_ip(), settings.ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS + 1, host)
            for _ in range(self.NUM_REGISTRATIONS)
        ]

    def test_is_not_locked(self):
        for user in self.users:
            self.assertIsNone(user.locked)
