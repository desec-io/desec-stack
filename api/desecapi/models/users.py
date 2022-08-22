from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import CIEmailField
from django.core.mail import EmailMessage, get_connection
from django.db import models
from django.template.loader import get_template
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin

from desecapi import logger, metrics


class MyUserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(ExportModelOperationsMixin("User"), AbstractBaseUser):
    @staticmethod
    def _limit_domains_default():
        return settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = CIEmailField(
        verbose_name="email address",
        unique=True,
    )
    email_verified = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, null=True)
    is_admin = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    credentials_changed = models.DateTimeField(auto_now_add=True)
    limit_domains = models.PositiveIntegerField(
        default=_limit_domains_default.__func__, null=True, blank=True
    )
    needs_captcha = models.BooleanField(default=True)
    outreach_preference = models.BooleanField(default=True)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    # noinspection PyMethodMayBeStatic
    def has_perm(self, *_):
        """Does the user have a specific permission?"""
        # Simplest possible answer: Yes, always
        return True

    # noinspection PyMethodMayBeStatic
    def has_module_perms(self, *_):
        """Does the user have permissions to view the app `app_label`?"""
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        """Is the user a member of staff?"""
        # Simplest possible answer: All admins are staff
        return self.is_admin

    def activate(self):
        self.is_active = True
        self.needs_captcha = False
        self.save()

    def change_email(self, email):
        old_email = self.email
        self.email = email
        self.credentials_changed = timezone.now()
        self.validate_unique()
        self.save()

        self.send_email("change-email-confirmation-old-email", recipient=old_email)

    def change_password(self, raw_password):
        self.set_password(raw_password)
        self.credentials_changed = timezone.now()
        self.save()
        self.send_email("password-change-confirmation")

    def delete(self):
        pk = self.pk
        ret = super().delete()
        logger.warning(f"User {pk} deleted")
        return ret

    def send_email(
        self, reason, context=None, recipient=None, subject=None, template=None
    ):
        fast_lane = "email_fast_lane"
        slow_lane = "email_slow_lane"
        immediate_lane = "email_immediate_lane"
        lanes = {
            "activate-account": slow_lane,
            "change-email": slow_lane,
            "change-email-confirmation-old-email": fast_lane,
            "change-outreach-preference": slow_lane,
            "confirm-account": slow_lane,
            "password-change-confirmation": fast_lane,
            "reset-password": fast_lane,
            "delete-account": fast_lane,
            "domain-dyndns": fast_lane,
            "renew-domain": immediate_lane,
        }
        if reason not in lanes:
            raise ValueError(
                f"Cannot send email to user {self.pk} without a good reason: {reason}"
            )

        context = context or {}
        template = template or get_template(f"emails/{reason}/content.txt")
        content = template.render(context)
        content += f"\nSupport Reference: user_id = {self.pk}\n"

        logger.warning(
            f"Queuing email for user account {self.pk} (reason: {reason}, lane: {lanes[reason]})"
        )
        num_queued = EmailMessage(
            subject=(
                subject or get_template(f"emails/{reason}/subject.txt").render(context)
            ).strip(),
            body=content,
            from_email=get_template("emails/from.txt").render(),
            to=[recipient or self.email],
            connection=get_connection(
                lane=lanes[reason], debug={"user": self.pk, "reason": reason}
            ),
        ).send()
        metrics.get("desecapi_messages_queued").labels(
            reason, self.pk, lanes[reason]
        ).observe(num_queued)
        return num_queued
