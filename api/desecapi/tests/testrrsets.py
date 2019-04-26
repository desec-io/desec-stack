import operator
from functools import reduce

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from rest_framework import status

from desecapi.models import RRset
from desecapi.tests.base import DesecTestCase, DomainOwnerTestCase


class UnauthenticatedRRSetTestCase(DesecTestCase):
    
    def test_unauthorized_access(self):
        url = self.reverse('v1:rrsets', name='example.com')
        for method in [
            self.client.get, 
            self.client.post, 
            self.client.put, 
            self.client.delete, 
            self.client.patch
        ]:
            response = method(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedRRSetTestCase(DomainOwnerTestCase):
    DEAD_TYPES = ['ALIAS', 'DNAME']
    RESTRICTED_TYPES = ['SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM', 'OPT']

    # see https://doc.powerdns.com/md/types/
    PDNS_RR_TYPES = ['A', 'AAAA', 'AFSDB', 'ALIAS', 'CAA', 'CERT', 'CDNSKEY', 'CDS', 'CNAME', 'DNSKEY', 'DNAME', 'DS',
                     'HINFO', 'KEY', 'LOC', 'MX', 'NAPTR', 'NS', 'NSEC', 'NSEC3', 'NSEC3PARAM', 'OPENPGPKEY', 'PTR',
                     'RP', 'RRSIG', 'SOA', 'SPF', 'SSHFP', 'SRV', 'TKEY', 'TSIG', 'TLSA', 'SMIMEA', 'TXT', 'URI']
    ALLOWED_TYPES = ['A', 'AAAA', 'AFSDB', 'CAA', 'CERT', 'CDNSKEY', 'CDS', 'CNAME', 'DS', 'HINFO', 'KEY', 'LOC', 'MX',
                     'NAPTR', 'NS', 'NSEC', 'NSEC3', 'OPENPGPKEY', 'PTR', 'RP', 'SPF', 'SSHFP', 'SRV', 'TKEY', 'TSIG',
                     'TLSA', 'SMIMEA', 'TXT', 'URI']

    SUBNAMES = ['foo', 'bar.baz', 'q.w.e.r.t', '*', '*.foobar', '_']

    @classmethod
    def _test_rr_sets(cls, subname=None, type_=None, records=None, ttl=None):
        """
        Gives a list of example RR sets for testing.
        Args:
            subname: Filter by subname. None to allow any.
            type_: Filter by type. None to allow any.
            records: Filter by records. Must match exactly. None to allow any.
            ttl: Filter by ttl. None to allow any.

        Returns: Returns a list of tuples that represents example RR sets represented as 4-tuples consisting of
        subname, type_, records, ttl
        """
        # TODO add more examples of cls.ALLOWED_TYPES
        rr_sets = [
            ('', 'A', ['1.2.3.4'], 120),
            ('test', 'A', ['2.2.3.4'], 120),
            ('test', 'TXT', ['"foobar"'], 120),
        ] + [
            (subname, 'TXT', ['"hey ho, let\'s go!"'], 134)
            for subname in cls.SUBNAMES
        ] + [
            (subname, type_, ['"10 mx1.example.com."'], 101)
            for subname in cls.SUBNAMES
            for type_ in ['MX', 'SPF']
        ] + [
            (subname, 'A', ['"1.2.3.4"'], 187)
            for subname in cls.SUBNAMES
        ]

        if subname or type_ or records or ttl:
            rr_sets = [
                rr_set for rr_set in rr_sets
                if (
                    (subname is None or subname == rr_set[0]) and
                    (type_ is None or type_ == rr_set[1]) and
                    (records is None or records == rr_set[2]) and
                    (ttl is None or ttl == rr_set[3])
                )
            ]
        return rr_sets

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()
        # TODO this test does not cover "dyn" / auto delegation domains
        cls.my_empty_domain = cls.create_domain(suffix='', owner=cls.owner)
        cls.my_rr_set_domain = cls.create_domain(suffix='', owner=cls.owner)
        cls.other_rr_set_domain = cls.create_domain(suffix='')
        for domain in [cls.my_rr_set_domain, cls.other_rr_set_domain]:
            for (subname, type_, records, ttl) in cls._test_rr_sets():
                cls.create_rr_set(domain, subname=subname, type=type_, records=records, ttl=ttl)

    def assertRRSet(self, response_rr, domain=None, subname=None, records=None, type_=None, **kwargs):
        kwargs['domain'] = domain
        kwargs['subname'] = subname
        kwargs['records'] = records
        kwargs['type'] = type_

        for key, value in kwargs.items():
            if value is not None:
                self.assertEqual(
                    response_rr[key], value,
                    'RR set did not have the expected %s: Expected "%s" but was "%s" in %s' % (
                        key, value, response_rr[key], response_rr
                    )
                )

    @staticmethod
    def _filter_rr_sets(rr_sets, **kwargs):
        return [
            rr_sets for rr_set in rr_sets
            if reduce(operator.and_, [rr_set.get(key, None) == value for key, value in kwargs.items()])
        ]

    def assertRRSetCount(self, rr_sets, count, **kwargs):
        filtered_rr_sets = self._filter_rr_sets(rr_sets, **kwargs)
        if len(filtered_rr_sets) != count:
            self.fail('Expected to find %i RR set(s) with %s, but only found %i in %s.' % (
                count, kwargs, len(filtered_rr_sets), rr_sets
            ))

    def assertContainsRRSet(self, rr_sets, **kwargs):
        filtered_rr_sets = self._filter_rr_sets(rr_sets, **kwargs)
        if not filtered_rr_sets:
            self.fail('Expected to find RR set with %s, but only found %s.' % (
                kwargs, rr_sets
            ))

    def test_subname_validity(self):
        with self.assertRaises(ValidationError):
            RRset(domain=self.my_domain, subname='aeroport', ttl=60, type='A').save()
            RRset(domain=self.my_domain, subname='AEROPORT', ttl=60, type='A').save()
            RRset(domain=self.my_domain, subname='aéroport', ttl=100, type='A').save()

    def test_retrieve_my_rr_sets(self):
        for response in [
            self.client.get_rr_sets(self.my_domain.name),
            self.client.get_rr_sets(self.my_domain.name, subname=''),
        ]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 2, response.data)
            self.assertContainsRRSet(response.data, subname='', records=settings.DEFAULT_NS, type='NS')

    def test_retrieve_other_rr_sets(self):
        self.assertEqual(self.client.get_rr_sets(self.other_domain.name).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get_rr_sets(self.other_domain.name, subname='test').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.get_rr_sets(self.other_domain.name, type='A').status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_my_rr_sets_filter(self):
        response = self.client.get_rr_sets(self.my_rr_set_domain.name)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(self._test_rr_sets()) + 1)  # Don't forget about the NS type RR set

        for subname in self.SUBNAMES:
            response = self.client.get_rr_sets(self.my_rr_set_domain.name, subname=subname)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertRRSetCount(response.data, count=len(self._test_rr_sets(subname=subname)), subname=subname)

        for type_ in self.ALLOWED_TYPES:
            response = self.client.get_rr_sets(self.my_rr_set_domain.name, type=type_)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            if type_ != 'NS':  # count does not match for NS, that's okay
                self.assertRRSetCount(response.data, count=len(self._test_rr_sets(type_=type_)), type=type_)

    def test_create_my_rr_sets(self):
        for subname in ['', 'create-my-rr-sets', 'foo.create-my-rr-sets', 'bar.baz.foo.create-my-rr-sets']:
            for data in [
                {'subname': subname, 'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'},
                {'subname': subname, 'records': ['desec.io.'], 'ttl': 900, 'type': 'PTR'},
            ]:
                with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_empty_domain.name)):
                    response = self.client.post_rr_set(domain_name=self.my_empty_domain.name, **data)
                    self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

                response = self.client.get_rr_sets(self.my_empty_domain.name)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertRRSetCount(response.data, count=1, **data)

                response = self.client.get_rr_set(self.my_empty_domain.name, data['subname'], data['type'])
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertRRSet(response.data, **data)

    def test_create_my_rr_sets_type_restriction(self):
        for subname in ['', 'create-my-rr-sets', 'foo.create-my-rr-sets', 'bar.baz.foo.create-my-rr-sets']:
            for data in [
                {'subname': subname, 'ttl': 60, 'type': 'a'},
                {'subname': subname, 'records': ['10 example.com.'], 'ttl': 60, 'type': 'txt'}
            ] + [
                {'subname': subname, 'records': ['10 example.com.'], 'ttl': 60, 'type': type_}
                for type_ in self.DEAD_TYPES
            ] + [
                {'subname': subname, 'records': ['ns1.desec.io. peter.desec.io. 2584 10800 3600 604800 60'],
                 'ttl': 60, 'type': type_}
                for type_ in self.RESTRICTED_TYPES
            ]:
                response = self.client.post_rr_set(self.my_domain.name, **data)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

                response = self.client.get_rr_sets(self.my_domain.name)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertRRSetCount(response.data, count=0, **data)

    def test_create_my_rr_sets_without_records(self):
        for subname in ['', 'create-my-rr-sets', 'foo.create-my-rr-sets', 'bar.baz.foo.create-my-rr-sets']:
            for data in [
                {'subname': subname, 'records': [], 'ttl': 60, 'type': 'A'},
                {'subname': subname, 'ttl': 60, 'type': 'A'},
            ]:
                response = self.client.post_rr_set(self.my_empty_domain.name, **data)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

                response = self.client.get_rr_sets(self.my_empty_domain.name)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertRRSetCount(response.data, count=0, **data)

    def test_create_other_rr_sets(self):
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        response = self.client.post_rr_set(self.other_domain.name, **data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_my_rr_sets_twice(self):
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'}
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            response = self.client.post_rr_set(self.my_empty_domain.name, **data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data['records'][0] = ['3.2.2.1']
        response = self.client.post_rr_set(self.my_empty_domain.name, **data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_create_my_rr_sets_unknown_type(self):
        for _type in ['AA', 'ASDF']:
            with self.assertPdnsRequests(
                    self.request_pdns_zone_update_unknown_type(name=self.my_domain.name, unknown_types=_type)
            ):
                response = self.client.post_rr_set(self.my_domain.name, records=['1234'], ttl=60, type=_type)
                self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_create_my_rr_sets_uppercase_subname(self):
        data = {'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A', 'subname': 'uppERcase'}
        response = self.client.post_rr_set(self.my_empty_domain.name, **data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("not lowercase" in response.data['subname'][0])

    def test_retrieve_my_rr_sets_apex(self):
        response = self.client.get_rr_set(self.my_rr_set_domain.name, subname='', type_='A')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '1.2.3.4')
        self.assertEqual(response.data['ttl'], 120)

    def test_retrieve_my_rr_sets_restricted_types(self):
        for type_ in self.RESTRICTED_TYPES:
            response = self.client.get_rr_sets(self.my_domain.name, type=type_)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            response = self.client.get_rr_sets(self.my_domain.name, type=type_, subname='')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_my_rr_sets(self):
        for subname in self.SUBNAMES:
            with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_rr_set_domain.name)):
                response = self.client.put_rr_set(self.my_rr_set_domain.name, subname, 'A', records=['2.2.3.4'], ttl=30)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            response = self.client.get_rr_set(self.my_rr_set_domain.name, subname, 'A')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['records'], ['2.2.3.4'])
            self.assertEqual(response.data['ttl'], 30)

            response = self.client.put_rr_set(self.my_rr_set_domain.name, subname, 'A', records=['2.2.3.5'])
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

            response = self.client.put_rr_set(self.my_rr_set_domain.name, subname, 'A', ttl=37)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partially_update_my_rr_sets(self):
        for subname in self.SUBNAMES:
            current_rr_set = self.client.get_rr_set(self.my_rr_set_domain.name, subname, 'A').data
            for data in [
                {'records': ['2.2.3.4'], 'ttl': 30},
                {'records': ['3.2.3.4']},
                {'ttl': 37},
            ]:
                with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_rr_set_domain.name)):
                    response = self.client.patch_rr_set(self.my_rr_set_domain.name, subname, 'A', **data)
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
                response = self.client.get_rr_set(self.my_rr_set_domain.name, subname, 'A')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                current_rr_set.update(data)
                self.assertEqual(response.data['records'], current_rr_set['records'])
                self.assertEqual(response.data['ttl'], current_rr_set['ttl'])

            data = {}
            response = self.client.patch_rr_set(self.my_rr_set_domain.name, subname, 'A', **data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_partially_update_other_rr_sets(self):
        for subname in self.SUBNAMES:
            response = self.client.patch_rr_set(self.other_rr_set_domain.name, subname='',
                                                type_='A', records=['3.2.3.4'], ttl=334)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_other_rr_sets(self):
        for subname in self.SUBNAMES:
            response = self.client.patch_rr_set(self.other_rr_set_domain.name, subname='', type_='A', ttl=305)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_essential_properties(self):
        # Changing the subname is expected to cause an error
        url = self.reverse('v1:rrset', name=self.my_rr_set_domain.name, subname='test', type='A')
        data = {'records': ['3.2.3.4'], 'ttl': 120, 'subname': 'test2'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Changing the type is expected to cause an error
        data = {'records': ['3.2.3.4'], 'ttl': 120, 'type': 'TXT'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check that nothing changed
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '2.2.3.4')
        self.assertEqual(response.data['ttl'], 120)
        self.assertEqual(response.data['name'], 'test.' + self.my_rr_set_domain.name + '.')
        self.assertEqual(response.data['subname'], 'test')
        self.assertEqual(response.data['type'], 'A')

        # This is expected to work, but the fields are ignored
        data = {'records': ['3.2.3.4'], 'name': 'example.com.', 'domain': 'example.com'}
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_rr_set_domain.name)):
            response = self.client.patch(url, data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['records'][0], '3.2.3.4')
        self.assertEqual(response.data['domain'], self.my_rr_set_domain.name)
        self.assertEqual(response.data['name'], 'test.' + self.my_rr_set_domain.name + '.')

    def test_delete_my_rr_sets_with_patch(self):
        for subname in self.SUBNAMES:
            with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_rr_set_domain.name)):
                response = self.client.patch_rr_set(self.my_rr_set_domain.name, subname=subname, type_='A', records=[])
                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

            response = self.client.get_rr_set(self.my_rr_set_domain.name, subname=subname, type_='A')
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_my_rr_sets_with_delete(self):
        for subname in self.SUBNAMES:
            with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_rr_set_domain.name)):
                response = self.client.delete_rr_set(self.my_rr_set_domain.name, subname=subname, type_='A')
                self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

            response = self.client.get_rr_set(self.my_rr_set_domain.name, subname=subname, type_='A')
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_other_rr_sets(self):
        for subname in self.SUBNAMES:
            # Try PATCH empty
            response = self.client.patch_rr_set(self.other_rr_set_domain.name, subname=subname, type_='A', records=[])
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

            # Try DELETE
            response = self.client.delete_rr_set(self.other_rr_set_domain.name, subname=subname, type_='A')
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

            # Make sure it actually is still there
            self.assertGreater(len(self.other_rr_set_domain.rrset_set.filter(subname=subname, type='A')), 0)

    def test_import_rr_sets(self):
        with self.assertPdnsRequests(self.request_pdns_zone_retrieve(name=self.my_domain.name)):
            call_command('sync-from-pdns', self.my_domain.name)
        for response in [
            self.client.get_rr_sets(self.my_domain.name),
            self.client.get_rr_sets(self.my_domain.name, subname=''),
        ]:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1, response.data)
            self.assertContainsRRSet(response.data, subname='', records=settings.DEFAULT_NS, type='NS')
