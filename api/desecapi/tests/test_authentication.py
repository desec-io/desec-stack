import re

from django.core import mail
from rest_framework import status
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from desecapi.models import Token, User
from desecapi.tests.base import DynDomainOwnerTestCase, DesecTestCase


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

        assertDynDNS12AuthenticationStatus('', self.token.key, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(self.owner.get_username(), self.token.key, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(self.my_domain.name, self.token.key, HTTP_200_OK)
        assertDynDNS12AuthenticationStatus(' ' + self.my_domain.name, self.token.key, HTTP_401_UNAUTHORIZED)
        assertDynDNS12AuthenticationStatus('wrong', self.token.key, HTTP_401_UNAUTHORIZED)
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


class SignUpLoginTestCase(DesecTestCase):

    EMAIL = None
    PASSWORD = None

    REGISTRATION_ENDPOINT = None
    LOGIN_ENDPOINT = None

    REGISTRATION_STATUS = status.HTTP_202_ACCEPTED
    LOGIN_STATUS = status.HTTP_200_OK

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.EMAIL = self.random_username()
        self.PASSWORD = self.random_password()
        if not self.REGISTRATION_ENDPOINT:
            self.REGISTRATION_ENDPOINT = self.reverse('v1:register')
        if not self.LOGIN_ENDPOINT:
            self.LOGIN_ENDPOINT = self.reverse('v1:login')

    def sign_up(self):
        self.assertStatus(
            self.client.post(self.REGISTRATION_ENDPOINT, {
                'email': self.EMAIL,
                'password': self.PASSWORD,
            }),
            self.REGISTRATION_STATUS
        )

    def activate(self):
        total = 1
        self.assertEqual(len(mail.outbox), total, "Expected %i message in the outbox, but found %i." %
                         (total, len(mail.outbox)))
        email = mail.outbox[-1]
        self.assertTrue('Welcome' in email.subject)
        confirmation_link = re.search(r'following link:\s+([^\s]*)', email.body).group(1)
        self.client.get(confirmation_link)

    def log_in(self):
        response = self.client.post(self.LOGIN_ENDPOINT, {
            'email': self.EMAIL,
            'password': self.PASSWORD,
        })
        self.assertContains(response, "auth_token", status_code=self.LOGIN_STATUS)

    def test_sign_up(self):
        self.sign_up()
        self.assertFalse(User.objects.get(email=self.EMAIL).is_active)

    def test_activate(self):
        self.sign_up()
        self.activate()
        self.assertTrue(User.objects.get(email=self.EMAIL).is_active)

    def test_log_in(self):
        self.sign_up()
        self.activate()
        self.log_in()

    def test_log_in_twice(self):
        self.sign_up()
        self.activate()
        self.log_in()
        self.log_in()

    def test_log_in_two_tokens(self):
        self.sign_up()
        self.activate()
        for _ in range(2):
            Token.objects.create(user=User.objects.get(email=self.EMAIL))
        self.log_in()


class TokenAuthenticationTestCase(DynDomainOwnerTestCase):

    def _get_domains(self):
        with self.assertPdnsNoRequestsBut(self.request_pdns_zone_retrieve_crypto_keys()):
            return self.client.get(self.reverse('v1:domain-list'))

    def assertAuthenticationStatus(self, code=HTTP_200_OK, token=''):
        self.client.set_credentials_token_auth(token)
        self.assertStatus(self._get_domains(), code)

    def test_token_case_sensitive(self):
        self.assertAuthenticationStatus(HTTP_200_OK, self.token.key)
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.key.upper())
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.key.lower())
