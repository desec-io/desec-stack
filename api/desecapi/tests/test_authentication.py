from datetime import timedelta
import json
from unittest import mock

from django.utils import timezone
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from desecapi.models import Token
from desecapi.tests.base import DynDomainOwnerTestCase


class DynUpdateAuthenticationTestCase(DynDomainOwnerTestCase):
    NUM_OWNED_DOMAINS = 1

    def _get_dyndns12(self):
        with self.assertPdnsNoRequestsBut(self.requests_desec_rr_sets_update()):
            return self.client.get(self.reverse('v1:dyndns12update'))

    def assertDynDNS12Status(self, code=HTTP_200_OK, authorization=None):
        if authorization:
            self.client.set_credentials_basic_auth(authorization)
        self.assertStatus(self._get_dyndns12(), code)

    def test_username_password(self):
        # noinspection PyPep8Naming
        def assertDynDNS12AuthenticationStatus(username, token, code):
            self.client.set_credentials_basic_auth(username, token)
            self.assertDynDNS12Status(code)

        assertDynDNS12AuthenticationStatus('', self.token.plain, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(self.owner.get_username(), self.token.plain, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(self.my_domain.name, self.token.plain, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(' ' + self.my_domain.name, self.token.plain, HTTP_401_UNAUTHORIZED)
        assertDynDNS12AuthenticationStatus('wrong', self.token.plain, HTTP_401_UNAUTHORIZED)
        assertDynDNS12AuthenticationStatus('', 'wrong', HTTP_401_UNAUTHORIZED)
        assertDynDNS12AuthenticationStatus(self.user.get_username(), 'wrong', HTTP_401_UNAUTHORIZED)

    def test_malformed_basic_auth(self):
        for authorization in [
            'asdf:asdf:sadf',
            'asdf',
            'bull[%]shit',
            '你好',
            '💩💩💩💩',
            '💩💩:💩💩',
        ]:
            self.assertDynDNS12Status(authorization=authorization, code=HTTP_401_UNAUTHORIZED)


class TokenAuthenticationTestCase(DynDomainOwnerTestCase):

    def setUp(self):
        super().setUp()
        # Refresh token from database, but keep plain value
        self.token, self.token.plain = Token.objects.get(pk=self.token.pk), self.token.plain

    def assertAuthenticationStatus(self, code, plain=None, expired=False ,**kwargs):
        plain = plain or self.token.plain
        self.client.set_credentials_token_auth(plain)

        # only forward REMOTE_ADDR if not None
        if kwargs.get('REMOTE_ADDR') is None:
            kwargs.pop('REMOTE_ADDR', None)

        response = self.client.get(self.reverse('v1:root'), **kwargs)
        body = json.dumps({'detail': 'Invalid token.'}) if code == HTTP_401_UNAUTHORIZED else None
        self.assertResponse(response, code, body)

        if expired:
            key = Token.make_hash(plain)
            self.assertFalse(Token.objects.get(key=key).is_valid)

    def test_token_case_sensitive(self):
        self.assertAuthenticationStatus(HTTP_200_OK)
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.plain.upper())
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.plain.lower())

    def test_token_subnets(self):
        datas = [  # Format: allowed_subnets, status, client_ip | None, [client_ip, ...]
            ([], HTTP_401_UNAUTHORIZED, None),
            (['127.0.0.1'], HTTP_200_OK, None),
            (['1.2.3.4'], HTTP_401_UNAUTHORIZED, None),
            (['1.2.3.4'], HTTP_200_OK, '1.2.3.4'),
            (['1.2.3.0/24'], HTTP_200_OK, '1.2.3.4'),
            (['1.2.3.0/24'], HTTP_401_UNAUTHORIZED, 'bade::affe'),
            (['bade::/64'], HTTP_200_OK, 'bade::affe'),
            (['bade::/64', '1.2.3.0/24'], HTTP_200_OK, 'bade::affe', '1.2.3.66'),
        ]

        for allowed_subnets, status, client_ips in ((*data[:2], data[2:]) for data in datas):
            self.token.allowed_subnets = allowed_subnets
            self.token.save()
            for client_ip in client_ips:
                self.assertAuthenticationStatus(status, REMOTE_ADDR=client_ip)

    def test_token_max_age(self):
        # No maximum age: can use now and in ten years
        self.token.max_age = None
        self.token.save()

        self.assertAuthenticationStatus(HTTP_200_OK)
        with mock.patch('desecapi.models.timezone.now', return_value=timezone.now() + timedelta(days=3650)):
            self.assertAuthenticationStatus(HTTP_200_OK)

        # Maximum age zero: token cannot be used
        self.token.max_age = timedelta(0)
        self.token.save()
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)

        # Maximum age 10 10:10:10: can use one second before, but not once second after
        period = timedelta(days=10, hours=10, minutes=10, seconds=10)
        self.token.max_age = period
        self.token.save()

        second = timedelta(seconds=1)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + period - second):
            self.assertAuthenticationStatus(HTTP_200_OK)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + period + second):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)

    def test_token_max_unused_period(self):
        plain = self.token.plain
        second = timedelta(seconds=1)

        # Maximum unused period zero: token cannot be used
        self.token.max_unused_period = timedelta(0)
        self.token.save()
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)

        # Maximum unused period
        period = timedelta(days=10, hours=10, minutes=10, seconds=10)
        self.token.max_unused_period = period
        self.token.save()

        # Can't use after period if token was never used (last_used is None)
        self.assertIsNone(self.token.last_used)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + period + second):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, plain=plain, expired=True)
            self.assertIsNone(Token.objects.get(pk=self.token.pk).last_used)  # unchanged

        # Can use after half the period
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + period/2):
            self.assertAuthenticationStatus(HTTP_200_OK, plain=plain)
        self.token = Token.objects.get(pk=self.token.pk)  # update last_used field

        # Can't use once another period is over
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.last_used + period + second):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, plain=plain, expired=True)
            self.assertEqual(self.token.last_used, Token.objects.get(pk=self.token.pk).last_used)  # unchanged

        # ... but one second before, and also for one more period
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.last_used + period - second):
            self.assertAuthenticationStatus(HTTP_200_OK, plain=plain)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.last_used + 2*period - 2*second):
            self.assertAuthenticationStatus(HTTP_200_OK, plain=plain)

        # No maximum age: can use now and in ten years
        self.token.max_unused_period = None
        self.token.save()

        self.assertAuthenticationStatus(HTTP_200_OK, plain=plain)
        with mock.patch('desecapi.models.timezone.now', return_value=timezone.now() + timedelta(days=3650)):
            self.assertAuthenticationStatus(HTTP_200_OK, plain=plain)

    def test_token_max_age_max_unused_period(self):
        hour = timedelta(hours=1)
        self.token.max_age = 3 * hour
        self.token.max_unused_period = hour
        self.token.save()

        # max_unused_period wins if tighter than max_age
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 1.25*hour):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)

        # Can use immediately
        self.assertAuthenticationStatus(HTTP_200_OK)

        # Can use continuously within max_unused_period
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 0.75*hour):
            self.assertAuthenticationStatus(HTTP_200_OK)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 1.5*hour):
            self.assertAuthenticationStatus(HTTP_200_OK)

        # max_unused_period wins again if tighter than max_age
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 2.75*hour):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)

        # Can use continuously within max_unused_period
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 2.25*hour):
            self.assertAuthenticationStatus(HTTP_200_OK)
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 2.75*hour):
            self.assertAuthenticationStatus(HTTP_200_OK)

        # max_age wins again if tighter than max_unused_period
        with mock.patch('desecapi.models.timezone.now', return_value=self.token.created + 3.25*hour):
            self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, expired=True)
