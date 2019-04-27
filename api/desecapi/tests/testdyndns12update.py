from rest_framework import status

from desecapi.tests.base import DynDomainOwnerTestCase


class DynDNS12UpdateTest(DynDomainOwnerTestCase):

    def assertRRSet(self, name, subname, type_, content):
        response = self.client_token_authorized.get(self.reverse('v1:rrset', name=name, subname=subname, type=type_))

        if content:
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data['records'][0], content)
            self.assertEqual(response.data['ttl'], 60)
        else:
            self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def assertIP(self, ipv4=None, ipv6=None, name=None):
        name = name or self.my_domain.name
        self.assertRRSet(name, '', 'A', ipv4)
        self.assertRRSet(name, '', 'AAAA', ipv6)

    def test_identification_by_domain_name(self):
        self.client.set_credentials_basic_auth(self.my_domain.name + '.invalid', self.token.key)
        response = self.assertDynDNS12NoUpdate(mock_remote_addr='10.5.5.6')
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_identification_by_query_params(self):
        # /update?username=foobar.dedyn.io&password=secret
        self.client.set_credentials_basic_auth(None, None)
        response = self.assertDynDNS12Update(username=self.my_domain.name, password=self.token.key)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def test_deviant_ttl(self):
        """
        The dynamic update will try to set the TTL to 60. Here, we create
        a record with a different TTL beforehand and then make sure that
        updates still work properly.
        """
        with self.assertPdnsRequests(
            self.request_pdns_zone_update(self.my_domain.name),
            self.request_pdns_zone_notify(self.my_domain.name),
        ):
            response = self.client_token_authorized.patch_rr_set(self.my_domain.name, subname='', type_='A', ttl=3600)
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.assertDynDNS12Update(self.my_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def test_ddclient_dyndns1_v4_success(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myip=10.1.2.3
        with self.assertPdnsRequests(
                self.request_pdns_zone_update(self.my_domain.name),
                self.request_pdns_zone_notify(self.my_domain.name),
        ):
            response = self.client.get(
                self.reverse('v1:dyndns12update'),
                {
                    'action': 'edit',
                    'started': 1,
                    'hostname': 'YES',
                    'host_id': self.my_domain.name,
                    'myip': '10.1.2.3'
                }
            )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.1.2.3')

    def test_ddclient_dyndns1_v6_success(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myipv6=::1337
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            action='edit',
            started=1,
            hostname='YES',
            host_id=self.my_domain.name,
            myipv6='::1337'
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1', ipv6='::1337')

    def test_ddclient_dyndns2_v4_success(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myip=10.2.3.4
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            system='dyndns',
            hostname=self.my_domain.name,
            myip='10.2.3.4',
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.2.3.4')

    def test_ddclient_dyndns2_v6_success(self):
        # /nic/update?system=dyndns&hostname=foobar.dedyn.io&myipv6=::1338
        response = self.assertDynDNS12Update(
            domain_name=self.my_domain.name,
            system='dyndns',
            hostname=self.my_domain.name,
            myipv6='::666',
        )
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1', ipv6='::666')

    def test_fritz_box(self):
        # /
        response = self.assertDynDNS12Update(self.my_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def test_unset_ip(self):
        for (v4, v6) in [
            ('127.0.0.1', '::1'),
            ('127.0.0.1', ''),
            ('', '::1'),
            ('', ''),
        ]:
            response = self.assertDynDNS12Update(self.my_domain.name, ip=v4, ipv6=v6)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, 'good')
            self.assertIP(ipv4=v4, ipv6=v6)


class SingleDomainDynDNS12UpdateTest(DynDNS12UpdateTest):
    NUM_OWNED_DOMAINS = 1

    def test_identification_by_token(self):
        self.client.set_credentials_basic_auth('', self.token.key)
        response = self.assertDynDNS12Update(self.my_domain.name, mock_remote_addr='10.5.5.6')
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.5.5.6')


class MultipleDomainDynDNS12UpdateTest(DynDNS12UpdateTest):
    NUM_OWNED_DOMAINS = 4

    def test_identification_by_token(self):
        """
        Test if the conflict of having multiple domains, but not specifying which to update is correctly recognized.
        """
        self.client.set_credentials_basic_auth('', self.token.key)
        response = self.client.get(self.reverse('v1:dyndns12update'), REMOTE_ADDR='10.5.5.7')
        self.assertStatus(response, status.HTTP_409_CONFLICT)
