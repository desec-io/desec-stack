from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from psl_dns.exceptions import UnsupportedRule
from rest_framework import status

from desecapi.models import Domain
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.tests.base import DesecTestCase, DomainOwnerTestCase, PublicSuffixMockMixin


class IsRegistrableTestCase(DesecTestCase, PublicSuffixMockMixin):
    """ Tests which domains can be registered by whom, depending on domain ownership and public suffix
    configuration. Note that we use "global public suffix" to refer to public suffixes which appear on the
    Internet-wide Public Suffix List (accessible, e.g., via psl_dns), and "local public suffix" to public
    suffixes which are configured in the local Django settings.LOCAL_PUBLIC_SUFFIXES. Consequently, a
    public suffix can be just local, just global, or both. """

    def mock(self, global_public_suffixes, local_public_suffixes):
        self.setUpMockPatch()
        test_case = self

        class _MockSuffixLists:

            settings_mocker = None
            psl_mocker = None

            def __enter__(self):
                self.settings_mocker = test_case.settings(LOCAL_PUBLIC_SUFFIXES=local_public_suffixes)
                self.settings_mocker.__enter__()
                self.psl_mocker = test_case.get_psl_context_manager(global_public_suffixes)
                self.psl_mocker.__enter__()

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type or exc_val or exc_tb:
                    raise exc_val
                self.settings_mocker.__exit__(None, None, None)
                self.psl_mocker.__exit__(None, None, None)

        return _MockSuffixLists()

    def assertRegistrable(self, domain_name, user=None):
        """ Raises if the given user (fresh if None) cannot register the given domain name. """
        self.assertTrue(Domain(name=domain_name, owner=user or self.create_user()).is_registrable(),
                        f'{domain_name} was expected to be registrable for {user or "a new user"}, but wasn\'t.')

    def assertNotRegistrable(self, domain_name, user=None):
        """ Raises if the given user (fresh if None) can register the given domain name. """
        self.assertFalse(Domain(name=domain_name, owner=user or self.create_user()).is_registrable(),
                         f'{domain_name} was expected to be not registrable for {user or "a new user"}, but was.')

    def test_cant_register_global_non_local_public_suffix(self):
        with self.mock(
            global_public_suffixes=['com', 'de', 'xxx', 'com.uk'],
            local_public_suffixes=['something.else'],
        ):
            self.assertNotRegistrable('tld')
            self.assertNotRegistrable('xxx')
            self.assertNotRegistrable('com.uk')
            self.assertRegistrable('something.else')

    def test_can_register_local_public_suffix(self):
        # Avoid side effects from existing domains (such as dedyn.io.example.com being covered by the .com test below)
        # Existing domains depend on environment variables. We may want to make the tests "stand-alone" at some point.
        Domain.objects.filter(name__in=self.AUTO_DELEGATION_DOMAINS).delete()

        local_public_suffixes = ['something.else', 'our.public.suffix', 'com', 'com.uk']
        with self.mock(
            global_public_suffixes=['com', 'de', 'xxx', 'com.uk'],
            local_public_suffixes=local_public_suffixes,
        ):
            for local_public_suffix in local_public_suffixes:
                self.assertRegistrable(local_public_suffix)
            self.assertRegistrable('foo.bar.com')

    def test_cant_register_reserved_children_of_public_suffix(self):
        global_public_suffixes = ['global.public.suffix']
        local_public_suffixes = ['local.public.suffix']
        reserved_labels = ['_acme-challenge', '_tcp', '_foobar', 'autodiscover', 'autoconfig']
        with self.mock(
            global_public_suffixes=global_public_suffixes,
            local_public_suffixes=local_public_suffixes,
        ):
            for suffix in local_public_suffixes + global_public_suffixes:
                for label in reserved_labels:
                    self.assertNotRegistrable(f'{label}.{suffix}')
                    self.assertRegistrable(f'{label}.sub.{suffix}')

    def test_cant_register_descendants_of_children_of_public_suffixes(self):
        with self.mock(
            global_public_suffixes={'public.suffix'},
            local_public_suffixes={'public.suffix'},
        ):
            # let A own a.public.suffix
            user_a = self.create_user()
            self.assertRegistrable('a.public.suffix', user_a)
            self.create_domain(owner=user_a, name='a.public.suffix')
            # user B shall not register b.a.public.suffix, but A may
            user_b = self.create_user()
            self.assertNotRegistrable('b.a.public.suffix', user_b)
            self.assertRegistrable('b.a.public.suffix', user_a)

    def test_cant_register_ancestors_of_registered_domains(self):
        user_a = self.create_user()
        user_b = self.create_user()

        with self.mock(
            global_public_suffixes={'public.suffix'},
            local_public_suffixes={'public.suffix'},
        ):
            # let A own c.b.a.public.suffix
            self.assertRegistrable('c.b.a.public.suffix', user_a)
            self.create_domain(owner=user_a, name='c.b.a.public.suffix')

            # user B shall not register b.a.public.suffix or a.public.suffix, but A may
            self.assertNotRegistrable('b.a.public.suffix', user_b)
            self.assertNotRegistrable('a.public.suffix', user_b)
            self.assertRegistrable('b.a.public.suffix', user_a)
            self.assertRegistrable('a.public.suffix', user_a)

            # let A own _acme-challenge.foobar.public.suffix
            self.assertRegistrable('_acme-challenge.foobar.public.suffix', user_a)
            self.create_domain(owner=user_a, name='_acme-challenge.foobar.public.suffix')

            # user B shall not register foobar.public.suffix, but A may
            user_b = self.create_user()
            self.assertNotRegistrable('foobar.public.suffix', user_b)
            self.assertRegistrable('foobar.public.suffix', user_a)

    def test_can_register_public_suffixes_under_private_domains(self):
        with self.mock(
            global_public_suffixes={'public.suffix'},
            local_public_suffixes={'another.public.suffix.private.public.suffix', 'public.suffix'},
        ):
            # let A own public.suffix
            user_a = self.create_user()
            self.assertRegistrable('public.suffix', user_a)
            self.create_domain(owner=user_a, name='public.suffix')
            # user B may register private.public.suffix
            user_b = self.create_user()
            self.assertRegistrable('private.public.suffix', user_b)
            self.create_domain(owner=user_b, name='private.public.suffix')
            # user C may register b.another.public.suffix.private.public.suffix,
            # or long.silly.prefix.another.public.suffix.private.public.suffix,
            # but not b.private.public.suffix.
            user_c = self.create_user()
            self.assertRegistrable('b.another.public.suffix.private.public.suffix', user_c)
            self.assertRegistrable('long.silly.prefix.another.public.suffix.private.public.suffix', user_c)
            self.assertNotRegistrable('b.private.public.suffix', user_c)
            self.assertRegistrable('b.private.public.suffix', user_b)

    def test_cant_register_internal(self):
        self.assertNotRegistrable('internal')
        self.assertNotRegistrable('catalog.internal')
        self.assertNotRegistrable('some.other.internal')


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
            'too.long.x012345678901234567890123456789012345678901234567890123456789012.com',
        ]:
            with self.assertRaises(ValidationError):
                Domain(owner=self.owner, name=name).save()

        for name in [
            'org',
            'foobar.io',
            'hyphens--------------------hyphens-hyphens.com',
            '_example.com', '_.example.com',
            'exam_ple.com',
            '-dedyn.io', '--dedyn.io', '-.dedyn123.io',
            '_foobar.example.com',
            '-foobar.example.com',
            'hyphen-.example.com',
            'max.length.x01234567890123456789012345678901234567890123456789012345678901.com',
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

            response_set = {data['name'] for data in response.data}
            expected_set = {domain.name for domain in self.my_domains}
            self.assertEqual(response_set, expected_set)
            self.assertFalse(any('keys' in data for data in response.data))

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)

        with self.assertPdnsRequests(self.requests_desec_domain_deletion(self.my_domain)):
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

    def test_update_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name=self.my_domain.name)):
            response = self.client.get(url)
            self.assertStatus(response, status.HTTP_200_OK)

        for method in [self.client.patch, self.client.put]:
            response = method(url, response.data, format='json')
            self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_domains(self):
        self.owner.limit_domains = 100
        self.owner.save()
        for name in [
            '0.8.0.0.0.1.c.a.2.4.6.0.c.e.e.d.4.4.0.1.a.0.1.0.8.f.4.0.1.0.a.2.ip6.arpa',
            'very.long.domain.name.' + self.random_domain_name(),
            self.random_domain_name(),
            'xn--90aeeb7afyklt.xn--p1ai',
        ]:
            with self.assertPdnsRequests(self.requests_desec_domain_creation(name)):
                response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)
                self.assertTrue(all(field in response.data for field in
                                    ['created', 'published', 'name', 'keys', 'minimum_ttl', 'touched']))
                self.assertEqual(len(mail.outbox), 0)
                self.assertTrue(isinstance(response.data['keys'], list))

            with self.assertPdnsRequests(self.request_pdns_zone_retrieve_crypto_keys(name)):
                self.assertStatus(
                    self.client.get(self.reverse('v1:domain-detail', name=name), {'name': name}),
                    status.HTTP_200_OK
                )
                response = self.client.get_rr_sets(name, type='NS', subname='')
                self.assertStatus(response, status.HTTP_200_OK)
                self.assertContainsRRSets(response.data, [dict(subname='', records=settings.DEFAULT_NS, type='NS')])

            domain = Domain.objects.get(name=name)
            self.assertFalse(domain.is_locally_registrable)
            self.assertEqual(domain.renewal_state, Domain.RenewalState.IMMORTAL);

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

    def test_create_domain_with_whitespace(self):
        for name in [
            ' ' + self.random_domain_name(),
            self.random_domain_name() + '  ',
        ]:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertTrue("Domain names must be labels separated by dots. Labels" in response.data['name'][0])

    def test_create_public_suffixes(self):
        for name in self.PUBLIC_SUFFIXES:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data['name'][0].code, 'name_unavailable')

    def test_create_domain_under_public_suffix_with_private_parent(self):
        name = 'amazonaws.com'
        with self.assertPdnsRequests(self.requests_desec_domain_creation(name)[:-1]), PDNSChangeTracker():
            Domain(owner=self.create_user(), name=name).save()
            self.assertTrue(Domain.objects.filter(name=name).exists())

        # If amazonaws.com is owned by another user, we cannot register test.s4.amazonaws.com
        name = 'test.s4.amazonaws.com'
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['name'][0].code, 'name_unavailable')

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
            self.assertStatus(response, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_create_domain_policy(self):
        for name in ['1.2.3..4.test.dedyn.io', 'test..de', '*.' + self.random_domain_name(), 'a' * 64 + '.bla.test']:
            response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertTrue("Domain names must be labels separated by dots. Labels" in response.data['name'][0])

    def test_create_domain_other_parent(self):
        name = 'something.' + self.other_domain.name
        response = self.client.post(self.reverse('v1:domain-list'), {'name': name})
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['name'][0].code, 'name_unavailable')

    def test_create_domain_atomicity(self):
        name = self.random_domain_name()
        with self.assertPdnsRequests(self.request_pdns_zone_create_422()):
            with self.assertRaises(ValueError):
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
            'UPPER.case',
            'case.UPPER',
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


