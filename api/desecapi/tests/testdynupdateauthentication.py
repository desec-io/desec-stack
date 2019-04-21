from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from desecapi.tests.base import DynDomainOwnerTestCase


class DynUpdateAuthenticationTestCase(DynDomainOwnerTestCase):
    NUM_OWNED_DOMAINS = 1

    def _get_dyndns12(self):
        with self.assertPdnsNoRequestsBut(self.requests_desec_rr_sets_update()):
            return self.client.get(self.reverse('v1:dyndns12update'))

    def assertDynDNS12Status(self, status=HTTP_200_OK, authorization=None):
        if authorization:
            self._set_credentials(self.client, 'Basic ' + self._http_header_base64_conversion(authorization))
        request = self._get_dyndns12()
        self.assertEqual(request.status_code, status, request)

    def assertDynDNS12AuthenticationStatus(self, username, token, status):
        # Note that this overwrites self.client's credentials, which may be unexpected
        self._set_credentials_basic_auth(self.client, username, token)
        self.assertDynDNS12Status(status)

    def test_username_password(self):
        # FIXME the following test fails
        # self.assertDyndns12AuthenticationStatus(self.user.get_username(), self.token.key, HTTP_200_OK)
        self.assertDynDNS12AuthenticationStatus('', self.token.key, HTTP_200_OK)
        self.assertDynDNS12AuthenticationStatus('wrong', self.token.key, HTTP_404_NOT_FOUND)
        self.assertDynDNS12AuthenticationStatus('', 'wrong', HTTP_401_UNAUTHORIZED)
        self.assertDynDNS12AuthenticationStatus(self.user.get_username(), 'wrong', HTTP_401_UNAUTHORIZED)

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
