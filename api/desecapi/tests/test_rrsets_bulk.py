import copy

from rest_framework import status

from desecapi.tests.base import AuthenticatedRRSetBaseTestCase


class AuthenticatedRRSetBulkTestCase(AuthenticatedRRSetBaseTestCase):

    @classmethod
    def setUpTestDataWithPdns(cls):
        super().setUpTestDataWithPdns()

        cls.data = [
            {'subname': 'my-bulk', 'records': ['1.2.3.4'], 'ttl': 60, 'type': 'A'},
            {'subname': 'my-bulk', 'records': ['desec.io.'], 'ttl': 60, 'type': 'PTR'},
        ]

        cls.data_no_records = copy.deepcopy(cls.data)
        cls.data_no_records[1].pop('records')

        cls.data_no_subname = copy.deepcopy(cls.data)
        cls.data_no_subname[0].pop('subname')

        cls.data_no_ttl = copy.deepcopy(cls.data)
        cls.data_no_ttl[0].pop('ttl')

        cls.data_no_type = copy.deepcopy(cls.data)
        cls.data_no_type[1].pop('type')

        cls.data_no_records_no_ttl = copy.deepcopy(cls.data_no_records)
        cls.data_no_records_no_ttl[1].pop('ttl')

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

    def test_bulk_patch_fresh_rrsets_need_records(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_records)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{}, {'records': ['This field is required for new RRsets.']}])

    def test_bulk_patch_fresh_rrsets_dont_need_subname(self):
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.my_empty_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name,
                                                      payload=self.data_no_subname)
            self.assertStatus(response, status.HTTP_200_OK)

            # Check that RRsets have been created
            response = self.client.get_rr_sets(self.my_empty_domain.name)
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertRRSetsCount(response.data, self.data_no_subname)

    def test_bulk_patch_fresh_rrsets_need_ttl(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_ttl)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{'ttl': ['This field is required for new RRsets.']}, {}])

    def test_bulk_patch_fresh_rrsets_need_type(self):
        response = self.client.bulk_patch_rr_sets(domain_name=self.my_empty_domain.name, payload=self.data_no_type)
        self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, [{}, {'type': ['This field is required.']}])

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
        data_no_ttl[0]['records'] = ['4.3.2.1', '8.8.1.2']
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.bulk_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.bulk_domain.name, payload=data_no_ttl)
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.client.get_rr_sets(self.bulk_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, data_no_ttl)

    def test_bulk_patch_change_ttl(self):
        data_no_records = copy.deepcopy(self.data_no_records)
        data_no_records[1]['ttl'] = 911
        with self.assertPdnsRequests(self.requests_desec_rr_sets_update(name=self.bulk_domain.name)):
            response = self.client.bulk_patch_rr_sets(domain_name=self.bulk_domain.name, payload=data_no_records)
            self.assertStatus(response, status.HTTP_200_OK)

        response = self.client.get_rr_sets(self.bulk_domain.name)
        self.assertStatus(response, status.HTTP_200_OK)
        self.assertRRSetsCount(response.data, data_no_records)

    def test_bulk_put_partial(self):
        # Need TTL and type and records
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

            response = self.client.bulk_put_rr_sets(domain_name=domain.name, payload=self.data_no_type)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data, [{}, {'type': ['This field is required.']}])

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

    def test_bulk_duplicate_rrset(self):
        data = self.data + self.data
        for bulk_request_rr_sets in [
            self.client.bulk_patch_rr_sets,
            self.client.bulk_put_rr_sets,
            self.client.bulk_post_rr_sets,
        ]:
            response = bulk_request_rr_sets(domain_name=self.my_empty_domain.name, payload=data)
            self.assertStatus(response, status.HTTP_400_BAD_REQUEST)
