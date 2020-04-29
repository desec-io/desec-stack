from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

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

    def _get_domains(self):
        with self.assertPdnsNoRequestsBut(self.request_pdns_zone_retrieve_crypto_keys()):
            return self.client.get(self.reverse('v1:domain-list'))

    def assertAuthenticationStatus(self, code=HTTP_200_OK, token=''):
        self.client.set_credentials_token_auth(token)
        self.assertStatus(self._get_domains(), code)

    def test_token_case_sensitive(self):
        self.assertAuthenticationStatus(HTTP_200_OK, self.token.plain)
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.plain.upper())
        self.assertAuthenticationStatus(HTTP_401_UNAUTHORIZED, self.token.plain.lower())
