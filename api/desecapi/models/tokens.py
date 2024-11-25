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
from django.db.models.fields.related import ForeignObject
from django.db.models.functions import Coalesce
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin
from netfields import CidrAddressField, NetManager

from desecapi.models import RRset


# No 0OIl characters, non-alphanumeric only (select by double-click no line-break)
# https://github.com/bitcoin/bitcoin/blob/master/src/base58.h
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


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
    owner = models.ForeignKey("User", on_delete=models.CASCADE, related_name="+")
    user_id = models.GeneratedField(
        expression=Coalesce("user_override", "owner"),
        output_field=models.UUIDField(),
        db_index=True,
        db_persist=True,
    )
    user = ForeignObject(
        "User",
        on_delete=models.CASCADE,
        from_fields=["user_id"],
        to_fields=["id"],
        null=True,
        related_name="token_set",
    )
    user_override = models.ForeignKey(
        "User", on_delete=models.CASCADE, null=True, related_name="+"
    )
    name = models.CharField("Name", blank=True, max_length=64)
    last_used = models.DateTimeField(null=True, blank=True)
    mfa = models.BooleanField(default=None, null=True)
    perm_create_domain = models.BooleanField(default=False)
    perm_delete_domain = models.BooleanField(default=False)
    perm_manage_tokens = models.BooleanField(default=False)
    allowed_subnets = ArrayField(
        CidrAddressField(), default=_allowed_subnets_default.__func__
    )
    max_age = models.DurationField(null=True, default=None, validators=_validators)
    max_unused_period = models.DurationField(
        null=True, default=None, validators=_validators
    )
    domain_policies = models.ManyToManyField("Domain", through="TokenDomainPolicy")
    auto_policy = models.BooleanField(default=False)

    plain = None
    objects = NetManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "user_id"], name="unique_id_user"),
            models.CheckConstraint(
                condition=Q(user_override__isnull=True)
                | (
                    Q(perm_manage_tokens=False, mfa__isnull=True)
                    & ~Q(user_override=F("owner"))
                ),
                name="user_override_conditions",
            ),
        ]
        triggers = [
            # Ensure that a default policy is defined when auto_policy=true
            pgtrigger.Trigger(
                name="token_auto_policy",
                operation=pgtrigger.Insert | pgtrigger.UpdateOf("auto_policy"),
                when=pgtrigger.After,
                timing=pgtrigger.Deferred,
                func=pgtrigger.Func(
                    """
                    IF
                        NEW.auto_policy = true AND NOT EXISTS(
                            SELECT * FROM {meta.many_to_many[0].remote_field.through._meta.db_table} WHERE token_id = NEW.id AND domain_id IS NULL AND subname IS NULL AND type IS NULL
                        )
                    THEN
                        RAISE EXCEPTION 'Token auto policy without a default policy is not allowed. (token.id=%)', NEW.id;
                    END IF;
                    RETURN NULL;
                """
                ),
            ),
            # Update TokenDomainPolicy.token_user when .user_override changes (will fail FK if token
            # has domain-specific policies). Also protect against further .user_override changes.
            pgtrigger.Trigger(
                name="token_policy_user_id",
                operation=pgtrigger.UpdateOf("user_id"),
                condition=pgtrigger.AnyChange("user_id"),
                when=pgtrigger.After,
                func=pgtrigger.Func(
                    """
                    IF
                        OLD.user_override_id IS NOT NULL
                    THEN
                        RAISE EXCEPTION 'Cannot alter Token.user_override_id once set. (token.id=%)', NEW.id;
                    END IF;
                    UPDATE {meta.many_to_many[0].remote_field.through._meta.db_table} SET token_user_id = NEW.user_id WHERE token_id = NEW.id;
                    RETURN NULL;
                """
                ),
            ),
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
        # Entropy: len(ALPHABET) == 58, log_2(58) * 28 = 164.02
        self.plain = "".join(secrets.choice(ALPHABET) for _ in range(28))
        self.key = Token.make_hash(self.plain)
        return self.key

    @staticmethod
    def make_hash(plain):
        return make_password(plain, salt="static", hasher="pbkdf2_sha256_iter1")

    def get_policy(self, rrset=None):
        order_by = [
            F(field).asc(
                nulls_last=True  # default Postgres sorting, but: explicit is better than implicit
            )
            for field in ["domain", "subname", "type"]
        ]
        return (
            self.tokendomainpolicy_set.filter(
                Q(domain=rrset.domain if rrset else None) | Q(domain__isnull=True),
                Q(subname=rrset.subname if rrset else None) | Q(subname__isnull=True),
                Q(type=rrset.type if rrset else None) | Q(type__isnull=True),
            )
            .order_by(*order_by)
            .first()
        )

    def can_safely_delete_domain(self, domain):
        forbidden = (
            # Check if token is explicitly prohibited from writing some RRsets in this domain
            # (priority order 1-4, see /docs/auth/tokens.rst#token-scoping-policies)
            self.tokendomainpolicy_set.filter(domain=domain)
            .filter(perm_write=False)
            .exists()
            or
            # Check that the token has no permissive default policy for this domain
            # (priority order 4) and apply fall-through to domain-independent policies (5-8)
            (
                not self.tokendomainpolicy_set.filter(
                    domain=domain, subname=None, type=None
                )
                .filter(perm_write=True)
                .exists()
                # Fall-through. Uses a conservative approximation and does not account for
                # permissive policies of priority order 1, 2, 3 shadowing restrictive policies
                # of priority order 5, 6, 7, respectively. For details, see
                # https://github.com/desec-io/desec-stack/pull/990#discussion_r1864977009.
                and self.tokendomainpolicy_set.filter(domain=None)
                .filter(perm_write=False)
                .exists()
            )
        )
        return not forbidden

    def clean(self):
        if self.perm_manage_tokens and self.user_override:
            # Prevent raw database constraint error from leaking
            raise ValidationError(
                {
                    "non_field_errors": [
                        "perm_manage_tokens and user_override are mutually exclusive."
                    ]
                }
            )
        if not self.auto_policy:
            return
        default_policy = self.get_policy()
        if default_policy and default_policy.perm_write:
            raise ValidationError(
                {"auto_policy": ["Auto policy requires a restrictive default policy."]}
            )

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Do not perform policy checks when only updating fields like last_used
        if kwargs.get("update_fields") != ["last_used"]:
            self.clean()
        super().save(*args, **kwargs)
        if self.auto_policy and self.get_policy() is None:
            TokenDomainPolicy(token=self).save()


class TokenDomainPolicy(ExportModelOperationsMixin("TokenDomainPolicy"), models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    domain = models.ForeignKey("Domain", on_delete=models.CASCADE, null=True)
    subname = models.CharField(
        max_length=178,
        blank=True,
        null=True,
        validators=RRset.subname.field._validators,
    )
    type = models.CharField(
        max_length=10, null=True, validators=RRset.type.field._validators
    )
    perm_write = models.BooleanField(default=False)
    # Token user, filled via trigger. Used by compound FK constraints to tie domain.owner to token.user (see migration).
    token_user = models.ForeignKey(
        "User", on_delete=models.CASCADE, db_constraint=False, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_policy",
                fields=["token", "domain", "subname", "type"],
                nulls_distinct=False,
            ),
        ]
        triggers = [
            # Ensure that token_user is consistent with token (to fulfill compound FK constraint, see migration)
            pgtrigger.Trigger(
                name="token_user_insert",
                operation=pgtrigger.Insert,
                when=pgtrigger.Before,
                func="NEW.token_user_id = (SELECT user_id FROM desecapi_token WHERE id = NEW.token_id); RETURN NEW;",
            ),
            pgtrigger.Trigger(
                name="token_user_update",
                operation=pgtrigger.UpdateOf("token_user_id"),
                when=pgtrigger.Before,
                func="""
                    IF
                        NEW.token_user_id != (SELECT user_id FROM desecapi_token WHERE id = NEW.token_id)
                    THEN
                        RAISE EXCEPTION 'Invalid token_user_id: %', NEW.token_user_id;
                    END IF;
                    RETURN NEW;
                """,
            ),
            # Ensure that if there is *any* domain policy for a given token, there is always one with domain=None.
            pgtrigger.Trigger(
                name="default_policy_primacy",
                operation=pgtrigger.Insert | pgtrigger.Update | pgtrigger.Delete,
                when=pgtrigger.After,
                timing=pgtrigger.Deferred,
                func=pgtrigger.Func(
                    """
                    IF
                        EXISTS(SELECT * FROM {meta.db_table} WHERE token_id = COALESCE(NEW.token_id, OLD.token_id)) AND NOT EXISTS(
                            SELECT * FROM {meta.db_table} WHERE token_id = COALESCE(NEW.token_id, OLD.token_id) AND domain_id IS NULL AND subname IS NULL AND type IS NULL
                        )
                    THEN
                        RAISE EXCEPTION 'Token policies without a default policy are not allowed.';
                    END IF;
                    RETURN NULL;
                """
                ),
            ),
            # Ensure default policy when auto_policy is in effect
            pgtrigger.Trigger(
                name="default_policy_when_auto_policy",
                operation=pgtrigger.Delete,
                when=pgtrigger.After,
                timing=pgtrigger.Deferred,
                func=pgtrigger.Func(
                    """
                    IF
                        OLD.domain_id IS NULL AND OLD.subname IS NULL AND OLD.type IS NULL AND (SELECT auto_policy FROM {fields.token.remote_field.model._meta.db_table} WHERE id = OLD.token_id) = true
                    THEN
                        RAISE EXCEPTION 'Cannot delete default policy while auto_policy is in effect. (tokendomainpolicy.id=%)', OLD.id;
                    END IF;
                    RETURN OLD;
                """
                ),
            ),
        ]

    @property
    def is_default_policy(self):
        default_policy = self.token.get_policy()
        return default_policy is not None and self.pk == default_policy.pk

    @property
    def represents_default_policy(self):
        return self.domain is None and self.subname is None and self.type is None

    def clean(self):
        if self._state.adding:  # create
            # Can't violate policy precedence (default policy has to be first)
            default_policy = self.token.get_policy()
            if (default_policy is None) and not self.represents_default_policy:
                raise ValidationError(
                    {
                        "non_field_errors": [
                            "Policy precedence: The first policy must be the default policy."
                        ]
                    }
                )
        else:  # update
            # Can't make non-default policy default and vice versa
            if self.is_default_policy != self.represents_default_policy:
                raise ValidationError(
                    {
                        "non_field_errors": [
                            "When using policies, there must be exactly one default policy."
                        ]
                    }
                )
            # Can't relax default policy if auto_policy is in effect
            if self.perm_write and self.is_default_policy and self.token.auto_policy:
                raise ValidationError(
                    {
                        "perm_write": [
                            "Must be false when auto_policy is in effect for the token."
                        ]
                    }
                )

    def delete(self, *args, **kwargs):
        # Can't delete default policy when others exist
        if (
            self.is_default_policy
            and self.token.tokendomainpolicy_set.exclude(pk=self.pk).exists()
        ):
            raise ValidationError(
                {
                    "non_field_errors": [
                        "Policy precedence: Can't delete default policy when there exist others."
                    ]
                }
            )
        # Can't delete default policy when auto_policy is in effect
        if self.is_default_policy and self.token.auto_policy:
            raise ValidationError(
                {
                    "non_field_errors": [
                        "Can't delete default policy when auto_policy is in effect for the token."
                    ]
                }
            )
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
