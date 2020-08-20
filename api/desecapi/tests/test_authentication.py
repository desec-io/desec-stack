import json

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

    def assertAuthenticationStatus(self, code, token=None, **kwargs):
        self.client.set_credentials_token_auth(token or self.token.plain)

        # only forward REMOTE_ADDR if not None
        if kwargs.get('REMOTE_ADDR') is None:
            kwargs.pop('REMOTE_ADDR', None)

        response = self.client.get(self.reverse('v1:root'), **kwargs)
        body = json.dumps({'detail': 'Invalid token.'}) if code == HTTP_401_UNAUTHORIZED else None
        self.assertResponse(response, code, body)

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
