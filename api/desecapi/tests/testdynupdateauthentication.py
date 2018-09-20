from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
import httpretty
import base64
from django.conf import settings


class DynUpdateAuthenticationTests(APITestCase):

    def setCredentials(self, username, password):
        self.client.credentials(
            HTTP_AUTHORIZATION='Basic ' + base64.b64encode((username + ':' + password).encode()).decode())

    def setUp(self):
        if not hasattr(self, 'owner'):
            self.username = utils.generateRandomString(12)
            self.password = utils.generateRandomString(12)
            self.user = utils.createUser(self.username, self.password)
            self.token = utils.createToken(user=self.user)
            self.setCredentials(self.username, self.password)
            self.url = reverse('dyndns12update')

            self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
            self.domain = utils.generateDynDomainname()
            url = reverse('domain-list')
            data = {'name': self.domain}
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            httpretty.enable()
            httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
            httpretty.register_uri(httpretty.GET,
                                   settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.',
                                   body='{"rrsets": []}',
                                   content_type="application/json")
            httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.domain + '.')
            httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.domain + './notify')

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

    def testSuccessfulAuthentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, 'good')

    def testWrongUsername(self):
        self.setCredentials('wrong', self.password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testWrongPassword(self):
        self.setCredentials(self.username, 'wrong')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testDoubleColonInAuthentication(self):
        self.client.credentials(
            HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + ':' + self.password + ':bullshit').encode()).decode())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testlNoColonInAuthentication(self):
        self.client.credentials(
            HTTP_AUTHORIZATION='Basic ' + base64.b64encode((self.username + '' + self.password).encode()).decode())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testNoValidEncoding(self):
        self.client.credentials(HTTP_AUTHORIZATION='Basic bull[%]shit')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

