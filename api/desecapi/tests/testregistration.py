from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from desecapi import models
from datetime import timedelta
from django.utils import timezone
from django.core import mail
from desecapi.emails import send_account_lock_email
from api import settings


class RegistrationTest(APITestCase):

    def test_registration_successful(self):
        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.7")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.7")

    def test_multiple_registration_locked_same_ip_short_time(self):
        outboxlen = len(mail.outbox)

        url = reverse('register')
        data = {'email': utils.generateUsername(),
                'password': utils.generateRandomString(size=12), 'dyn': True}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.7")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.7")
        self.assertIsNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen)

        url = reverse('register')
        data = {'email': utils.generateUsername(),
                'password': utils.generateRandomString(size=12), 'dyn': True}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.7")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.7")
        self.assertIsNotNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen + 1)

        url = reverse('register')
        data = {'email': utils.generateUsername(),
                'password': utils.generateRandomString(size=12), 'dyn': True}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.7")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.7")
        self.assertIsNotNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen + 2)

    def test_multiple_registration_not_locked_different_ip(self):
        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.8")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.8")
        self.assertIsNone(user.locked)

        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.9")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.9")
        self.assertIsNone(user.locked)

    def test_multiple_registration_not_locked_same_ip_long_time(self):
        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.10")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.10")
        self.assertIsNone(user.locked)

        #fake registration time
        user.created = timezone.now() - timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS+1)
        user.save()

        url = reverse('register')
        data = {'email': utils.generateUsername(), 'password': utils.generateRandomString(size=12)}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.10")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertEqual(user.registration_remote_ip, "1.3.3.10")
        self.assertIsNone(user.locked)

    def test_send_captcha_email_manually(self):
        outboxlen = len(mail.outbox)

        url = reverse('register')
        data = {'email': utils.generateUsername(),
                'password': utils.generateRandomString(size=12), 'dyn': True}
        response = self.client.post(url, data, REMOTE_ADDR="1.3.3.10")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        send_account_lock_email(None, user)

        self.assertEqual(len(mail.outbox), outboxlen+1)

    def test_multiple_registration_locked_same_email_host(self):
        outboxlen = len(mail.outbox)

        url = reverse('register')
        for i in range(settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT):
            data = {
                'email': utils.generateRandomString() + '@test-same-email.desec.io',
                'password': utils.generateRandomString(size=12),
                'dyn': True,
            }
            response = self.client.post(url, data, REMOTE_ADDR=utils.generateRandomIPv4Address())
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            user = models.User.objects.get(email=data['email'])
            self.assertEqual(user.email, data['email'])
            self.assertIsNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen)

        url = reverse('register')
        data = {
            'email': utils.generateRandomString() + '@test-same-email.desec.io',
            'password': utils.generateRandomString(size=12),
            'dyn': True,
        }
        response = self.client.post(url, data, REMOTE_ADDR=utils.generateRandomIPv4Address())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertIsNotNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen + 1)

    def test_multiple_registration_not_locked_same_email_host_long_time(self):
        outboxlen = len(mail.outbox)

        url = reverse('register')
        for i in range(settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT):
            data = {
                'email': utils.generateRandomString() + '@test-same-email-1.desec.io',
                'password': utils.generateRandomString(size=12),
                'dyn': True,
            }
            response = self.client.post(url, data, REMOTE_ADDR=utils.generateRandomIPv4Address())
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            user = models.User.objects.get(email=data['email'])
            self.assertEqual(user.email, data['email'])
            self.assertIsNone(user.locked)

            #fake registration time
            user = models.User.objects.get(email=data['email'])
            user.created = timezone.now() - timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS+1)
            user.save()

        self.assertEqual(len(mail.outbox), outboxlen)

        url = reverse('register')
        data = {
            'email': utils.generateRandomString() + '@test-same-email-1.desec.io',
            'password': utils.generateRandomString(size=12),
            'dyn': True,
        }
        response = self.client.post(url, data, REMOTE_ADDR=utils.generateRandomIPv4Address())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = models.User.objects.get(email=data['email'])
        self.assertEqual(user.email, data['email'])
        self.assertIsNone(user.locked)

        self.assertEqual(len(mail.outbox), outboxlen)

    def test_token_email(self):
        outboxlen = len(mail.outbox)

        url = reverse('register')
        data = {
            'email': utils.generateRandomString() + '@test-same-email.desec.io',
            'password': utils.generateRandomString(size=12),
            'dyn': False,
        }
        response = self.client.post(url, data, REMOTE_ADDR=utils.generateRandomIPv4Address())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(len(mail.outbox), outboxlen + 1)

        user = models.User.objects.get(email=data['email'])
        self.assertTrue(user.get_or_create_first_token() in mail.outbox[-1].body)
