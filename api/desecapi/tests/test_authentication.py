from rest_framework import status
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from desecapi.models import Token, User
from desecapi.tests.base import DynDomainOwnerTestCase, DesecTestCase


class DynUpdateAuthenticationTestCase(DynDomainOwnerTestCase):
    NUM_OWNED_DOMAINS = 1

    def _get_dyndns12(self):
        with self.assertPdnsNoRequestsBut(self.requests_desec_rr_sets_update()):
            return self.client.get(self.reverse('v1:dyndns12update'))

    def assertDynDNS12Status(self, status=HTTP_200_OK, authorization=None):
        if authorization:
            self.client.set_credentials_basic_auth(authorization)
        self.assertStatus(self._get_dyndns12(), status)

    def test_username_password(self):
        def _test_DynDNS12AuthenticationStatus(username, token, status):
            self.client.set_credentials_basic_auth(username, token)
            self.assertDynDNS12Status(status)

        _test_DynDNS12AuthenticationStatus('', self.token.key, HTTP_200_OK)
        _test_DynDNS12AuthenticationStatus(self.owner.get_username(), self.token.key, HTTP_200_OK)
        _test_DynDNS12AuthenticationStatus(self.my_domain.name, self.token.key, HTTP_200_OK)
        _test_DynDNS12AuthenticationStatus(' ' + self.my_domain.name, self.token.key, HTTP_401_UNAUTHORIZED)
        _test_DynDNS12AuthenticationStatus('wrong', self.token.key, HTTP_401_UNAUTHORIZED)
        _test_DynDNS12AuthenticationStatus('', 'wrong', HTTP_401_UNAUTHORIZED)
        _test_DynDNS12AuthenticationStatus(self.user.get_username(), 'wrong', HTTP_401_UNAUTHORIZED)

    def test_malformed_basic_auth(self):
        for authorization in [
            'asdf:asdf:sadf',
            'asdf',
            'bull[%]shit',
            '你好',
            '💩💩💩💩',
            '💩💩:💩💩',
        ]:
            self.assertDynDNS12Status(authorization=authorization, status=HTTP_401_UNAUTHORIZED)


class SignUpLoginTestCase(DesecTestCase):

    EMAIL = None
    PASSWORD = None

    REGISTRATION_ENDPOINT = None
    LOGIN_ENDPOINT = None

    REGISTRATION_STATUS = status.HTTP_201_CREATED
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

    def log_in(self):
        response = self.client.post(self.LOGIN_ENDPOINT, {
            'email': self.EMAIL,
            'password': self.PASSWORD,
        })
        self.assertContains(response, "auth_token", status_code=self.LOGIN_STATUS)

    def test_sign_up(self):
        self.sign_up()

    def test_log_in(self):
        self.sign_up()
        self.log_in()

    def test_log_in_twice(self):
        self.sign_up()
        self.log_in()
        self.log_in()

    def test_log_in_two_tokens(self):
        self.sign_up()  # this may create a token
        for _ in range(2):
            Token.objects.create(user=User.objects.get(email=self.EMAIL))
        self.log_in()


class URLSignUpLoginTestCase(SignUpLoginTestCase):

    REGISTRATION_ENDPOINT = '/api/v1/auth/users/'
    LOGIN_ENDPOINT = '/api/v1/auth/token/login/'

    LOGIN_STATUS = status.HTTP_201_CREATED


class LegacyURLSignUpLoginTestCase(SignUpLoginTestCase):

    REGISTRATION_ENDPOINT = '/api/v1/auth/users/create/'
    LOGIN_ENDPOINT = '/api/v1/auth/token/create/'

    LOGIN_STATUS = status.HTTP_201_CREATED


class LegacyURLSignUpLoginTestCase2(SignUpLoginTestCase):

    REGISTRATION_ENDPOINT = '/api/v1/auth/users/create/'
    LOGIN_ENDPOINT = '/api/v1/auth/token/create'

    LOGIN_STATUS = status.HTTP_200_OK


class TokenAuthenticationTestCase(DynDomainOwnerTestCase):

    def _get_domains(self):
        with self.assertPdnsNoRequestsBut(self.request_pdns_zone_retrieve_crypto_keys()):
            return self.client.get(self.reverse('v1:domain-list'))

    def assertAuthenticationStatus(self, status=HTTP_200_OK, token=''):
        self.client.set_credentials_token_auth(token)
        self.assertStatus(self._get_domains(), status)

    def test_token_case_sensitive(self):
        self.assertAuthenticationStatus(HTTP_200_OK, self.token.key)
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.key.upper())
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.key.lower())
