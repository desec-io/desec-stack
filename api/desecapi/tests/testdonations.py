from rest_framework.reverse import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core import mail


class UnsuccessfulDonationTests(APITestCase):
    def testExpectUnauthorizedOnGet(self):
        url = reverse('v1:donation')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testExpectUnauthorizedOnPut(self):
        url = reverse('v1:donation')
        response = self.client.put(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def testExpectUnauthorizedOnDelete(self):
        url = reverse('v1:donation')
        response = self.client.delete(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class SuccessfulDonationTests(APITestCase):
    def testCanPostDonations(self):
        url = reverse('v1:donation')
        data = \
            {
                'name': 'Komplizierter Vörnämü-ßßß 马大为',
                'iban': 'DE89370400440532013000',
                'bic': 'BYLADEM1SWU',
                'amount': 123.45,
                'message': 'hi there, thank you. Also, some random chars:  ™ • ½ ¼ ¾ ⅓ ⅔ † ‡ µ ¢ £ € « » ♤ ♧ ♥ ♢ ¿ ',
                'email': 'email@example.com',
            }
        response = self.client.post(url, data)
        self.assertTrue(len(mail.outbox) > 0)
        email_internal = str(mail.outbox[0].message())
        direct_debit = str(mail.outbox[0].attachments[0][1])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.data['iban'], 'DE8937xxx')
        self.assertTrue('Komplizierter Vornamu' in direct_debit)
        self.assertTrue(data['iban'] in email_internal)
