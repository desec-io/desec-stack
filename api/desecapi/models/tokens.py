from __future__ import annotations

import ipaddress
import secrets
import uuid
from datetime import timedelta

import pgtrigger
import rest_framework.authtoken.models
from django.contrib.auth.hashers import make_password
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin
from netfields import CidrAddressField, NetManager


class Token(ExportModelOperationsMixin("Token"), rest_framework.authtoken.models.Token):
    @staticmethod
    def _allowed_subnets_default():
        return [ipaddress.IPv4Network("0.0.0.0/0"), ipaddress.IPv6Network("::/0")]

    _validators = [
        validators.MinValueValidator(timedelta(0)),
        validators.MaxValueValidator(timedelta(days=365 * 1000)),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField("Key", max_length=128, db_index=True, unique=True)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    name = models.CharField("Name", blank=True, max_length=64)
    last_used = models.DateTimeField(null=True, blank=True)
    perm_manage_tokens = models.BooleanField(default=False)
    allowed_subnets = ArrayField(
        CidrAddressField(), default=_allowed_subnets_default.__func__
    )
    max_age = models.DurationField(null=True, default=None, validators=_validators)
    max_unused_period = models.DurationField(
        null=True, default=None, validators=_validators
    )
    domain_policies = models.ManyToManyField("Domain", through="TokenDomainPolicy")

    plain = None
    objects = NetManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "user"], name="unique_id_user")
        ]

    @property
    def is_valid(self):
        now = timezone.now()

        # Check max age
        try:
            if self.created + self.max_age < now:
                return False
        except TypeError:
            pass

        # Check regular usage requirement
        try:
            if (self.last_used or self.created) + self.max_unused_period < now:
                return False
        except TypeError:
            pass

        return True

    def generate_key(self):
        self.plain = secrets.token_urlsafe(21)
        self.key = Token.make_hash(self.plain)
        return self.key

    @staticmethod
    def make_hash(plain):
        return make_password(plain, salt="static", hasher="pbkdf2_sha256_iter1")

    def get_policy(self, *, domain=None):
        order_by = F("domain").asc(
            nulls_last=True
        )  # default Postgres sorting, but: explicit is better than implicit
        return (
            self.tokendomainpolicy_set.filter(Q(domain=domain) | Q(domain__isnull=True))
            .order_by(order_by)
            .first()
        )

    @transaction.atomic
    def delete(self):
        # This is needed because Model.delete() emulates cascade delete via django.db.models.deletion.Collector.delete()
        # which deletes related objects in pk order.  However, the default policy has to be deleted last.
        # Perhaps this will change with https://code.djangoproject.com/ticket/21961
        self.tokendomainpolicy_set.filter(domain__isnull=False).delete()
        self.tokendomainpolicy_set.filter(domain__isnull=True).delete()
        return super().delete()


@pgtrigger.register(
    # Ensure that token_user is consistent with token
    pgtrigger.Trigger(
        name="token_user",
        operation=pgtrigger.Update | pgtrigger.Insert,
        when=pgtrigger.Before,
        func="NEW.token_user_id = (SELECT user_id FROM desecapi_token WHERE id = NEW.token_id); RETURN NEW;",
    ),
    # Ensure that if there is *any* domain policy for a given token, there is always one with domain=None.
    pgtrigger.Trigger(
        name="default_policy_on_insert",
        operation=pgtrigger.Insert,
        when=pgtrigger.Before,
        # Trigger `condition` arguments (corresponding to WHEN clause) don't support subqueries, so we use `func`
        func="IF (NEW.domain_id IS NOT NULL and NOT EXISTS(SELECT * FROM desecapi_tokendomainpolicy WHERE domain_id IS NULL AND token_id = NEW.token_id)) THEN "
        "  RAISE EXCEPTION 'Cannot insert non-default policy into % table when default policy is not present', TG_TABLE_NAME; "
        "END IF; RETURN NEW;",
    ),
    pgtrigger.Protect(
        name="default_policy_on_update",
        operation=pgtrigger.Update,
        when=pgtrigger.Before,
        condition=pgtrigger.Q(old__domain__isnull=True, new__domain__isnull=False),
    ),
    # Ideally, a deferred trigger (https://github.com/Opus10/django-pgtrigger/issues/14). Available in 3.4.0.
    pgtrigger.Trigger(
        name="default_policy_on_delete",
        operation=pgtrigger.Delete,
        when=pgtrigger.Before,
        # Trigger `condition` arguments (corresponding to WHEN clause) don't support subqueries, so we use `func`
        func="IF (OLD.domain_id IS NULL and EXISTS(SELECT * FROM desecapi_tokendomainpolicy WHERE domain_id IS NOT NULL AND token_id = OLD.token_id)) THEN "
        "  RAISE EXCEPTION 'Cannot delete default policy from % table when non-default policy is present', TG_TABLE_NAME; "
        "END IF; RETURN OLD;",
    ),
)
class TokenDomainPolicy(ExportModelOperationsMixin("TokenDomainPolicy"), models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    domain = models.ForeignKey("Domain", on_delete=models.CASCADE, null=True)
    perm_dyndns = models.BooleanField(default=False)
    perm_rrsets = models.BooleanField(default=False)
    # Token user, filled via trigger. Used by compound FK constraints to tie domain.owner to token.user (see migration).
    token_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, db_constraint=False, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["token", "domain"], name="unique_entry"),
            models.UniqueConstraint(
                fields=["token"],
                condition=Q(domain__isnull=True),
                name="unique_entry_null_domain",
            ),
        ]

    def clean(self):
        default_policy = self.token.get_policy(domain=None)
        if self.pk:  # update
            # Can't change policy's default status ("domain NULLness") to maintain policy precedence
            if (self.domain is None) != (self.pk == default_policy.pk):
                raise ValidationError(
                    {
                        "domain": "Policy precedence: Cannot disable default policy when others exist."
                    }
                )
        else:  # create
            # Can't violate policy precedence (default policy has to be first)
            if (self.domain is not None) and (default_policy is None):
                raise ValidationError(
                    {
                        "domain": "Policy precedence: The first policy must be the default policy."
                    }
                )

    def delete(self):
        # Can't delete default policy when others exist
        if (self.domain is None) and self.token.tokendomainpolicy_set.exclude(
            domain__isnull=True
        ).exists():
            raise ValidationError(
                {
                    "domain": "Policy precedence: Can't delete default policy when there exist others."
                }
            )
        return super().delete()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
