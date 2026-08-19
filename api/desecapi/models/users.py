from __future__ import annotations

import math
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
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
        # No longer used as a field default (limit_domains defaults to null,
        # i.e. to the computed limit), but referenced by historical migrations.
        return settings.DOMAIN_LIMIT_INSECURE_HEADROOM

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        verbose_name="email address",
        db_collation="case_insensitive",  # LIKE queries: LOWER(email COLLATE "und-x-icu") LIKE '%...%'
        unique=True,
    )
    email_verified = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(db_index=True, default=True, null=True)
    is_admin = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    credentials_changed = models.DateTimeField(auto_now_add=True)
    # Null means the limit is computed from the user's securely delegated
    # domains (see effective_limit_domains); a value pins it, e.g. because
    # support granted one. Never enforced directly -- go through the property.
    limit_domains = models.PositiveIntegerField(null=True, blank=True)
    needs_captcha = models.BooleanField(default=True)
    outreach_preference = models.BooleanField(default=True)
    throttle_daily_rate = models.PositiveIntegerField(null=True)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [models.Index(fields=["last_login"])]

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

    @property
    def mfa_enabled(self):
        return self.basefactor_set.exclude(last_used__isnull=True).exists()

    @property
    def secure_domain_count(self):
        """
        How many of the user's domains are securely delegated to us, i.e. reach
        us through an intact chain of trust.

        Includes domains under one of our own public suffixes, which are secure
        by construction: we host and sign every zone between them and the public
        root. They are counted without being measured, which is why the sweep
        does not have to look at them.
        """
        return self.domains.securely_delegated().count()

    @property
    def secure_external_domain_count(self):
        """
        The part of secure_domain_count the user actually configured: domains
        delegated to us from a parent zone we do not operate.
        """
        return (
            self.domains.securely_delegated()
            .exclude_under_local_public_suffix()
            .count()
        )

    @property
    def effective_limit_domains(self):
        """
        The domain limit that is actually enforced: the explicit one where
        support has set it, and otherwise one derived from the domains the user
        has securely delegated to us.

        Two terms, counting different things.

        Every securely delegated domain pays for its own slot, those under our
        own public suffixes included: they are secure by construction, and a
        delegation that is in perfect order earns its slot like any other.

        The headroom on top is how many domains may be held *without* being
        secured. DOMAIN_LIMIT_INSECURE_HEADROOM is its floor, so an account
        that has demonstrated nothing still gets exactly what it always got;
        above that, headroom is earned, and only by externally delegated
        domains. A domain under our own public suffix arrives secure, so it
        moves both s and the limit by exactly one and earns no headroom.

        Being sublinear, the headroom shrinks as a fraction of the limit, so the
        incentive to enable DNSSEC does not dilute as a portfolio grows -- while
        every external domain secured still raises the limit, by one or two.
        round() never sees a tie here: sqrt(e) is an integer for square e and
        irrational otherwise.
        """
        if self.limit_domains is not None:
            return self.limit_domains
        headroom = round(math.sqrt(self.secure_external_domain_count))
        return self.secure_domain_count + max(
            settings.DOMAIN_LIMIT_INSECURE_HEADROOM, headroom
        )

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

    def delete(self, *args, **kwargs):
        pk = self.pk
        ret = super().delete(*args, **kwargs)
        logger.warning(f"User {pk} deleted")
        return ret

    def save(self, *args, **kwargs):
        if kwargs.pop("credentials_changed", False):
            self.credentials_changed = timezone.now()
            # https://docs.djangoproject.com/en/4.2/releases/4.2/#setting-update-fields-in-model-save-may-now-be-required
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {"credentials_changed"}.union(
                    kwargs["update_fields"]
                )
        super().save(*args, **kwargs)

    def send_email(
        self, reason, context=None, recipient=None, subject=None, template=None
    ):
        fast_lane = "email_fast_lane"
        slow_lane = "email_slow_lane"
        immediate_lane = "email_immediate_lane"
        lanes = {
            "activate-account": slow_lane,
            "activate-account-with-override-token": fast_lane,
            "change-email": slow_lane,
            "change-email-confirmation-old-email": fast_lane,
            "change-outreach-preference": slow_lane,
            "confirm-account": slow_lane,
            "create-totp": fast_lane,
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
