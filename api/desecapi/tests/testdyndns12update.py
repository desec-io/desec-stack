from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from django.db import transaction
import base64
import httpretty
from django.conf import settings


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
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify')

    def tearDown(self):
        httpretty.disable()

    def assertIP(self, ipv4=None, ipv6=None):
        old_credentials = self.client._credentials['HTTP_AUTHORIZATION']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.password)
        url = reverse('domain-detail/byName', args=(self.username,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if ipv4 is not None:
            self.assertEqual(response.data['arecord'], ipv4)
        if ipv6 is not None:
            self.assertEqual(response.data['aaaarecord'], ipv6)
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
        self.assertIP(ipv6='::1337')

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
        self.assertIP(ipv6='::1338')

    def testFritzBoxIPv6(self):
        #/
        url = reverse('dyndns12update')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='127.0.0.1')

    def testIdentificationByUsernameDomainname(self):
        # To force identification by the provided username (which is the domain name)
        # we add a second domain for the current user.

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('domain-list')
        data = {'name': 'second-' + self.domain}
        response = self.client.post(url, data)
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
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testIdentificationByTokenWithEmptyUser(self):
        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode((':' + self.password).encode()).decode())
        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.6')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')
        self.assertIP(ipv4='10.5.5.6')

        # Now make sure we get a conflict when the user has multiple domains. Thus,
        # we add a second domain for the current user.

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('domain-list')
        data = {'name': 'second-' + self.domain}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('dyndns12update')
        response = self.client.get(url, REMOTE_ADDR='10.5.5.7')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testManualIPv6(self):
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

    def testSuspendedUpdates(self):
        self.owner.captcha_required = True
        self.owner.save()

        httpretty.reset()
        httpretty.enable()
        httpretty.HTTPretty.allow_net_connect = False

        domain = self.owner.domains.all()[0]
        domain.arecord = '10.1.1.1'
        domain.save()

        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.GET, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.', status=200)
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify', status=200)

        self.owner.unlock()

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.').endswith(httpretty.httpretty.latest_requests[-2].path))
        self.assertTrue(self.domain in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('10.1.1.1' in httpretty.httpretty.latest_requests[-2].parsed_body)

    def testSuspendedUpdatesDomainCreation(self):
        self.owner.captcha_required = True
        self.owner.save()

        httpretty.reset()
        httpretty.enable()
        httpretty.HTTPretty.allow_net_connect = False

        url = reverse('domain-list')
        newdomain = utils.generateDynDomainname()
        data = {'name': newdomain, 'dyn': True, 'arecord': '10.2.2.2'}
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        domain = self.owner.domains.all()[0]
        domain.arecord = '10.1.1.1'
        domain.save()

        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.')
        httpretty.register_uri(httpretty.GET, settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.', status=200)
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + newdomain + './notify', status=200)
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
        httpretty.register_uri(httpretty.GET, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.', status=200)
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify', status=200)

        self.owner.unlock()

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue(
                (settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.').endswith(httpretty.httpretty.latest_requests[-2].path) \
                or (settings.NSLORD_PDNS_API + '/zones/' + newdomain + '.').endswith(httpretty.httpretty.latest_requests[-2].path)
            )
        self.assertTrue('10.2.2.2' in httpretty.httpretty.latest_requests[-2].parsed_body)
