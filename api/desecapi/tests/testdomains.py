from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
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
        url = reverse('domain-detail', args=('example.com',))
        response = self.client.put(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnDelete(self):
        url = reverse('domain-detail', args=('example.com',))
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

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

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

        url = reverse('domain-detail', args=(self.ownedDomains[1].name,))
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

        url = reverse('domain-detail', args=(self.otherDomains[1].name,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(isinstance(httpretty.last_request(), httpretty.core.HTTPrettyRequestEmpty))
        self.assertTrue(Domain.objects.filter(pk=self.otherDomains[1].pk).exists())

    def testCanGetOwnedDomains(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + './cryptokeys',
                               body='[]',
                               content_type="application/json")

        url = reverse('domain-detail', args=(self.ownedDomains[1].name,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.ownedDomains[1].name)
        self.assertTrue(isinstance(response.data['keys'], list))

    def testCantGetOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].name,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantChangeDomainName(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].name,))
        response = self.client.get(url)
        newname = utils.generateDomainname()
        response.data['name'] = newname
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.ownedDomains[1].name)

    def testCantPutOtherDomains(self):
        url = reverse('domain-detail', args=(self.otherDomains[1].name,))
        response = self.client.put(url, json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanPostDomains(self):
        url = reverse('domain-list')
        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)

    def testCanPostReverseDomains(self):
        name = '0.8.0.0.0.1.c.a.2.4.6.0.c.e.e.d.4.4.0.1.a.0.1.0.8.f.4.0.1.0.a.2.ip6.arpa'

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones', status=201)
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify', status=200)

        url = reverse('domain-list')
        data = {'name': name}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)

    def testCantPostDomainAlreadyTakenInAPI(self):
        url = reverse('domain-list')

        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        data = {'name': 'www.' + self.ownedDomains[0].name}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'name': 'www.' + self.otherDomains[0].name}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCantPostDomainAlreadyTakenInPdns(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones',
                               body='{"error": "Domain \'' + name + '.\' already exists"}', status=422)

        url = reverse('domain-list')
        data = {'name': name}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCantPostDomainsViolatingPolicy(self):
        url = reverse('domain-list')

        data = {'name': '*.' + utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("does not match the required pattern." in response.data['name'][0])

    def testCanPostComplicatedDomains(self):
        url = reverse('domain-list')
        data = {'name': 'very.long.domain.name.' + utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testPostingCausesPdnsAPICalls(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + '.',
                               body='{"rrsets": []}',
                               content_type="application/json")
        httpretty.register_uri(httpretty.GET,
                               settings.NSLORD_PDNS_API + '/zones/' + name + './cryptokeys',
                               body='[]',
                               content_type="application/json")
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + name + './notify', status=200)

        url = reverse('domain-list')
        self.client.post(url, {'name': name})

        self.assertEqual(httpretty.httpretty.latest_requests[-4].method, 'POST')
        self.assertTrue(name in httpretty.httpretty.latest_requests[-4].parsed_body)
        self.assertTrue('ns1.desec.io' in httpretty.httpretty.latest_requests[-4].parsed_body)
        self.assertEqual(httpretty.httpretty.latest_requests[-3].method, 'PUT')
        self.assertEqual(httpretty.httpretty.latest_requests[-2].method, 'GET')
        self.assertTrue((settings.NSLORD_PDNS_API + '/zones/' + name + '.').endswith(httpretty.httpretty.latest_requests[-2].path))

    def testDomainDetailURL(self):
        url = reverse('domain-detail', args=(self.ownedDomains[1].name,))
        self.assertTrue("/" + self.ownedDomains[1].name in url)

    def testRollback(self):
        name = utils.generateDomainname()

        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones', body="some error", status=500)

        url = reverse('domain-list')
        data = {'name': name}
        self.client.post(url, data)

        self.assertFalse(Domain.objects.filter(name=name).exists())


class AuthenticatedDynDomainTests(APITestCase):
    def setUp(self):
        if not hasattr(self, 'owner'):
            self.owner = utils.createUser(dyn=True)
            self.ownedDomains = [utils.createDomain(self.owner, dyn=True), utils.createDomain(self.owner, dyn=True)]
            self.otherDomains = [utils.createDomain(), utils.createDomain()]
            self.token = utils.createToken(user=self.owner)
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

    def tearDown(self):
        httpretty.reset()
        httpretty.disable()

    def testCanDeleteOwnedDynDomain(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.DELETE, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.DELETE, settings.NSMASTER_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')

        url = reverse('domain-detail', args=(self.ownedDomains[1].name,))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # FIXME In this testing scenario, the parent domain dedyn.io does not
        # have the proper NS and DS records set up, so we cannot test their
        # deletion.

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

        url = reverse('domain-detail', args=(self.otherDomains[1].name,))
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

        # FIXME We also need to test that proper NS and DS records are set up
        # in the parent zone dedyn.io.  Because this relies on the cron hook,
        # it is currently not covered.

    def testCantPostNonDynDomains(self):
        url = reverse('domain-list')

        data = {'name': utils.generateDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'domain-illformed')

        data = {'name': 'very.long.domain.' + utils.generateDynDomainname()}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'domain-illformed')


    def testLimitDynDomains(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, settings.NSLORD_PDNS_API + '/zones')

        outboxlen = len(mail.outbox)

        url = reverse('domain-list')
        for i in range(settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT-2):
            name = utils.generateDynDomainname()

            httpretty.register_uri(httpretty.GET,
                                   settings.NSLORD_PDNS_API + '/zones/' + name + '.',
                                   body='{"rrsets": []}',
                                   content_type="application/json")
            httpretty.register_uri(httpretty.GET,
                                   settings.NSLORD_PDNS_API + '/zones/' + name + './cryptokeys',
                                   body='[]',
                                   content_type="application/json")
            httpretty.register_uri(httpretty.PUT,
                                   settings.NSLORD_PDNS_API + '/zones/' + name + './notify',
                                   status=200)

            response = self.client.post(url, {'name': name})
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
