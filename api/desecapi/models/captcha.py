from __future__ import annotations

import secrets
import string
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin

from desecapi import metrics


def captcha_default_content(kind: str) -> str:
    if kind == Captcha.Kind.IMAGE:
        alphabet = (string.ascii_uppercase + string.digits).translate(
            {ord(c): None for c in "IO0"}
        )
        length = 5
    elif kind == Captcha.Kind.AUDIO:
        alphabet = string.digits
        length = 8
    else:
        raise ValueError(f"Unknown Captcha kind: {kind}")

    content = "".join([secrets.choice(alphabet) for _ in range(length)])
    metrics.get("desecapi_captcha_content_created").labels(kind).inc()
    return content


class Captcha(ExportModelOperationsMixin("Captcha"), models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image"
        AUDIO = "audio"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=24, default="")
    kind = models.CharField(choices=Kind.choices, default=Kind.IMAGE, max_length=24)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.content:
            self.content = captcha_default_content(self.kind)

    def verify(self, solution: str):
        age = timezone.now() - self.created
        self.delete()
        return (
            str(solution).upper().strip() == self.content  # solution correct
            and age <= settings.CAPTCHA_VALIDITY_PERIOD  # not expired
        )
