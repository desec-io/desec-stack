from rest_framework import status

from desecapi.tests.base import DesecTestCase


class ReplicationTest(DesecTestCase):
    def test_serials(self):
        url = self.reverse("v1:serial")
        serials = {"test.example.": 12345, "example.org.": 54321}

        # knot.get_serials is patched by MockPDNSTestCase.setUp(); configure it here.
        self.mock_knot_get_serials.return_value = serials

        # Run twice to make sure cache output varies on remote address
        for i in range(2):
            response = self.client.get(path=url, REMOTE_ADDR="123.8.0.2")
            self.assertStatus(response, status.HTTP_401_UNAUTHORIZED)

            response = self.client.get(path=url, REMOTE_ADDR="10.8.0.2")
            self.assertStatus(response, status.HTTP_200_OK)
            self.assertEqual(response.data, serials)

            # Do not expect knot call in next iteration (result will be cached)
            self.mock_knot_get_serials.return_value = {}
