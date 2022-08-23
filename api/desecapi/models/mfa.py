from __future__ import annotations

import base64
import secrets
import uuid

from django.db import models, transaction
from django.utils import timezone


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

    @transaction.atomic()
    def delete(self):
        if self.last_used is not None:
            self.user.credentials_changed = timezone.now()
            self.user.save()
        return super().delete()


class TOTPFactor(BaseFactor):
    @staticmethod
    def _secret_default():
        return secrets.token_bytes(32)

    secret = models.BinaryField(max_length=32, default=_secret_default.__func__)
    last_verified_timestep = models.PositiveIntegerField(default=0)

    @property
    def base32_secret(self):
        return base64.b32encode(self.secret).rstrip(b"=").decode("ascii")
