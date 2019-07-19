import json

from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from psl_dns.exceptions import UnsupportedRule
from rest_framework import status

from desecapi.models import Domain
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.tests.base import DesecTestCase, DomainOwnerTestCase, LockedDomainOwnerTestCase


class UnauthenticatedDomainTests(DesecTestCase):

    def test_unauthorized_access(self):
        for url in [
            self.reverse('v1:domain-list'),
            self.reverse('v1:domain-detail', name='example.com.')
        ]:
            for method in [self.client.put, self.client.delete]:
                self.assertStatus(method(url), status.HTTP_401_UNAUTHORIZED)


class DomainOwnerTestCase1(DomainOwnerTestCase):

    def test_name_validity(self):
        for name in [
            'FOO.BAR.com',
            'tEst.dedyn.io',
            'ORG',
            '--BLAH.example.com',
            '_ASDF.jp',
        ]:
            with self.assertRaises(ValidationError):
                Domain(owner=self.owner, name=name).save()
        for name in [
            '_example.com', '_.example.com',
            '-dedyn.io', '--dedyn.io', '-.dedyn123.io',
            'foobar.io', 'exam_ple.com',
        ]:
            with self.assertPdnsRequests(
                self.requests_desec_domain_creation(name=name)[:-1]  # no serializer, no cryptokeys API call
            ), PDNSChangeTracker():
                Domain(owner=self.owner, name=name).save()

    def test_list_domains(self):
        with self.assertPdnsNoRequestsBut(self.request_pdns_zone_retrieve_crypto_keys()):
            response = self.client.get(self.reverse('v1:domain-list'))
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(len(response.data), self.NUM_OWNED_DOMAINS)
            for i in range(self.NUM_OWNED_DOMAINS):
                self.assertEqual(response.data[i]['name'], self.my_domains[i].name)

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)

        with self.assertPdnsRequests(self.requests_desec_domain_deletion()):
            response = self.client.delete(url)
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)
            self.assertFalse(Domain.objects.filter(pk=self.my_domain.pk).exists())

        response = self.client.get(url)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_delete_other_domain(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        response = self.client.delete(url)
        self.assertStatus(response, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Domain.objects.filter(pk=self.other_domain.pk).exists())

    def test_retrieve_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(
            self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)
        ):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data['name'], self.my_domain.name)
            self.assertTrue(isinstance(response.data['keys'], list))

    def test_retrieve_other_domains(self):
        for domain in self.other_domains:
            response = self.client.get(self.reverse('v1:domain-detail', name=domain.name))
            self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_update_my_domain_name(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)

        response.data['name'] = self.random_domain_name()
        response = self.client.put(url, response.data, format='json')
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)

        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data['name'], self.my_domain.name)

    def test_update_my_domain_immutable(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)

        created = response.data['created']
        keys = response.data['keys']
        published = response.data['published']

        response.data['created'] = '2019-08-07T18:34:39.249227Z'
        response.data['published'] = '2019-08-07T18:34:39.249227Z'
        response.data['keys'] = [{'dnskey': '257 3 13 badefefe'}]

        self.assertNotEqual(response.data['created'], created)
        self.assertNotEqual(response.data['published'], published)
        self.assertNotEqual(response.data['keys'], keys)

        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.put(url, response.data, format='json')
        self.assertStatus(response, status.HTTP_200_OK)

        self.assertEqual(response.data['created'], created)
        self.assertEqual(response.data['published'], published)
        self.assertEqual(response.data['keys'], keys)

    def test_update_other_domains(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        response = self.client.put(url, {}, format='json')
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_create_domains(self):
        self.owner.limit_domains = 100
        self.owner.save()
        for name in [
            '0.8.0.0.0.1.c.a.2.4.6.0.c.e.e.d.4.4.0.1.a.0.1.0.8.f.4.0.1.0.a.2.ip6.arpa',
            'very.long.domain.name.' + self.random_domain_name(),
            self.random_domain_name(),
            'very.long.domain.name.with_underscore.' + self.random_domain_name(),
        ]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
                response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)
                self.assertEqual(len(mail.outbox), 0)

            with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name)):
                self.assertStatus(
                    self.client.get(self.reverse('v1:domain-detail', name=name), {'name': name}),
                    status.HTTP_200_OK
                )
                response = self.client.get_rr_sets(name, type='NS', subname='')
                self.assertStatus(response, status.HTTP_200_OK)
                self.assertContainsRRSets(response.data, [dict(subname='', records=settings.DEFAULT_NS, type='NS')])

    def test_create_api_known_domain(self):
        url = self.reverse('v1:domain-list')

        for name in [
            self.random_domain_name(),
            'www.' + self.my_domain.name,
        ]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
                response = self.client.post(url, {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)
            response = self.client.post(url, {'name': name})
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_create_pdns_known_domain(self):
        url = self.reverse('v1:domain-list')
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.request_pdns_zone_create_already_exists(existing_domains=[name])):
            response = self.client.post(url, {'name': name})
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_create_domain_with_whitespace(self):
        for name in [
            ' ' + self.random_domain_name(),
            self.random_domain_name() + '  ',
        ]:
            self.assertResponse(
                self.client.post(self.reverse('v1:domain-list'), {'name': name}),
                status.HTTP_400_BAD_REQUEST,
                {'name': ['Domain name malformed.']},
            )

    def test_create_public_suffixes(self):
        for name in self.PUBLIC_SUFFIXES:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data['code'], 'domain-unavailable')

    def test_create_domain_under_public_suffix_with_private_parent(self):
        name = 'amazonaws.com'
        with self.assertPdnsRequests(self.requests_desec_domain_creation(name)[:-1]), PDNSChangeTracker():
            Domain(owner=self.create_user(), name=name).save()
            self.assertTrue(Domain.objects.filter(name=name).exists())

        # If amazonaws.com is owned by another user, we cannot register test.s4.amazonaws.com
        name = 'test.s4.amazonaws.com'
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertStatus(response, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'domain-unavailable')

        # s3.amazonaws.com is a public suffix. Therefore, test.s3.amazonaws.com can be
        # registered even if the parent zone amazonaws.com is owned by another user
        name = 'test.s3.amazonaws.com'
        psl_cm = self.get_psl_context_manager('s3.amazonaws.com')
        with psl_cm, self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_201_CREATED)

    def test_create_domain_under_unsupported_public_suffix_rule(self):
        # Show lenience if the PSL library produces an UnsupportedRule exception
        name = 'unsupported.wildcard.test'
        psl_cm = self.get_psl_context_manager(UnsupportedRule)
        with psl_cm, self.assertPdnsRequests():
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_create_domain_policy(self):
        name = '*.' + self.random_domain_name()
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("Domain name malformed." in response.data['name'][0])

    def test_create_domain_other_parent(self):
        name = 'something.' + self.other_domain.name
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertStatus(response, status.HTTP_409_CONFLICT)
        self.assertIn('domain name is unavailable.', response.data['detail'])

    def test_create_domain_atomicity(self):
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.request_pdns_zone_create_422()):
            self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertFalse(Domain.objects.filter(name=name).exists())

    def test_create_domain_punycode(self):
        names = ['公司.cn', 'aéroport.ci']
        for name in names:
            self.assertStatus(
                self.client.post(self.reverse('v1:domain-list'), {'name': name}),
                status.HTTP_400_BAD_REQUEST
            )

        for name in [n.encode('idna').decode('ascii') for n in names]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name=name)):
                self.assertStatus(
                    self.client.post(self.reverse('v1:domain-list'), {'name': name}),
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
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(len(mail.outbox), 0)

    def test_domain_minimum_ttl(self):
        url = self.reverse('v1:domain-list')
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.requests_desec_domain_creation(name=name)):
            response = self.client.post(url, {'name': name})
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data['minimum_ttl'], settings.MINIMUM_TTL_DEFAULT)