class AutoDelegationDomainOwnerTests(DomainOwnerTestCase):
    DYN = True

    def test_delete_my_domain(self):
        url = self.reverse('v1:domain-detail', name=self.my_domain.name)
        with self.assertPdnsRequests(
            self.requests_desec_domain_deletion(domain=self.my_domain)
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
                self.assertFalse(mail.outbox)  # do not send email

            domain = Domain.objects.get(name=name)
            self.assertTrue(domain.is_locally_registrable)
            self.assertEqual(domain.renewal_state, Domain.RenewalState.FRESH);

    def test_domain_limit(self):
        url = self.reverse('v1:domain-list')
        user_quota = settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT - self.NUM_OWNED_DOMAINS

        for i in range(user_quota):
            name = self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)
            with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
                response = self.client.post(url, {'name': name})
                self.assertStatus(response, status.HTTP_201_CREATED)

        response = self.client.post(url, {'name': self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)})
        self.assertContains(response, 'Domain limit', status_code=status.HTTP_403_FORBIDDEN)
        self.assertFalse(mail.outbox)  # do not send email

    def test_domain_minimum_ttl(self):
        url = self.reverse('v1:domain-list')
        name = self.random_domain_name(self.AUTO_DELEGATION_DOMAINS)
        with self.assertPdnsRequests(self.requests_desec_domain_creation_auto_delegation(name)):
            response = self.client.post(url, {'name': name})
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(response.data['minimum_ttl'], 60)


