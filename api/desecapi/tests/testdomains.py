import random
import json

from django.core import mail
from django.conf import settings
from rest_framework import status

from desecapi.exceptions import PdnsException
from desecapi.tests.base import DesecTestCase, DomainOwnerTestCase, LockedDomainOwnerTestCase
from desecapi.models import Domain


class UnauthenticatedDomainTests(DesecTestCase):

    def test_unauthorized_access(self):
        for url in [
            self.reverse('v1:domain-list'),
            self.reverse('v1:domain-detail', name='example.com.')
        ]:
            for method in [self.client.put, self.client.delete]:
                self.assertEqual(method(url).status_code, status.HTTP_401_UNAUTHORIZED)


class DomainOwnerTestCase1(DomainOwnerTestCase):

    def test_list_domains(self):
        with self.assertPdnsNoRequestsBut(self.request_pdns_zone_retrieve_crypto_keys()):
            response = self.client.get(self.reverse('v1:domain-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.NUM_OWNED_DOMAINS)
        for i in range(self.NUM_OWNED_DOMAINS):
            self.assertEqual(response.data[i]['name'], self.my_domains[i].name)

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)

        with self.assertPdnsRequests(self.requests_desec_domain_deletion()):
            response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Domain.objects.filter(pk=self.my_domain.pk).exists())

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_other_domain(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Domain.objects.filter(pk=self.other_domain.pk).exists())

    def test_retrieve_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.my_domain.name)
        self.assertTrue(isinstance(response.data['keys'], list))

    def test_retrieve_other_domains(self):
        for domain in self.other_domains:
            response = self.client.get(self.reverse('v1:domain-detail', name=domain.name))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_my_domain_name(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)

        response.data['name'] = self.random_domain_name()
        response = self.client.put(url, json.dumps(response.data), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.my_domain.name)

    def test_update_other_domains(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        response = self.client.put(url, json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_domains(self):
        for name in [
            '0.8.0.0.0.1.c.a.2.4.6.0.c.e.e.d.4.4.0.1.a.0.1.0.8.f.4.0.1.0.a.2.ip6.arpa',
            'very.long.domain.name.' + self.random_domain_name(),
            self.random_domain_name()
        ]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
                response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(len(mail.outbox), 0)

    def test_create_api_known_domain(self):
        url = self.reverse('v1:domain-list')

        for name in [
            self.random_domain_name(),
            'www.' + self.my_domain.name,
        ]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
                response = self.client.post(url, {'name': name})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            response = self.client.post(url, {'name': name})
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_pdns_known_domain(self):
        url = self.reverse('v1:domain-list')
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.request_pdns_zone_create_already_exists(existing_domains=[name])):
            response = self.client.post(url, {'name': name})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_domain_policy(self):
        name = '*.' + self.random_domain_name()
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("does not match the required pattern." in response.data['name'][0])

    def test_create_domain_atomicity(self):
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.request_pdns_zone_create_422()):
            self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertFalse(Domain.objects.filter(name=name).exists())

    def test_create_domain_punycode(self):
        names = ['公司.cn', 'aéroport.ci']
        for name in names:
            self.assertEqual(
                self.client.post(self.reverse('v1:domain-list'), {'name': name}).status_code,
                status.HTTP_400_BAD_REQUEST
            )

        for name in [n.encode('idna').decode('ascii') for n in names]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name=name)):
                self.assertEqual(
                    self.client.post(self.reverse('v1:domain-list'), {'name': name}).status_code,
                    status.HTTP_201_CREATED
                )

    def test_create_domain_name_validation(self):
        for name in [
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
        ]:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(len(mail.outbox), 0)


class LockedDomainOwnerTestCase1(LockedDomainOwnerTestCase):

    def test_create_domains(self):
        self.assertEqual(
            self.client.post(self.reverse('v1:domain-list'), {'name': self.random_domain_name()}).status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_update_domains(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        data = {'name': self.random_domain_name()}

        for method in [self.client.patch, self.client.put]:
            response = method(url, data)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rr_sets(self):
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post_rr_set(self.my_domain.name, **data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_rr_sets(self):
        type_ = 'A'
        for subname in ['', '*', 'asdf', 'asdf.adsf.asdf']:
            data = {'records': ['1.2.3.4'], 'ttl': 60}
            response = self.client.put_rr_set(self.my_domain.name, subname, type_, **data)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            for patch_request in [
                {'records': ['1.2.3.4'], 'ttl': 60},
                {'records': [], 'ttl': 60},
                {'records': []},
                {'ttl': 60},
                {},
            ]:
                response = self.client.patch_rr_set(self.my_domain.name, subname, type_, **patch_request)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

            # Try DELETE
            response = self.client.delete_rr_set(self.my_domain.name, subname, type_)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AutoDelegationDomainOwnerTests(DomainOwnerTestCase):
    DYN = True

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(
            self.requests_desec_domain_deletion_auto_delegation(name=self.my_domain.name)
        ):
            response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_other_domains(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        with self.assertPdnsRequests():
            response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Domain.objects.filter(pk=self.other_domain.pk).exists())

    def test_create_auto_delegated_domains(self):
        for i, suffix in enumerate(self.AUTO_DELEGATION_DOMAINS):
            name = self.random_domain_name(suffix)
            with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name=name)):
                response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(len(mail.outbox), i + 1)
            email = str(mail.outbox[0].message())
            self.assertTrue(name in email)
            self.assertTrue(self.token.key in email)
            self.assertFalse(self.user.plain_password in email)

    def test_create_regular_domains(self):
        for name in [
            self.random_domain_name(),
            'very.long.domain.' + self.random_domain_name()
        ]:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data['code'], 'domain-illformed')

    def test_domain_limit(self):
        url = self.reverse('v1:domain-list')
        user_quota = settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT - self.NUM_OWNED_DOMAINS

        for i in range(user_quota):
            name = self.random_domain_name(random.choice(self.AUTO_DELEGATION_DOMAINS))
            with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
                response = self.client.post(url, {'name': name})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(len(mail.outbox), i + 1)

        response = self.client.post(url, {'name': self.random_domain_name(random.choice(self.AUTO_DELEGATION_DOMAINS))})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(len(mail.outbox), user_quota)


class LockedAutoDelegationDomainOwnerTests(LockedDomainOwnerTestCase):
    DYN = True

    def test_unlock_user(self):
        name = self.random_domain_name(self.AUTO_DELEGATION_DOMAINS[0])

        # Users should be able to create domains under auto delegated domains even when locked
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=name)):
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        with self.assertPdnsRequests(self.request_pdns_zone_create_already_exists(existing_domains=[name])),\
             self.assertRaises(PdnsException) as cm:
            self.owner.unlock()

        self.assertEqual(str(cm.exception), "Domain '" + name + ".' already exists")

        # See what happens upon unlock if this domain is new to pdns
        with self.assertPdnsRequests(
                self.requests_desec_domain_creation_auto_delegation(name=name)[:-1]  # No crypto keys retrieved
        ):
            self.owner.unlock()
