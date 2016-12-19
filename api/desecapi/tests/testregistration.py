from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from desecapi import models


class RegistrationTest(APITestCase):
    def testRegistrationSuccessful(self):
        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.7")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.7")
