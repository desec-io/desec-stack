from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from utils import utils
from django.db import transaction
from desecapi.models import Domain


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
            transaction.commit()
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
