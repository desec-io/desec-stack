from __future__ import annotations

import base64
from functools import cached_property
import secrets
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from pyotp import TOTP, utils as pyotp_utils


class BaseFactor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    name = models.CharField(blank=True, default="", max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_user_name"),
        ]

    @transaction.atomic
    def delete(self):
        if self.last_used is not None:
            self.user.save(credentials_changed=True)
        return super().delete()

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.user.mfa_enabled:  # enabling MFA
            self.user.save(credentials_changed=True)
        return super().save(*args, **kwargs)


class TOTPFactor(BaseFactor):
    @staticmethod
    def _secret_default():
        return secrets.token_bytes(32)

    secret = models.BinaryField(max_length=32, default=_secret_default.__func__)
    last_verified_timestep = models.PositiveIntegerField(default=0)

    @cached_property
    def _totp(self):
        # TODO switch to self.secret once https://github.com/pyauth/pyotp/pull/138 is released
        return TOTP(self.base32_secret, digits=6)

    @property
    def base32_secret(self):
        return base64.b32encode(self.secret).rstrip(b"=").decode("ascii")

    @property
    def uri(self):
        return self._totp.provisioning_uri(
            name=self.user.email,
            issuer_name=f"desec.{settings.DESECSTACK_DOMAIN}",
        )

    @transaction.atomic
    def verify(self, code):
        now = timezone.now()
        timestep_now = self._totp.timecode(now)

        for offset in (-1, 0, 1):
            timestep = timestep_now + offset
            if not (self.last_verified_timestep < timestep):
                continue
            if pyotp_utils.strings_equal(str(code), self._totp.generate_otp(timestep)):
                self.last_used = now
                self.last_verified_timestep = timestep
                self.save()
                return True
        return False
