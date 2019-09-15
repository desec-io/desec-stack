from rest_framework.reverse import reverse

from desecapi import models
from desecapi.tests.base import DesecTestCase


class RegistrationTestCase(DesecTestCase):

    def setUp(self):
        super().setUp()
        email = self.random_username()
        self.assertRegistration(
            email=email,
            password=self.random_password(),
            remote_addr="1.3.3.7",
        )
        self.user = models.User.objects.get(email=email)

    def assertRegistration(self, remote_addr='', status=202, **kwargs):
        url = reverse('v1:register')
        post_kwargs = {}
        if remote_addr:
            post_kwargs['REMOTE_ADDR'] = remote_addr
        response = self.client.post(url, kwargs, **post_kwargs)
        self.assertStatus(response, status)
        return response

    def test_registration_successful(self):
        self.assertEqual(self.user.registration_remote_ip, "1.3.3.7")
