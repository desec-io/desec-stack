from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from django.db import transaction
from desecapi.models import Domain
from django.core import mail
import httpretty
from django.conf import settings


class UnauthenticatedDomainTests(APITestCase):
    def testExpectUnauthorizedOnGet(self):
        url = reverse('domain-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnPost(self):
        url = reverse('domain-list')
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnPut(self):
        url = reverse('domain-detail', args=(1,))
        response = self.client.put(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnDelete(self):
        url = reverse('domain-detail', args=(1,))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedDomainTests(APITestCase):
    def setUp(self):
        if not hasattr(self, 'owner'):
            self.owner = utils.createUser()
            self.ownedDomains = [utils.createDomain(self.owner), utils.createDomain(self.owner)]
            self.otherDomains = [utils.createDomain(), utils.createDomain()]
            self.token = utils.createToken(user=self.owner)
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

    def testExpectOnlyOwnedDomains(self):
        url = reverse('domain-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['name'], self.ownedDomains[0].name)
        self.assertEqual(response.data[1]['name'], self.ownedDomains[1].name)

    def testCanDeleteOwnedDomain(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantDeleteOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanGetOwnedDomains(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.ownedDomains[1].name)

    def testCantGetOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanPutOwnedDomain(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        newname = utils.generateDomainname()
        response.data['name'] = newname
        response = self.client.put(url, response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], newname)

    def testCantPutOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.put(url, {})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanPostDomains(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(response.data['dyn'], False)

    def testCanPostDynDomains(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname(), 'dyn': True}
        response = self.client.post(url, data)
        email = str(mail.outbox[0].message())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(data['name'] in email)
        self.assertTrue(self.token in email)
        self.assertEqual(response.data['dyn'], True)

    def testCantPostSameDomainTwice(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname(), 'dyn': True}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCanUpdateARecord(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        response.data['arecord'] = '10.13.3.7'
        response = self.client.put(url, response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['arecord'], '10.13.3.7')

    def testCanUpdateAAAARecord(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        response.data['aaaarecord'] = 'fe80::a11:10ff:fee0:ff77'
        response = self.client.put(url, response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['aaaarecord'], 'fe80::a11:10ff:fee0:ff77')

    def testPostingCausesPdnsAPICall(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.POWERDNS_API + '/zones')

        url = reverse('domain-list')
        data = {'name': utils.generateDomainname(), 'dyn': True}
        response = self.client.post(url, data)

        self.assertTrue(data['name'] in httpretty.last_request().parsed_body)
        self.assertTrue('ns1.desec.io' in httpretty.last_request().parsed_body)

    def testUpdateingCausesPdnsAPICall(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)

        httpretty.enable()
        httpretty.register_uri(httpretty.PATCH, settings.POWERDNS_API + '/zones/' + response.data['name'])

        response.data['arecord'] = '10.13.3.7'
        response = self.client.put(url, response.data)

        self.assertTrue('10.13.3.7' in httpretty.last_request().parsed_body)

    def testDomainDetailURL(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        urlByName = reverse('domain-detail/byName', args=(self.ownedDomains[1].name,))

        self.assertTrue(("/%d" % self.ownedDomains[1].pk) in url)
        self.assertTrue("/" + self.ownedDomains[1].name in urlByName)

    def testCantUseInvalidCharactersInDomainName(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.POWERDNS_API + '/zones')

        outboxlen = len(mail.outbox)
        invalidnames = [
            'with space.dedyn.io',
            'another space.de',
            ' spaceatthebeginning.com',
            'percentage%sign.com',
            '%percentagesign.dedyn.io',
            'slash/desec.io',
            '/slashatthebeginning.dedyn.io',
            '\\backslashatthebeginning.dedyn.io',
            'backslash\\inthemiddle.at',
            '@atsign.com',
            'at@sign.com',
        ]

        url = reverse('domain-list')
        for domainname in invalidnames:
            data = {'name': domainname, 'dyn': True}
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(len(mail.outbox), outboxlen)
