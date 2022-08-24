from datetime import datetime, timedelta

from pyotp import TOTP
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
        self.assertEqual(
            totp.keys(), {"id", "created", "last_used", "name", "secret", "uri"}
        )
        self.assertEqual(totp["name"], "")
        self.assertIsNone(totp["last_used"])
        self.assertRegex(totp["secret"], r"^[A-Z0-9]{52}$")  # 32 bytes make 52 chars
        self.assertResponse(
            self.assertRegex(
                totp["uri"],
                r"^otpauth://totp/.*:Secret[?]secret=[A-Z0-9]{52}&issuer=.*$",
            )
        )
        self.assertEqual(
            self.owner.basefactor_set.get().totpfactor.last_verified_timestep, 0
        )

        # Can't fetch the secret
        response = self.client.get(self.reverse("v1:totp-detail", pk=totp["id"]))
        self.assertEqual(
            response.data, {k: v for k, v in totp.items() if k not in ("secret", "uri")}
        )

        # Ensure that MFA is not active yet
        response = self.client.get(self.reverse("v1:domain-list"))
        self.assertEqual(len(response.data), 2)
        self.assertFalse(self.owner.mfa_enabled)

        # Verify requires a code
        url = self.reverse("v1:totp-detail", pk=totp["id"]) + "verify/"
        response = self.client.post(url)
        self.assertResponse(
            response, status.HTTP_400_BAD_REQUEST, {"code": ["This field is required."]}
        )

        # Wrong code won't work
        now = datetime.now()
        step = timedelta(seconds=30)
        authenticator = TOTP(totp["secret"], digits=6)
        url = self.reverse("v1:totp-detail", pk=totp["id"]) + "verify/"
        for message, codes in {
            "This field may not be blank.": [""],
            "Invalid code.": [
                "000000",
                authenticator.at(now - 2 * step),
                authenticator.at(now + 2 * step),
            ],
        }.items():
            for code in codes:
                response = self.client.post(url, {"code": code})
                self.assertResponse(
                    response, status.HTTP_400_BAD_REQUEST, {"code": [message]}
                )

        # Correct code works
        credentials_changed = self.owner.credentials_changed
        response = self.client.post(url, {"code": authenticator.at(now)})
        self.assertResponse(
            response, status.HTTP_200_OK, {"detail": "The code was correct."}
        )
        self.assertTrue(self.owner.mfa_enabled)
        self.owner.refresh_from_db()

        # Successful verification activates MFA and registers credential change
        self.assertTrue(self.owner.mfa_enabled)
        self.assertGreater(self.owner.credentials_changed, credentials_changed)

        # Graceful validation window
        factor = self.owner.basefactor_set.get().totpfactor
        factor.last_verified_timestep -= 2
        factor.save()
        window_codes = [authenticator.at(now + i * step) for i in (-1, 0, 1)]
        for code in window_codes:
            response = self.client.post(url, {"code": code})
            self.assertResponse(
                response, status.HTTP_200_OK, {"detail": "The code was correct."}
            )

        # Replay won't work
        for code in window_codes:
            response = self.client.post(url, {"code": code})
            self.assertResponse(
                response, status.HTTP_400_BAD_REQUEST, {"code": ["Invalid code."]}
            )
