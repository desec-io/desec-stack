# coding: utf-8
from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .utils import utils
from django.db import transaction
from desecapi.models import Domain
from django.core import mail
import httpretty
from django.conf import settings


class UnsuccessfulDonationTests(APITestCase):
    def testExpectUnauthorizedOnGet(self):
        url = reverse('donation')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testExpectUnauthorizedOnPut(self):
        url = reverse('donation')
        response = self.client.put(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testExpectUnauthorizedOnDelete(self):
        url = reverse('donation')
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class SuccessfulDonationTests(APITestCase):
    def testCanPostDonations(self):
        url = reverse('donation')
        data = \
            {
                'name': u'KÖmplißier你好ter Vornamö',
                'iban': 'DE89370400440532013000',
                'bic': 'BYLADEM1SWU',
                'amount': 123.45,
                'message': u'hi there, thank you. Also, some random special chars: ß, ä, é, µ, 我爱你',
                'email': 'email@example.com',
            }
        response = self.client.post(url, data)
        email_internal = str(mail.outbox[0].message())
        direct_debit = str(mail.outbox[0].attachments[0][1])
        email_external = str(mail.outbox[1].message())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.data['iban'], 'DE8937xxx')
        self.assertTrue('KOmpliierter Vornamo' in direct_debit)
        self.assertTrue(data['iban'] in email_internal)
