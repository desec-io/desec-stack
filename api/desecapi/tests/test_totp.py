from rest_framework import status

from desecapi.tests.base import DomainOwnerTestCase


class TOTPFactorTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        # Make the token a log-in token
        self.token.perm_manage_tokens = True
        self.token.save()

    def test_workflow(self):
        # Request setting up TOTP factor
        self.client.post(self.reverse("v1:totp-list"))

        # Factor is not yet created
        self.assertFalse(self.owner.basefactor_set.exists())

        # Retrieve confirmation link
        confirmation_link = self.assertEmailSent(
            subject_contains="deSEC",
            body_contains="request to create a TOTP token",
            recipient=[self.owner.email],
            pattern=r"following link[^:]*:\s+([^\s]*)",
        )
        self.assertConfirmationLinkRedirect(confirmation_link)

        # Redeem confirmation link
        response = self.client.post(confirmation_link)
        self.assertResponse(response, status.HTTP_200_OK)
        totp = response.data
        self.assertEqual(totp.keys(), {"id", "created", "last_used", "name", "secret"})
        self.assertEqual(totp["name"], "")
        self.assertIsNone(totp["last_used"])
        self.assertRegex(totp["secret"], r"^[A-Z0-9]{52}$")  # 32 bytes make 52 chars
        self.assertEqual(
            self.owner.basefactor_set.get().totpfactor.last_verified_timestep, 0
        )

        # Can't fetch the secret
        response = self.client.get(self.reverse("v1:totp-detail", pk=totp["id"]))
        self.assertEqual(
            response.data, {k: v for k, v in totp.items() if k != "secret"}
        )

        # Ensure that MFA is not active yet
        response = self.client.get(self.reverse("v1:domain-list"))
        self.assertEqual(len(response.data), 2)