class LockedDomainOwnerTestCase1(LockedDomainOwnerTestCase):

    def test_create_domains(self):
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
            self.assertStatus(
                self.client.post(self.reverse('v1:domain-list'), {'name': name}),
                status.HTTP_201_CREATED
            )

    def test_update_domains(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        name = self.random_domain_name()

        for method in [self.client.patch, self.client.put]:
            with PDNSChangeTracker():
                response = method(url, {'name': name})
                self.assertStatus(response, status.HTTP_400_BAD_REQUEST)  # TODO fix docs, consider to change code

        with self.assertPdnsRequests(self.requests_desec_domain_deletion(name=self.my_domain.name)):
            response = self.client.delete(url)
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)

    def test_create_rr_sets(self):
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post_rr_set(self.my_domain.name, **data)
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)

    def test_update_rr_sets(self):
        type_ = 'A'
        for subname in ['', '*', 'asdf', 'asdf.adsf.asdf']:
            data = {'records': ['1.2.3.4'], 'ttl': 60}
            response = self.client.put_rr_set(self.my_domain.name, subname, type_, data)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            for patch_request in [
                {'records': ['1.2.3.4'], 'ttl': 60},
                {'records': [], 'ttl': 60},
                {'records': []},
                {'ttl': 60},
                {},
            ]:
                response = self.client.patch_rr_set(self.my_domain.name, subname, type_, patch_request)
                self.assertStatus(response, status.HTTP_403_FORBIDDEN)

            # Try DELETE
            response = self.client.delete_rr_set(self.my_domain.name, subname, type_)
            self.assertStatus(response, status.HTTP_403_FORBIDDEN)


