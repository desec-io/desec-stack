from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from utils import utils
from django.db import transaction
from desecapi.models import Domain
from django.core import mail
import httpretty
from django.conf import settings


class LogjamScannerTest(APITestCase):
    def testBasicSubprocess(self):
        url = reverse('scan-logjam')
        response = self.client.get(url, {'host':'google.com', 'port':'443', 'starttls':'none'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
