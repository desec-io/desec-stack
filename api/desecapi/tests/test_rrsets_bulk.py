import copy

from django.conf import settings
from rest_framework import status

from desecapi.tests.base import AuthenticatedRRSetBaseTestCase


class AuthenticatedRRSetBulkTestCase(AuthenticatedRRSetBaseTestCase):

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()

        cls.data = [
            {'subname': 'my-cname', 'records': ['example.com.'], 'ttl': 3600, 'type': 'CNAME'},
            {'subname': 'my-bulk', 'records': ['desec.io.', 'foobar.example.'], 'ttl': 3600, 'type': 'PTR'},
        ]

        cls.data_no_records = copy.deepcopy(cls.data)
        cls.data_no_records[1].pop('records')

        cls.data_empty_records = copy.deepcopy(cls.data)
        cls.data_empty_records[1]['records'] = []

        cls.data_no_subname = copy.deepcopy(cls.data)
        cls.data_no_subname[0].pop('subname')

        cls.data_no_ttl = copy.deepcopy(cls.data)
        cls.data_no_ttl[0].pop('ttl')

        cls.data_no_type = copy.deepcopy(cls.data)
        cls.data_no_type[1].pop('type')

        cls.data_no_records_no_ttl = copy.deepcopy(cls.data_no_records)
        cls.data_no_records_no_ttl[1].pop('ttl')

        cls.data_no_subname_empty_records = copy.deepcopy(cls.data_no_subname)
        cls.data_no_subname_empty_records[0]['records'] = []

        cls.bulk_domain = cls.create_domain(owner=cls.owner)
        for data in cls.data:
            cls.create_rr_set(cls.bulk_domain, **data)

    def test_bulk_post_my_rr_sets(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_empty_domain.name)):
            response = self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data)
            self.assertStatus(response, status.HTTP_201_CREATED)

        response = self.client.get_rr_sets(self.my_empty_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, self.data)

        # Check subname requirement on bulk endpoint (and uniqueness at the same time)
        self.assertResponse(
            self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_subname),
            status.HTTP_400_BAD_REQUEST,
            [
                {'subname': ['This field is required.']},
                {'non_field_errors': ['Another RRset with the same subdomain and type exists for this domain.']}
            ]
        )

    def test_bulk_post_rr_sets_empty_records(self):
        expected_response_data = [copy.deepcopy(self.data_empty_records[0]), None]
        expected_response_data[0]['domain'] = self.my_empty_domain.name
        expected_response_data[0]['name'] = '%s.%s.' % (self.data_empty_records[0]['subname'],
                                                        self.my_empty_domain.name)
        self.assertResponse(
            self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_empty_records),
            status.HTTP_400_BAD_REQUEST,
            [
                {},
                {'records': ['This field must not be empty when using POST.']}
            ]
        )

    def test_bulk_post_existing_rrsets(self):
        self.assertResponse(
            self.client.bulk_post_rr_sets(
                domain_name=self.bulk_domain,
                payload=self.data,
            ),
            status.HTTP_400_BAD_REQUEST,
            2 * [{
                'non_field_errors': ['Another RRset with the same subdomain and type exists for this domain.']
            }]
        )

    def test_bulk_post_duplicates(self):
        data = 2 * [self.data[0]] + [self.data[1]]
        self.assertResponse(
            self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=data),
            status.HTTP_400_BAD_REQUEST,
            [
                {'non_field_errors': ['Same subname and type as in position(s) 1, but must be unique.']},
                {'non_field_errors': ['Same subname and type as in position(s) 0, but must be unique.']},
                {},
            ]
        )

        data = 2 * [self.data[0]] + [self.data[1]] + [self.data[0]]
        self.assertResponse(
            self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=data),
            status.HTTP_400_BAD_REQUEST,
            [
                {'non_field_errors': ['Same subname and type as in position(s) 1, 3, but must be unique.']},
                {'non_field_errors': ['Same subname and type as in position(s) 0, 3, but must be unique.']},
                {},
                {'non_field_errors': ['Same subname and type as in position(s) 0, 1, but must be unique.']},
            ]
        )

    def test_bulk_post_missing_fields(self):
        self.assertResponse(
            self.client.bulk_post_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                    {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                    {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                    {'subname': '', 'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                    {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'SOA',
                     'records': ['get.desec.io. get.desec.io. 2018034419 10800 3600 604800 60']},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'OPT', 'records': ['9999']},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'TYPE099', 'records': ['v=spf1 mx -all']},
                ]
            ),
            status.HTTP_400_BAD_REQUEST,
            [
                {'type': ['This field is required.']},
                {'ttl': [f'Ensure this value is greater than or equal to {self.my_empty_domain.minimum_ttl}.']},
                {'subname': ['This field is required.']},
                {},
                {'ttl': ['This field is required.']},
                {'records': ['This field is required.']},
                {'type': ['You cannot tinker with the SOA RR set. It is managed automatically.']},
                {'type': ['You cannot tinker with the OPT RR set. It is managed automatically.']},
                {'type': ['Generic type format is not supported.']},
            ]
        )

    def test_bulk_patch_cname_exclusivity(self):
        response = self.client.bulk_patch_rr_sets(
            domain_name=self.my_rr_set_domain.name,
            payload=[
                {'subname': 'test', 'type': 'A', 'ttl': 3600, 'records': ['1.2.3.4']},
                {'subname': 'test', 'type': 'CNAME', 'ttl': 3600, 'records': ['example.com.']},
            ]
        )
        self.assertResponse(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), [
            {"non_field_errors":["RRset with conflicting type present: 1 (CNAME). (No other RRsets are allowed alongside CNAME.)"]},
            {"non_field_errors":["RRset with conflicting type present: 0 (A), database (A, TXT). (No other RRsets are allowed alongside CNAME.)"]},
        ])

    def test_bulk_post_accepts_empty_list(self):
        self.assertResponse(
            self.client.bulk_post_rr_sets(domain_name=self.my_empty_domain.name, payload=[]),
            status.HTTP_201_CREATED,
        )

    def test_bulk_patch_fresh_rrsets_need_records(self):
        response = self.client.bulk_patch_rr_sets(self.my_empty_domain.name, payload=self.data_no_records)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{}, {'records': ['This field is required.']}])

        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            response = self.client.bulk_patch_rr_sets(self.my_empty_domain.name, payload=self.data_empty_records)
            self.assertStatus(response, status.HTTP_200_OK)

    def test_bulk_patch_fresh_rrsets_need_subname(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_subname)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_bulk_patch_fresh_rrsets_need_ttl(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_ttl)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{'ttl': ['This field is required.']}, {}])

    def test_bulk_patch_fresh_rrsets_need_type(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_type)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{}, {'type': ['This field is required.']}])

    def test_bulk_patch_does_not_accept_single_objects(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data[0])
        self.assertContains(response, 'Expected a list of items but got dict.', status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_patch_does_accept_empty_list(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=[])
        self.assertStatus(response, status.HTTP_200_OK)

        response = self.client.bulk_patch_rr_sets(domain_name=self.my_rr_set_domain.name, payload=[])
        self.assertStatus(response, status.HTTP_200_OK)

    def test_bulk_patch_does_not_accept_empty_payload(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=None)
        self.assertContains(response, 'No data provided', status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_patch_cname_exclusivity_atomic_rrset_replacement(self):
        self.create_rr_set(self.my_empty_domain, subname='test', type='A', records=['1.2.3.4'], ttl=3600)

        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            response = self.client.bulk_patch_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'test', 'type': 'CNAME', 'ttl': 3605, 'records': ['example.com.']},
                    {'subname': 'test', 'type': 'A', 'records': []},
                ]
            )
            self.assertResponse(response, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]['type'], 'CNAME')
            self.assertEqual(response.data[0]['records'], ['example.com.'])
            self.assertEqual(response.data[0]['ttl'], 3605)

        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            response = self.client.bulk_patch_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'test', 'type': 'CNAME', 'records': []},
                    {'subname': 'test', 'type': 'A', 'ttl': 3600, 'records': ['5.4.2.1']},
                ]
            )
            self.assertResponse(response, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]['type'], 'A')
            self.assertEqual(response.data[0]['records'], ['5.4.2.1'])
            self.assertEqual(response.data[0]['ttl'], 3600)

    def test_bulk_patch_full_on_empty_domain(self):
        # Full patch always works
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_empty_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data)
            self.assertStatus(response, status.HTTP_200_OK)

        # Check that RRsets have been created
        response = self.client.get_rr_sets(self.my_empty_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, self.data)

    def test_bulk_patch_change_records(self):
        data_no_ttl = copy.deepcopy(self.data_no_ttl)
        data_no_ttl[0]['records'] = ['example.org.']
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.bulk_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.bulk_domain.name, payload=data_no_ttl)
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.client.get_rr_sets(self.bulk_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, data_no_ttl)

    def test_bulk_patch_change_ttl(self):
        data_no_records = copy.deepcopy(self.data_no_records)
        data_no_records[1]['ttl'] = 3911
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.bulk_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.bulk_domain.name, payload=data_no_records)
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.client.get_rr_sets(self.bulk_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, data_no_records)

    def test_bulk_patch_does_not_need_ttl(self):
        self.assertResponse(
            self.client.bulk_patch_rr_sets(domain_name=self.bulk_domain.name, payload=self.data_no_ttl),
            status.HTTP_200_OK,
        )

    def test_bulk_patch_delete_non_existing_rr_sets(self):
        self.assertResponse(
            self.client.bulk_patch_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'a', 'type': 'A', 'records': [], 'ttl': 3622},
                    {'subname': 'b', 'type': 'AAAA', 'records': []},
                ]),
            status.HTTP_200_OK,
            [],
        )

    def test_bulk_patch_missing_invalid_fields_1(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            self.client.bulk_post_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': '', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']},
                    {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA', 'ttl': 3603},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA', 'records': ['::1', '::2']},
                ]
            )
        self.assertResponse(
            self.client.bulk_patch_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                    {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                    {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                    {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                ]),
            status.HTTP_400_BAD_REQUEST,
            [
                {'type': ['This field is required.']},
                {'ttl': [f'Ensure this value is greater than or equal to {settings.MINIMUM_TTL_DEFAULT}.']},
                {'subname': ['This field is required.']},
                {},
                {},
            ]
        )

    def test_bulk_patch_missing_invalid_fields_2(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(self.my_empty_domain.name)):
            self.client.bulk_post_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': '', 'ttl': 3650, 'type': 'TXT', 'records': ['"foo"']}
                ]
            )
        self.assertResponse(
            self.client.bulk_patch_rr_sets(
                domain_name=self.my_empty_domain.name,
                payload=[
                    {'subname': 'a.1', 'records': ['dead::beef'], 'ttl': 3622},
                    {'subname': 'b.1', 'ttl': -50, 'type': 'AAAA', 'records': ['dead::beef']},
                    {'ttl': 3640, 'type': 'TXT', 'records': ['"bar"']},
                    {'subname': 'c.1', 'records': ['dead::beef'], 'type': 'AAAA'},
                    {'subname': 'd.1', 'ttl': 3650, 'type': 'AAAA'},
                ]),
            status.HTTP_400_BAD_REQUEST,
            [
                {'type': ['This field is required.']},
                {'ttl': [f'Ensure this value is greater than or equal to {settings.MINIMUM_TTL_DEFAULT}.']},
                {'subname': ['This field is required.']},
                {'ttl': ['This field is required.']},
                {'records': ['This field is required.']},
            ]
        )

    def test_bulk_put_partial(self):
        # Need all fields
        for domain in [self.my_empty_domain, self.bulk_domain]:
            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_records)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{}, {'records': ['This field is required.']}])

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_ttl)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{'ttl': ['This field is required.']}, {}])

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_records_no_ttl)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{},
                                             {'ttl': ['This field is required.'],
                                              'records': ['This field is required.']}])

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_subname)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{'subname': ['This field is required.']}, {}])

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_subname_empty_records)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{'subname': ['This field is required.']}, {}])

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_type)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{}, {'type': ['This field is required.']}])

    def test_bulk_put_does_not_accept_single_objects(self):
        response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data[0])
        self.assertContains(response, 'Expected a list of items but got dict.', status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_put_does_accept_empty_list(self):
        response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=[])
        self.assertStatus(response, status.HTTP_200_OK)
        response = self.client.bulk_put_rr_sets(domain_name=self.my_rr_set_domain.name, payload=[])
        self.assertStatus(response, status.HTTP_200_OK)

    def test_bulk_put_does_not_accept_empty_payload(self):
        response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=None)
        self.assertContains(response, 'No data provided', status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_put_does_not_accept_list_of_crap(self):
        response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=['bla'])
        self.assertContains(response, 'Expected a dictionary, but got str.', status_code=status.HTTP_400_BAD_REQUEST)

        response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=[42])
        self.assertContains(response, 'Expected a dictionary, but got int.', status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_put_full(self):
        # Full PUT always works
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_empty_domain.name)):
            response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data)
            self.assertStatus(response, status.HTTP_200_OK)

        # Check that RRsets have been created
        response = self.client.get_rr_sets(self.my_empty_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, self.data)

        # Do not expect any updates, but successful code when PUT'ing only existing RRsets
        response = self.client.bulk_put_rr_sets(domain_name=self.bulk_domain.name, payload=self.data)
        self.assertStatus(response, status.HTTP_200_OK)

    def test_bulk_put_invalid_records(self):
        for records in [
            'asfd',
            ['1.1.1.1', '2.2.2.2', 123],
            ['1.2.3.4', None],
            [True, '1.1.1.1'],
            dict(foobar='foobar', asdf='asdf'),
        ]:
            payload = [{'subname': 'a.2', 'ttl': 3600, 'type': 'MX', 'records': records}]
            response = self.client.bulk_put_rr_sets(domain_name=self.my_empty_domain.name, payload=payload)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertTrue('records' in response.data[0])

    def test_bulk_put_empty_records(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.bulk_domain.name)):
            self.assertStatus(
                self.client.bulk_put_rr_sets(domain_name=self.bulk_domain.name, payload=self.data_empty_records),
                status.HTTP_200_OK
            )

    def test_bulk_duplicate_rrset(self):
        data = self.data + self.data
        for bulk_request_rr_sets in [
            self.client.bulk_patch_rr_sets,
            self.client.bulk_put_rr_sets,
            self.client.bulk_post_rr_sets,
        ]:
            response = bulk_request_rr_sets(domain_name=self.my_empty_domain.name, payload=data)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_bulk_patch_or_post_failure_with_single_rrset(self):
        for method in [self.client.bulk_patch_rr_sets, self.client.bulk_put_rr_sets]:
            response = method(domain_name=self.my_empty_domain.name, payload=self.data[0])
            self.assertContains(response, 'Expected a list of items but got dict.',
                                status_code=status.HTTP_400_BAD_REQUEST)

    def test_bulk_delete_rrsets(self):
        self.assertStatus(
            self.client.delete(
                self.reverse('v1:rrsets', name=self.my_empty_domain.name),
                data=None,
            ),
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
