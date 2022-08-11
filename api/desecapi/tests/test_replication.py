import json

from rest_framework import status

from desecapi.tests.base import DesecTestCase


class ReplicationTest(DesecTestCase):
    def test_serials(self):
        url = self.reverse('v1:serial')
        zones = [
            {'name': 'test.example.', 'edited_serial': 12345},
            {'name': 'example.org.', 'edited_serial': 54321},
        ]
        serials = {zone['name']: zone['edited_serial'] for zone in zones}
        pdns_requests = [{
            'method': 'GET',
            'uri': self.get_full_pdns_url(r'/zones', ns='MASTER'),
            'status': 200,
            'body': json.dumps(zones),
        }]

        # Run twice to make sure cache output varies on remote address
        for i in range(2):
            response = self.client.get(path=url, REMOTE_ADDR='123.8.0.2')
            self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

            with self.assertPdnsRequests(pdns_requests):
                response = self.client.get(path=url, REMOTE_ADDR='10.8.0.2')
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, serials)

            # Do not expect pdns request in next iteration (result will be cached)
            pdns_requests = []
