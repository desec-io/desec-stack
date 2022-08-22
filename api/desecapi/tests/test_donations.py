from django.core import mail
from rest_framework import status
from rest_framework.reverse import reverse

from desecapi.tests.base import DesecTestCase


class DonationTests(DesecTestCase):
    def test_unauthorized_access(self):
        for method in [self.client.get, self.client.put, self.client.delete]:
            response = method(reverse("v1:donation"))
            self.assertStatus(response, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_donation_minimal(self):
        url = reverse("v1:donation")
        data = {
            "name": "Name",
            "iban": "DE89370400440532013000",
            "amount": 123.45,
        }
        response = self.client.post(url, data)
        self.assertTrue(mail.outbox)
        email_internal = str(mail.outbox[0].message())
        direct_debit = str(mail.outbox[0].attachments[0][1])
        reply_to = mail.outbox[0].reply_to
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data.keys(), {"name", "amount", "email", "mref", "interval"}
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.data["interval"], 0)
        self.assertIn("ONDON1", response.data["mref"])
        self.assertTrue("Name" in direct_debit)
        self.assertTrue(data["iban"] in email_internal)
        self.assertEqual(reply_to, [])

    def test_create_donation_verbose(self):
        url = reverse("v1:donation")
        data = {
            "name": "Komplizierter Vörnämü-ßßß 马大为",
            "iban": "DE89370400440532013000",
            "bic": "BYLADEM1SWU",
            "amount": 123.45,
            "message": "hi there, thank you. Also, some random chars:  ™ • ½ ¼ ¾ ⅓ ⅔ † ‡ µ ¢ £ € « » ♤ ♧ ♥ ♢ ¿ ",
            "email": "email@example.com",
            "interval": 3,
        }
        response = self.client.post(url, data)
        self.assertTrue(mail.outbox)
        email_internal = str(mail.outbox[0].message())
        direct_debit = str(mail.outbox[0].attachments[0][1])
        reply_to = mail.outbox[0].reply_to
        self.assertStatus(response, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data.keys(), {"name", "amount", "email", "mref", "interval"}
        )
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(response.data["interval"], 3)
        self.assertIn("ONDON1", response.data["mref"])
        self.assertTrue("Komplizierter Vornamu" in direct_debit)
        self.assertTrue(data["iban"] in email_internal)
        self.assertEqual(reply_to, [data["email"]])
