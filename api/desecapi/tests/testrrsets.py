from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
import httpretty
from django.conf import settings
import json
from django.core.management import call_command
from django.utils import timezone


class UnauthenticatedDomainTests(APITestCase):
    def testExpectUnauthorizedOnGet(self):
        url = reverse('rrsets', args=('example.com',))
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnPost(self):
        url = reverse('rrsets', args=('example.com',))
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnPut(self):
        url = reverse('rrsets', args=('example.com',))
        response = self.client.put(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def testExpectUnauthorizedOnDelete(self):
        url = reverse('rrsets', args=('example.com',))
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedRRsetTests(APITestCase):
    dead_types = ('ALIAS', 'DNAME')
    restricted_types = ('SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM')

    def setUp(self):
        httpretty.reset()
        httpretty.disable()

        if not hasattr(self, 'owner'):
            self.owner = utils.createUser()
            self.ownedDomains = [utils.createDomain(self.owner), utils.createDomain(self.owner)]
            self.token = utils.createToken(user=self.owner)
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

            self.otherOwner = utils.createUser()
            self.otherDomains = [utils.createDomain(self.otherOwner), utils.createDomain()]
            self.otherToken = utils.createToken(user=self.otherOwner)

    def testCanGetOwnRRsets(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) # don't forget NS RRset

    def testCantGetForeignRRsets(self):
        url = reverse('rrsets', args=(self.otherDomains[1].name,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanGetOwnRRsetsEmptySubname(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        response = self.client.get(url + '?subname=')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1) # don't forget NS RRset

    def testCanGetOwnRRsetsFromSubname(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))

        data = {'records': ['1.2.3.4'], 'ttl': 120, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['2.2.3.4'], 'ttl': 120, 'type': 'A', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['"test"'], 'ttl': 120, 'type': 'TXT', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3 + 1) # don't forget NS RRset

        response = self.client.get(url + '?subname=test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def testCantGetForeignRRsetsFromSubname(self):
        url = reverse('rrsets', args=(self.otherDomains[1].name,))
        response = self.client.get(url + '?subname=test')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanGetOwnRRsetsFromType(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))

        data = {'records': ['1.2.3.4'], 'ttl': 120, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['2.2.3.4'], 'ttl': 120, 'type': 'A', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['"test"'], 'ttl': 120, 'type': 'TXT', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3 + 1) # don't forget NS RRset

        response = self.client.get(url + '?type=A')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def testCantGetForeignRRsetsFromType(self):
        url = reverse('rrsets', args=(self.otherDomains[1].name,))
        response = self.client.get(url + '?test=A')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanPostOwnRRsets(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1 + 1) # don't forget NS RRset

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')

        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['desec.io.'], 'ttl': 900, 'type': 'PTR'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def testCantPostEmptyRRset(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': [], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testCantPostDeadTypes(self):
        for type_ in self.dead_types:
            url = reverse('rrsets', args=(self.ownedDomains[1].name,))
            data = {'records': ['www.example.com.'], 'ttl': 60, 'type': type_}
            response = self.client.post(url, json.dumps(data), content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testCantPostRestrictedTypes(self):
        for type_ in self.restricted_types:
            url = reverse('rrsets', args=(self.ownedDomains[1].name,))
            data = {'records': ['ns1.desec.io. peter.desec.io. 2584 10800 3600 604800 60'], 'ttl': 60, 'type': type_}
            response = self.client.post(url, json.dumps(data), content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testCantPostForeignRRsets(self):
        url = reverse('rrsets', args=(self.otherDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantPostTwiceRRsets(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['3.2.2.1'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def testCantPostFaultyRRsets(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))

        # New record without a value is a syntactical error --> 400
        data = {'records': [], 'ttl': 60, 'type': 'TXT'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Lower-case type is a syntactical error --> 400
        data = {'records': ['123456'], 'ttl': 60, 'type': 'txt'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Unknown type is a semantical error --> 422
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['123456'], 'ttl': 60, 'type': 'AA'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def testCanGetOwnRRset(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')
        self.assertEqual(response.data['ttl'], 60)

    def testCanGetOwnRRsetApex(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset@', args=(self.ownedDomains[1].name, '@', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')
        self.assertEqual(response.data['ttl'], 60)

    def testCantGetRestrictedTypes(self):
        for type_ in self.restricted_types:
            url = reverse('rrsets', args=(self.ownedDomains[1].name,))
            response = self.client.get(url + '?type=%s' % type_)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            url = reverse('rrset', args=(self.ownedDomains[1].name, '', type_,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def testCantGetForeignRRset(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.otherToken)
        url = reverse('rrsets', args=(self.otherDomains[0].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('rrset', args=(self.otherDomains[0].name, '', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanGetOwnRRsetWithSubname(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))

        data = {'records': ['1.2.3.4'], 'ttl': 120, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['2.2.3.4'], 'ttl': 120, 'type': 'A', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {'records': ['"test"'], 'ttl': 120, 'type': 'TXT', 'subname': 'test'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3 + 1) # don't forget NS RRset

        url = reverse('rrset', args=(self.ownedDomains[1].name, 'test', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '2.2.3.4')
        self.assertEqual(response.data['ttl'], 120)
        self.assertEqual(response.data['name'], 'test.' + self.ownedDomains[1].name + '.')

    def testCanGetOwnRRsetWithWildcard(self):
        for subname in ('*', '*.foobar'):
            url = reverse('rrsets', args=(self.ownedDomains[1].name,))

            data = {'records': ['"barfoo"'], 'ttl': 120, 'type': 'TXT', 'subname': subname}
            response = self.client.post(url, json.dumps(data), content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            response1 = self.client.get(url + '?subname=' + subname)
            self.assertEqual(response1.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data[0]['records'][0], '"barfoo"')
            self.assertEqual(response1.data[0]['ttl'], 120)
            self.assertEqual(response1.data[0]['name'], subname + '.' + self.ownedDomains[1].name + '.')

            url = reverse('rrset', args=(self.ownedDomains[1].name, subname, 'TXT',))
            response2 = self.client.get(url)
            self.assertEqual(response2.data, response1.data[0])

    def testCanPutOwnRRset(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))

        data = {'records': ['2.2.3.4'], 'ttl': 30}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '2.2.3.4')
        self.assertEqual(response.data['ttl'], 30)

        data = {'records': ['3.2.3.4']}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'ttl': 37}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testCanPutOwnRRsetApex(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset@', args=(self.ownedDomains[1].name, '@', 'A',))

        data = {'records': ['2.2.3.4'], 'ttl': 30}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '2.2.3.4')
        self.assertEqual(response.data['ttl'], 30)

        data = {'records': ['3.2.3.4']}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {'ttl': 37}
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def testCanPatchOwnRRset(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Change records and TTL
        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        data = {'records': ['3.2.3.4'], 'ttl': 32}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '3.2.3.4')
        self.assertEqual(response.data['ttl'], 32)

        # Change records alone
        data = {'records': ['5.2.3.4']}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 32)

        # Change TTL alone
        data = {'ttl': 37}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 37)

        # Change nothing
        data = {}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 37)

    def testCanPatchOwnRRsetApex(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Change records and TTL
        url = reverse('rrset@', args=(self.ownedDomains[1].name, '@', 'A',))
        data = {'records': ['3.2.3.4'], 'ttl': 32}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '3.2.3.4')
        self.assertEqual(response.data['ttl'], 32)

        # Change records alone
        data = {'records': ['5.2.3.4']}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 32)

        # Change TTL alone
        data = {'ttl': 37}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 37)

        # Change nothing
        data = {}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '5.2.3.4')
        self.assertEqual(response.data['ttl'], 37)

    def testCantChangeForeignRRset(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.otherToken)
        url = reverse('rrsets', args=(self.otherDomains[0].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('rrset', args=(self.otherDomains[0].name, '', 'A',))
        data = {'records': ['3.2.3.4'], 'ttl': 30, 'type': 'A'}

        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantChangeForeignRRsetApex(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.otherToken)
        url = reverse('rrsets', args=(self.otherDomains[0].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('rrset@', args=(self.otherDomains[0].name, '@', 'A',))
        data = {'records': ['3.2.3.4'], 'ttl': 30, 'type': 'A'}

        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantChangeEssentialProperties(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A', 'subname': 'test1'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Changing the subname is expected to cause an error
        url = reverse('rrset', args=(self.ownedDomains[1].name, 'test1', 'A',))
        data = {'records': ['3.2.3.4'], 'ttl': 120, 'subname': 'test2'}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Changing the type is expected to cause an error
        data = {'records': ['3.2.3.4'], 'ttl': 120, 'type': 'TXT'}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.put(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check that nothing changed
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')
        self.assertEqual(response.data['ttl'], 60)
        self.assertEqual(response.data['name'], 'test1.' + self.ownedDomains[1].name + '.')
        self.assertEqual(response.data['subname'], 'test1')
        self.assertEqual(response.data['type'], 'A')

        # This is expected to work, but the fields are ignored
        data = {'records': ['3.2.3.4'], 'name': 'example.com.', 'domain': 'example.com'}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '3.2.3.4')
        self.assertEqual(response.data['domain'], self.ownedDomains[1].name)
        self.assertEqual(response.data['name'], 'test1.' + self.ownedDomains[1].name + '.')

    def testCanDeleteOwnRRset(self):
        # Try PATCH with empty records
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        data = {'records': []}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Try DELETE
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCanDeleteOwnRRsetApex(self):
        # Try PATCH with empty records
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset@', args=(self.ownedDomains[1].name, '@', 'A',))
        data = {'records': []}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Try DELETE
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset@', args=(self.ownedDomains[1].name, '@', 'A',))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def testCantDeleteForeignRRset(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.otherToken)
        url = reverse('rrsets', args=(self.otherDomains[0].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)
        url = reverse('rrset', args=(self.otherDomains[0].name, '', 'A',))

        # Try PATCH with empty records
        data = {'records': []}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Try DELETE
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Make sure it actually is still there
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.otherToken)
        url = reverse('rrset@', args=(self.otherDomains[0].name, '@', 'A',))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')

    def testCantDeleteOwnRRsetWhileAccountIsLocked(self):
        self.owner.locked = timezone.now()
        self.owner.save()

        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))

        # Try PATCH with empty records
        data = {'records': []}
        response = self.client.patch(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try DELETE
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def testPostCausesPdnsAPICall(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + './notify')

        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        self.client.post(url, json.dumps(data), content_type='application/json')

        result = json.loads(httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertEqual(result['rrsets'][0]['name'], self.ownedDomains[1].name + '.')
        self.assertEqual(result['rrsets'][0]['records'][0]['content'], '1.2.3.4')
        self.assertEqual(httpretty.last_request().method, 'PUT')

    def testDeleteCausesPdnsAPICall(self):
        httpretty.enable()
        httpretty.register_uri(httpretty.PATCH, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + '.')
        httpretty.register_uri(httpretty.PUT, settings.NSLORD_PDNS_API + '/zones/' + self.ownedDomains[1].name + './notify')

        # Create record, should cause a pdns PATCH request and a notify
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        self.client.post(url, json.dumps(data), content_type='application/json')

        # Delete record, should cause a pdns PATCH request and a notify
        url = reverse('rrset', args=(self.ownedDomains[1].name, '', 'A',))
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Check pdns requests from creation
        result = json.loads(httpretty.httpretty.latest_requests[-4].parsed_body)
        self.assertEqual(result['rrsets'][0]['name'], self.ownedDomains[1].name + '.')
        self.assertEqual(result['rrsets'][0]['records'][0]['content'], '1.2.3.4')
        self.assertEqual(httpretty.httpretty.latest_requests[-3].method, 'PUT')

        # Check pdns requests from deletion
        result = json.loads(httpretty.httpretty.latest_requests[-2].parsed_body)
        self.assertEqual(result['rrsets'][0]['name'], self.ownedDomains[1].name + '.')
        self.assertEqual(result['rrsets'][0]['records'], [])
        self.assertEqual(httpretty.httpretty.latest_requests[-1].method, 'PUT')

    def testImportRRsets(self):
        url = reverse('rrsets', args=(self.ownedDomains[1].name,))
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Not checking anything here; errors will raise an exception
        call_command('sync-from-pdns', self.ownedDomains[1].name)
