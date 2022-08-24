from datetime import datetime, timedelta

from pyotp import TOTP
from rest_framework import status

from desecapi.tests.base import DomainOwnerTestCase


class TOTPFactorTestCase(DomainOwnerTestCase):
    def setUp(self):
        super().setUp()
        # Make the token a log-in token
        self.token.perm_manage_tokens = True
        self.token.mfa = False
        self.token.save()

    def _assertTOTP(self, totp, name):
        self.assertEqual(
            totp.keys(), {"id", "created", "last_used", "name", "secret", "uri"}
        )
        self.assertEqual(totp["name"], name)
        self.assertIsNone(totp["last_used"])
        self.assertRegex(totp["secret"], r"^[A-Z0-9]{52}$")  # 32 bytes make 52 chars
        self.assertRegex(
            totp["uri"], r"^otpauth://totp/.*:.*[?]secret=[A-Z0-9]{52}&issuer=.*$"
        )

    def _decrement_timestep(self, offset):
        factor = self.owner.basefactor_set.get().totpfactor
        factor.last_verified_timestep -= offset
        factor.save()

    def _test_MFA_permission_status(self, assertion):
        for method, view_names in {
            self.client.get: [
                "v1:account",
                "v1:domain-list",
                "v1:token-list",
            ],
            self.client.post: [
                "v1:domain-list",
                "v1:token-list",
                "v1:totp-list",
            ],
        }.items():
            for view_name in view_names:
                response = method(self.reverse(view_name))
                assertion(response.status_code, status.HTTP_403_FORBIDDEN)
        for view_name in [
            "v1:domain-detail",
            "v1:rrsets",
        ]:
            for method in [self.client.get, self.client.post]:
                response = method(self.reverse(view_name, name=self.my_domain))
                assertion(response.status_code, status.HTTP_403_FORBIDDEN)
        for method in [self.client.get, self.client.post]:
            response = method(
                self.reverse("v1:rrset@", name=self.my_domain, subname="", type="NS")
            )
            assertion(response.status_code, status.HTTP_403_FORBIDDEN)

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
        self._assertTOTP(totp, "")
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

        # Correct code allows activation
        credentials_changed = self.owner.credentials_changed
        self.client.credentials()
        response = self.client.post(url, {"code": authenticator.at(now)})
        self.assertResponse(
            response,
            status.HTTP_200_OK,
            {"detail": "Your TOTP token has been activated!"},
        )
        self.assertTrue(self.owner.mfa_enabled)
        self.owner.refresh_from_db()

        # Successful verification activates MFA and registers credential change
        self.assertTrue(self.owner.mfa_enabled)
        self.assertGreater(self.owner.credentials_changed, credentials_changed)

        # Anonymous verification only allowed for activation
        response = self.client.post(url, {"code": authenticator.at(now)})
        self.assertResponse(response, status.HTTP_401_UNAUTHORIZED)

        # Token has not yet passed MFA, but GET'ing TOTP list is allowed
        self.assertTrue(self.token.mfa == False)  # assertFalse also allows None
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.plain)
        response = self.client.get(self.reverse("v1:totp-list"))
        self.assertResponse(response, status.HTTP_200_OK)

        # MFA required
        self._test_MFA_permission_status(self.assertEqual)

        # Verification sets token step-up
        self._decrement_timestep(1)
        response = self.client.post(url, {"code": authenticator.at(now)})
        self.assertResponse(response, status.HTTP_200_OK)
        self.token.refresh_from_db()
        self.assertTrue(self.token.mfa)

        # MFA passed
        self._test_MFA_permission_status(self.assertNotEqual)

        # Graceful validation window
        self._decrement_timestep(2)
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

        # Additional token needs unique name
        response = self.client.post(self.reverse("v1:totp-list"))
        self.assertResponse(
            response,
            status.HTTP_400_BAD_REQUEST,
            {
                "non_field_errors": [
                    "An authentication factor with this name already exists."
                ]
            },
        )

        # When MFA is enabled, new TOTP factors are returned directly
        response = self.client.post(self.reverse("v1:totp-list"), data={"name": "test"})
        self.assertResponse(response, status.HTTP_201_CREATED)
        totp2 = response.data
        self._assertTOTP(totp2, "test")

        # Activation of additional factor doesn't change user state
        credentials_changed = self.owner.credentials_changed
        authenticator = TOTP(totp2["secret"], digits=6)
        url = self.reverse("v1:totp-detail", pk=totp2["id"]) + "verify/"
        response = self.client.post(url, {"code": authenticator.at(now)})
        self.assertResponse(
            response,
            status.HTTP_200_OK,
            {"detail": "Your TOTP token has been activated!"},
        )
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.credentials_changed, credentials_changed)

        # Removal disables MFA
        self.assertTrue(self.owner.mfa_enabled)
        for pk in (totp["id"], totp2["id"]):
            url = self.reverse("v1:totp-detail", pk=pk)
            self.client.delete(url)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.mfa_enabled)
        self.assertGreater(self.owner.credentials_changed, credentials_changed)
