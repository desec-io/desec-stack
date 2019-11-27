from django.core import mail
from rest_framework import status
from rest_framework.reverse import reverse

from desecapi.tests.base import DesecTestCase


class DonationTests(DesecTestCase):

    def test_unauthorized_access(self):
        for method in [self.client.get, self.client.put, self.client.delete]:
            response = method(reverse('v1:donation'))
            self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_donation(self):
        url = reverse('v1:donation')
        data = {
            'name': 'Komplizierter Vörnämü-ßßß 马大为',
            'iban': 'DE89370400440532013000',
            'bic': 'BYLADEM1SWU',
            'amount': 123.45,
            'message': 'hi there, thank you. Also, some random chars:  ™ • ½ ¼ ¾ ⅓ ⅔ † ‡ µ ¢ £ € « » ♤ ♧ ♥ ♢ ¿ ',
            'email': 'email@example.com',
        }
        response = self.client.post(url, data)
        self.assertTrue(mail.outbox)
        email_internal = str(mail.outbox[0].message())
        direct_debit = str(mail.outbox[0].attachments[0][1])
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.data['iban'], data['iban'])
        self.assertTrue('Komplizierter Vornamu' in direct_debit)
        self.assertTrue(data['iban'] in email_internal)
