from __future__ import annotations

import time
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin


class Donation(ExportModelOperationsMixin("Donation"), models.Model):
    @staticmethod
    def _created_default():
        return timezone.now()

    @staticmethod
    def _due_default():
        return timezone.now() + timedelta(days=7)

    @staticmethod
    def _mref_default():
        return "ONDON" + str(time.time())

    class Interval(models.IntegerChoices):
        ONCE = 0
        MONTHLY = 1
        QUARTERLY = 3
        ANNUALLY = 12

    created = models.DateTimeField(default=_created_default)
    name = models.CharField(max_length=255)
    iban = models.CharField(max_length=34)
    bic = models.CharField(max_length=11, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    message = models.CharField(max_length=255, blank=True)
    due = models.DateTimeField(default=_due_default)
    mref = models.CharField(max_length=32, default=_mref_default)
    interval = models.IntegerField(choices=Interval.choices, default=Interval.ONCE)
    email = models.EmailField(max_length=255, blank=True)

    class Meta:
        managed = False

    @property
    def interval_label(self):
        return dict(self.Interval.choices)[self.interval]
