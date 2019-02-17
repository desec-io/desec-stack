from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
import base64
import httpretty
from django.conf import settings
import json
from django.utils import timezone
from desecapi.exceptions import PdnsException


class DynDNS12UpdateTest(APITestCase):
    owner = None
    token = None
    username = None
    password = None

    def setUp(self):
        self.owner = utils.createUser()
        self.token = utils.createToken(user=self.owner)
        self.domain = utils.generateDynDomainname()
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

        url = reverse('domain-list')
        data = {'name': self.domain}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.username = response.data['name']
        self.password = self.token
        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + ':' + self.password).encode()).decode())

        httpretty.enable()
        httpretty.HTTPretty.allow_net_connect = False
        self.httpretty_reset_uris()

    def httpretty_reset_uris(self):
        httpretty.reset()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + self.domain + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify')

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

    def assertIP(self, ipv4=None, ipv6=None, name=None):
        old_credentials = self.client._credentials['HTTP_AUTHORIZATION']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.password)
        name = name or self.username

        def verify_response(type_, ip):
            url = reverse('rrset', args=(name, '', type_,))
            response = self.client.get(url)

            if ip is not None:
                self.assertEqual(response.data['records'][0], ip)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['ttl'], 60)
            else:
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        verify_response('A', ipv4)
        verify_response('AAAA', ipv6)

        self.client.credentials(HTTP_AUTHORIZATION=old_credentials)

    def testDynDNS1UpdateDDClientSuccess(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myip=10.1.2.3
        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'action': 'edit',
                                       'started': 1,
                                       'hostname': 'YES',
                                       'host_id': self.username,
                                       'myip': '10.1.2.3'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.1.2.3')

    def testDynDNS1UpdateDDClientIPv6Success(self):
        # /nic/dyndns?action=edit&started=1&hostname=YES&host_id=foobar.dedyn.io&myipv6=::1337
        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'action': 'edit',
                                       'started': 1,
                                       'hostname': 'YES',
                                       'host_id': self.username,
                                       'myipv6': '::1337'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1', ipv6='::1337')

    def testDynDNS2UpdateDDClientIPv4Success(self):
        #/nic/update?system=dyndns&hostname=foobar.dedyn.io&myip=10.2.3.4
        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'system': 'dyndns',
                                       'hostname': self.username,
                                       'myip': '10.2.3.4'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.2.3.4')

    def testDynDNS2UpdateDDClientIPv6Success(self):
        #/nic/update?system=dyndns&hostname=foobar.dedyn.io&myipv6=::1338
        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'system': 'dyndns',
                                       'hostname': self.username,
                                       'myipv6': '::1338'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1', ipv6='::1338')

    def testFritzBox(self):
        #/
        url = reverse('dyndns12update')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def testUnsetIP(self):
        url = reverse('dyndns12update')

        def testVariant(params, **kwargs):
            response = self.client.get(url, params)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data, 'good')
            self.assertIP(**kwargs)

        testVariant({'ipv6': '::1337'}, ipv4='127.0.0.1', ipv6='::1337')
        testVariant({'ipv6': '::1337', 'myip': ''}, ipv4=None, ipv6='::1337')
        testVariant({'ipv6': '', 'ip': '1.2.3.4'}, ipv4='1.2.3.4', ipv6=None)
        testVariant({'ipv6': '', 'myipv4': ''}, ipv4=None, ipv6=None)

    def testIdentificationByUsernameDomainname(self):
        # To force identification by the provided username (which is the domain name)
        # we add a second domain for the current user.

        name = 'second-' + self.domain
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify', status=200)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('domain-list')
        response = self.client.post(url, {'name': name})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + ':' + self.password).encode()).decode())
        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.5.5.5')

        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + '.invalid:' + self.password).encode()).decode())
        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.5')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testIdentificationByTokenWithEmptyUser(self):
        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((':' + self.password).encode()).decode())
        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.6')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.5.5.6')

        # Now make sure we get a conflict when the user has multiple domains. Thus,
        # we add a second domain for the current user.

        name = 'second-' + self.domain
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify', status=200)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('domain-list')
        response = self.client.post(url, {'name': name})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.7')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testManual(self):
        #/update?username=foobar.dedyn.io&password=secret
        self.client.credentials(HTTP_AUTHORIZATION='')
        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'username': self.username,
                                       'password': self.token,
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def testDeviantTTL(self):
        # The dynamic update will try to set the TTL to 60. Here, we create
        # a record with a different TTL beforehand and then make sure that
        # updates still work properly.
        url = reverse('rrsets', args=(self.domain,))
        data = {'records': ['127.0.0.1'], 'ttl': 3600, 'type': 'A'}
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        response = self.client.post(url, json.dumps(data),
                                    content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.httpretty_reset_uris()

        url = reverse('dyndns12update')
        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + ':' + self.password).encode()).decode())
        response = self.client.get(url)
        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.').endswith(httpretty.httpretty.latest_requests[-2].path))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def testSuspendedUpdates(self):
        self.owner.locked = timezone.now()
        self.owner.save()

        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'system': 'dyndns',
                                       'hostname': self.domain,
                                       'myip': '10.1.1.1'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIP(ipv4='10.1.1.1')

        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.POST,
                               settings.NSLORD_PDNS_API + '/zones',
                               body='{"error": "Domain \'%s.\' already exists"}' % self.domain,
                               content_type="application/json", status=422)
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify', status=200)

        self.owner.unlock()

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.').endswith(httpretty.httpretty.latest_requests[-2].path))
        self.assertTrue(self.domain in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('10.1.1.1' in httpretty.httpretty.latest_requests[-2].parsed_body)

    def testSuspendedUpdatesDomainCreation(self):
        # Lock user
        self.owner.locked = timezone.now()
        self.owner.save()

        # While in locked state, create a domain and set some records
        url = reverse('domain-list')
        newdomain = utils.generateDynDomainname()

        data = {'name': newdomain}
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + newdomain + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('dyndns12update')
        response = self.client.get(url,
                                   {
                                       'system': 'dyndns',
                                       'hostname': newdomain,
                                       'myip': '10.2.2.2'
                                   })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIP(name=newdomain, ipv4='10.2.2.2')

        # See what happens upon unlock if pdns knows this domain already
        httpretty.register_uri(httpretty.POST,
                               settings.NSLORD_PDNS_API + '/zones',
                               body='{"error": "Domain \'' + newdomain + '.\' already exists"}',
                               status=422)

        with self.assertRaises(PdnsException) as cm:
            self.owner.unlock()

        self.assertEqual(str(cm.exception),
                         "Domain '" + newdomain + ".' already exists")

        # See what happens upon unlock if this domain is new to pdns
        httpretty.register_uri(httpretty.POST,
                               settings.NSLORD_PDNS_API + '/zones')

        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.')
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.',
                               body='{"rrsets": [{"comments": [], "name": "%s.", "records": [ { "content": "ns1.desec.io.", "disabled": false }, { "content": "ns2.desec.io.", "disabled": false } ], "ttl": 60, "type": "NS"}]}' % self.domain,
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + newdomain + './notify', status=200)

        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.',
                               body='{"rrsets": [{"comments": [], "name": "%s.", "records": [ { "content": "ns1.desec.io.", "disabled": false }, { "content": "ns2.desec.io.", "disabled": false } ], "ttl": 60, "type": "NS"}]}' % self.domain,
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify', status=200)

        self.owner.unlock()

        self.assertEqual(httpretty.httpretty.latest_requests[-5].method, 'POST')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones').endswith(httpretty.httpretty.latest_requests[-5].path))
        self.assertEqual(httpretty.httpretty.latest_requests[-3].method, 'PATCH')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.').endswith(httpretty.httpretty.latest_requests[-3].path))
        self.assertTrue('10.2.2.2' in httpretty.httpretty.latest_requests[-3].parsed_body)