class AutoDelegationDomainOwnerTests(DomainOwnerTestCase):
    DYN = True

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(
            self.requests_desec_domain_deletion_auto_delegation(name=self.my_domain.name)
        ):
            response = self.client.delete(url)
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url)
        self.assertStatus(response, status.HTTP_404_NOT_FOUND)

    def test_delete_other_domains(self):
        url = self.reverse('v1:domain-detail', name=self.other_domain.name)
        with self.assertPdnsRequests():
            response = self.client.delete(url)
            self.assertStatus(response, status.HTTP_204_NO_CONTENT)
            self.assertTrue(Domain.objects.filter(pk=self.other_domain.pk).exists())

    def test_create_auto_delegated_domains(self):
        for i, suffix in enumerate(self.AUTO_DELEGATION_DOMAINS):
            name = self.random_domain_name(suffix)
            with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name=name)):
                response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)
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
            self.assertStatus(response, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data['code'], 'domain-illformed')

    def test_domain_limit(self):
        url = self.reverse('v1:domain-list')
        user_quota = settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT - self.NUM_OWNED_DOMAINS

        for i in range(user_quota):
            name = self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)
            with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
                response = self.client.post(url, {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)
                self.assertEqual(len(mail.outbox), i + 1)

        response = self.client.post(url, {'name': self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)})
        self.assertStatus(response, status.HTTP_403_FORBIDDEN)
        self.assertEqual(len(mail.outbox), user_quota)

    def test_domain_minimum_ttl(self):
        url = self.reverse('v1:domain-list')
        name = self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)
        with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
            response = self.client.post(url, {'name': name})
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data['minimum_ttl'], 60)


class LockedAutoDelegationDomainOwnerTests(LockedDomainOwnerTestCase):
    DYN = True

    def test_create_domain(self):
        name = self.random_domain_name(suffix=self.AUTO_DELEGATION_DOMAINS)
        with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
            self.assertStatus(
                self.client.post(self.reverse('v1:domain-list'), {'name': name}),
                status.HTTP_201_CREATED
            )

    def test_create_rrset(self):
        self.assertStatus(
            self.client.post_rr_set(self.my_domain.name, type='A', records=['1.1.1.1']),
            status.HTTP_403_FORBIDDEN
        )
