from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from django.db import transaction
from desecapi.models import Domain
from django.core import mail
import httpretty
from django.conf import settings
import json


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
        httpretty.reset()
        httpretty.disable()
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
        httpretty.enable()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.ownedDomains[1].name+ '.')

        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(httpretty.last_request().method, 'DELETE')
        self.assertEqual(httpretty.last_request().headers['Host'], 'nsmaster:8081')

        httpretty.reset()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.ownedDomains[1].name+ '.')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(isinstance(httpretty.last_request(), httpretty.core.HTTPrettyRequestEmpty))

    def testCantDeleteOtherDomains(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.otherDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.otherDomains[1].name+ '.')

        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(isinstance(httpretty.last_request(), httpretty.core.HTTPrettyRequestEmpty))
        self.assertTrue(Domain.objects.filter(pk=self.otherDomains[1].pk).exists())

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
        response.data['arecord'] = '1.2.3.4'
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['arecord'], '1.2.3.4')

    def testCantChangeDomainName(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        newname = utils.generateDomainname()
        response.data['name'] = newname
        response.data['arecord'] = None
        response.data['aaaarecord'] = None
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.ownedDomains[1].name)

    def testCantPutOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.put(url, json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanPostDomains(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)

    def testCantPostSameDomainTwice(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCantPostUnavailableDomain(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones',
                               body='{"error": "Domain \'' + name + '.\' already exists"}', status=422)

        url = reverse('domain-list')
        data = {'name': name}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCanPostComplicatedDomains(self):
        url = reverse('domain-list')
        data = {'name': 'very.long.domain.name.' + utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testCanUpdateARecord(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        response.data['arecord'] = '10.13.3.7'
        response.data['aaaarecord'] = None
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['arecord'], '10.13.3.7')

    def testCanUpdateAAAARecord(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        response.data['arecord'] = None
        response.data['aaaarecord'] = 'fe80::a11:10ff:fee0:ff77'
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['aaaarecord'], 'fe80::a11:10ff:fee0:ff77')

    def testCanUpdateAcmeChallenge(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)
        response.data['acme_challenge'] = 'test_challenge'
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['acme_challenge'], 'test_challenge')

    def testPostingCausesPdnsAPICall(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')

        url = reverse('domain-list')
        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)

        self.assertTrue(data['name'] in httpretty.last_request().parsed_body)
        self.assertTrue('ns1.desec.io' in httpretty.last_request().parsed_body)

    def testPostingWithRecordsCausesPdnsAPIPatch(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + name + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify')

        url = reverse('domain-list')
        data = {'name': name, 'arecord': '1.3.3.7', 'aaaarecord': 'dead::beef', 'acme_challenge': 'letsencrypt_ftw'}
        response = self.client.post(url, data)

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue(data['name'] in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('1.3.3.7' in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('dead::beef' in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('letsencrypt_ftw' in httpretty.httpretty.latest_requests[-2].parsed_body)

    def testPostDomainCausesPdnsAPIPatch(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + name + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify')

        url = reverse('domain-list')
        data = {'name': name, 'acme_challenge': 'letsencrypt_ftw'}
        self.client.post(url, data)

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue(data['name'] in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertTrue('letsencrypt_ftw' in httpretty.httpretty.latest_requests[-2].parsed_body)

    def testUpdateingCausesPdnsAPIPatchCall(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)

        httpretty.enable()
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + response.data['name'] + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + response.data['name'] + './notify')

        response.data['arecord'] = '10.13.3.7'
        self.client.put(url, json.dumps(response.data), content_type='application/json')

        self.assertTrue('10.13.3.7' in httpretty.httpretty.latest_requests[-2].parsed_body)

    def testUpdateingCausesPdnsAPINotifyCall(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.get(url)

        httpretty.enable()
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + response.data['name'] + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + response.data['name'] + './notify')

        response.data['arecord'] = '10.13.3.10'
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')

        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'PATCH')
        self.assertTrue('10.13.3.10' in httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertEqual(httpretty.last_request().method, 'PUT')

    def testDomainDetailURL(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        urlByName = reverse('domain-detail/byName', args=(self.ownedDomains[1].name,))

        self.assertTrue(("/%d" % self.ownedDomains[1].pk) in url)
        self.assertTrue("/" + self.ownedDomains[1].name in urlByName)

    def testRollback(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones', body="some error", status=500)

        url = reverse('domain-list')
        data = {'name': name}
        try:
            response = self.client.post(url, data)
        except:
            pass

        self.assertFalse(Domain.objects.filter(name=name).exists())


class AuthenticatedDynDomainTests(APITestCase):
    def setUp(self):
        httpretty.reset()
        httpretty.disable()
        if not hasattr(self, 'owner'):
            self.owner = utils.createUser(dyn=True)
            self.ownedDomains = [utils.createDomain(self.owner, dyn=True), utils.createDomain(self.owner, dyn=True)]
            self.otherDomains = [utils.createDomain(), utils.createDomain()]
            self.token = utils.createToken(user=self.owner)
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

    def testCanDeleteOwnedDynDomain(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.ownedDomains[1].name+ '.')
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/dedyn.io.')

        url = reverse('domain-detail', args=(self.ownedDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(httpretty.last_request().method, 'PATCH')
        self.assertEqual(httpretty.last_request().headers['Host'], 'nslord:8081')
        self.assertTrue('"NS"' in httpretty.last_request().parsed_body)
        self.assertTrue('"' + self.ownedDomains[1].name + '."' in httpretty.last_request().parsed_body)
        self.assertTrue('"DELETE"' in httpretty.last_request().parsed_body)

        httpretty.reset()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.ownedDomains[1].name+ '.')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(isinstance(httpretty.last_request(), httpretty.core.HTTPrettyRequestEmpty))

    def testCantDeleteOtherDynDomains(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.otherDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.otherDomains[1].name+ '.')

        url = reverse('domain-detail', args=(self.otherDomains[1].pk,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(isinstance(httpretty.last_request(), httpretty.core.HTTPrettyRequestEmpty))
        self.assertTrue(Domain.objects.filter(pk=self.otherDomains[1].pk).exists())

    def testCanPostDynDomains(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDynDomainname()}
        response = self.client.post(url, data)
        email = str(mail.outbox[0].message())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(data['name'] in email)
        self.assertTrue(self.token in email)

    def testCantPostNonDynDomains(self):
        url = reverse('domain-list')

        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {'name': 'very.long.domain.' + utils.generateDynDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


    def testLimitDynDomains(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')

        outboxlen = len(mail.outbox)

        url = reverse('domain-list')
        for i in range(settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT-2):
            data = {'name': utils.generateDynDomainname()}
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(len(mail.outbox), outboxlen+i+1)

        data = {'name': utils.generateDynDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(len(mail.outbox), outboxlen + settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT-2)

    def testCantUseInvalidCharactersInDomainNamePDNS(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')

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
            data = {'name': domainname}
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(len(mail.outbox), outboxlen)