class DomainManagerTestCase(DesecTestCase):

    def test_filter_qname(self):
        user1, user2 = self.create_user(), self.create_user()
        domains = {
            user1: ['domain.dedyn.io', 'foobar.example'],
            user2: ['dedyn.io', 'desec.io'],
        }
        for user, names in domains.items():
            for name in names:
                Domain(name=name, owner=user).save()

        config = {
            'domain.dedyn.io': {
                None: ['domain.dedyn.io', 'dedyn.io'],
                user1: ['domain.dedyn.io'],
                user2: ['dedyn.io'],
            },
            'foo.bar.baz.foobar.example': {
                None: ['foobar.example'],
                user1: ['foobar.example'],
                user2: [],
            },
            'dedyn.io': {
                None: ['dedyn.io'],
                user1: [],
                user2: ['dedyn.io'],
            },
            'foobar.desec.io': {
                None: ['desec.io'],
                user1: [],
                user2: ['desec.io'],
            },
        }
        config['sub.domain.dedyn.io'] = config['domain.dedyn.io']

        for qname, cases in config.items():
            for owner, expected in cases.items():
                filter_kwargs = dict(owner=owner) if owner is not None else {}
                qs = Domain.objects.filter_qname(qname, **filter_kwargs).values_list('name', flat=True)
                self.assertListEqual(list(qs), expected)

    def test_filter_qname_invalid(self):
        with self.assertRaises(ValueError):
            Domain.objects.filter_qname('foo@bar.com')
