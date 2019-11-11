from __future__ import annotations

import json
import logging
import random
import secrets
import string
import time
import uuid
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta
from os import urandom

import psl_dns
import rest_framework.authtoken.models
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, AnonymousUser
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.signing import Signer
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Manager, Q
from django.template.loader import get_template
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import APIException

from desecapi import pdns

logger = logging.getLogger(__name__)
psl = psl_dns.PSL(resolver=settings.PSL_RESOLVER)


def validate_lower(value):
    if value != value.lower():
        raise ValidationError('Invalid value (not lowercase): %(value)s',
                              code='invalid',
                              params={'value': value})


def validate_upper(value):
    if value != value.upper():
        raise ValidationError('Invalid value (not uppercase): %(value)s',
                              code='invalid',
                              params={'value': value})


class MyUserManager(BaseUserManager):
    def create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(email, password=password)
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(
        verbose_name='email address',
        max_length=191,
        unique=True,
    )
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    limit_domains = models.IntegerField(default=settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT, null=True, blank=True)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
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
        self.save()

    def change_email(self, email):
        old_email = self.email
        self.email = email
        self.validate_unique()
        self.save()

        self.send_email('change-email-confirmation-old-email', recipient=old_email)

    def change_password(self, raw_password):
        self.set_password(raw_password)
        self.save()
        self.send_email('password-change-confirmation')

    def send_email(self, reason, context=None, recipient=None):
        fast_lane = 'email_fast_lane'
        slow_lane = 'email_slow_lane'
        lanes = {
            'activate': slow_lane,
            'activate-with-domain': slow_lane,
            'change-email': slow_lane,
            'change-email-confirmation-old-email': fast_lane,
            'password-change-confirmation': fast_lane,
            'reset-password': fast_lane,
            'delete-user': fast_lane,
            'domain-dyndns': fast_lane,
        }
        if reason not in lanes:
            raise ValueError(f'Cannot send email to user {self.pk} without a good reason: {reason}')

        context = context or {}
        content = get_template(f'emails/{reason}/content.txt').render(context)
        footer = get_template('emails/footer.txt').render()

        logger.warning(f'Queuing email for user account {self.pk} (reason: {reason})')
        return EmailMessage(
            subject=get_template(f'emails/{reason}/subject.txt').render(context).strip(),
            body=content + footer,
            from_email=get_template('emails/from.txt').render(),
            to=[recipient or self.email],
            connection=get_connection(lane=lanes[reason], debug={'user': self.pk, 'reason': reason})
        ).send()


class Token(rest_framework.authtoken.models.Token):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField("Key", max_length=128, db_index=True, unique=True)
    user = models.ForeignKey(
        User, related_name='auth_tokens',
        on_delete=models.CASCADE, verbose_name="User"
    )
    name = models.CharField("Name", max_length=64, default="")
    plain = None

    def generate_key(self):
        self.plain = urlsafe_b64encode(urandom(21)).decode()
        self.key = Token.make_hash(self.plain)
        return self.key

    @staticmethod
    def make_hash(plain):
        return make_password(plain, salt='static', hasher='pbkdf2_sha256_iter1')


validate_domain_name = [
    validate_lower,
    RegexValidator(
        regex=r'^[a-z0-9_.-]*[a-z]$',
        message='Invalid value (not a DNS name).',
        code='invalid_domain_name'
    )
]


def get_minimum_ttl_default():
    return settings.MINIMUM_TTL_DEFAULT


class Domain(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=191,
                            unique=True,
                            validators=validate_domain_name)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='domains')
    published = models.DateTimeField(null=True, blank=True)
    minimum_ttl = models.PositiveIntegerField(default=get_minimum_ttl_default)

    @classmethod
    def is_registrable(cls, domain_name: str, user: User):
        """
        Returns False in any of the following cases:
        (a) the domain_name appears on the public suffix list,
        (b) the domain is descendant to a zone that belongs to any user different from the given one,
            unless it's parent is a public suffix, either through the Internet PSL or local settings.
        Otherwise, True is returned.
        """
        if domain_name != domain_name.lower():
            raise ValueError

        try:
            public_suffix = psl.get_public_suffix(domain_name)
            is_public_suffix = psl.is_public_suffix(domain_name)
        except psl_dns.exceptions.UnsupportedRule as e:
            # It would probably be fine to just return True (with the TLD acting as the
            # public suffix and setting both public_suffix and is_public_suffix accordingly).
            # However, in order to allow to investigate the situation, it's better not catch
            # this exception. For web requests, our error handler turns it into a 503 error
            # and makes sure admins are notified.
            raise e

        if not is_public_suffix:
            # Take into account that any of the parent domains could be a local public suffix. To that
            # end, identify the longest local public suffix that is actually a suffix of domain_name.
            # Then, override the global PSL result.
            for local_public_suffix in settings.LOCAL_PUBLIC_SUFFIXES:
                has_local_public_suffix_parent = ('.' + domain_name).endswith('.' + local_public_suffix)
                if has_local_public_suffix_parent and len(local_public_suffix) > len(public_suffix):
                    public_suffix = local_public_suffix
                    is_public_suffix = (public_suffix == domain_name)

        if is_public_suffix and domain_name not in settings.LOCAL_PUBLIC_SUFFIXES:
            return False

        # Generate a list of all domains connecting this one and its public suffix.
        # If another user owns a zone with one of these names, then the requested
        # domain is unavailable because it is part of the other user's zone.
        private_components = domain_name.rsplit(public_suffix, 1)[0].rstrip('.')
        private_components = private_components.split('.') if private_components else []
        private_components += [public_suffix]
        private_domains = ['.'.join(private_components[i:]) for i in range(0, len(private_components) - 1)]
        assert is_public_suffix or domain_name == private_domains[0]

        # Deny registration for non-local public suffixes and for domains covered by other users' zones
        user = user if not isinstance(user, AnonymousUser) else None
        return not cls.objects.filter(Q(name__in=private_domains) & ~Q(owner=user)).exists()

    @property
    def keys(self):
        return pdns.get_keys(self)

    @property
    def is_locally_registrable(self):
        return self.parent_domain_name in settings.LOCAL_PUBLIC_SUFFIXES

    @property
    def parent_domain_name(self):
        return self._partitioned_name[1]

    @property
    def _partitioned_name(self):
        subname, _, parent_name = self.name.partition('.')
        return subname, parent_name or None

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def update_delegation(self, child_domain: Domain):
        child_subname, child_domain_name = child_domain._partitioned_name
        if self.name != child_domain_name:
            raise ValueError('Cannot update delegation of %s as it is not an immediate child domain of %s.' %
                             (child_domain.name, self.name))

        if child_domain.pk:
            # Domain real: set delegation
            child_keys = child_domain.keys
            if not child_keys:
                raise APIException('Cannot delegate %s, as it currently has no keys.' % child_domain.name)

            RRset.objects.create(domain=self, subname=child_subname, type='NS', ttl=3600, contents=settings.DEFAULT_NS)
            RRset.objects.create(domain=self, subname=child_subname, type='DS', ttl=300,
                                 contents=[ds for k in child_keys for ds in k['ds']])
        else:
            # Domain not real: remove delegation
            for rrset in self.rrset_set.filter(subname=child_subname, type__in=['NS', 'DS']):
                rrset.delete()

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('created',)


def get_default_value_created():
    return timezone.now()


def get_default_value_due():
    return timezone.now() + timedelta(days=7)


def get_default_value_mref():
    return "ONDON" + str(time.time())


class Donation(models.Model):
    created = models.DateTimeField(default=get_default_value_created)
    name = models.CharField(max_length=255)
    iban = models.CharField(max_length=34)
    bic = models.CharField(max_length=11)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    message = models.CharField(max_length=255, blank=True)
    due = models.DateTimeField(default=get_default_value_due)
    mref = models.CharField(max_length=32, default=get_default_value_mref)
    email = models.EmailField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        self.iban = self.iban[:6] + "xxx"  # do NOT save account details
        super().save(*args, **kwargs)

    class Meta:
        ordering = ('created',)


class RRsetManager(Manager):
    def create(self, contents=None, **kwargs):
        rrset = super().create(**kwargs)
        for content in contents or []:
            RR.objects.create(rrset=rrset, content=content)
        return rrset


class RRset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True)  # undocumented, used for debugging only
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    subname = models.CharField(
        max_length=178,
        blank=True,
        validators=[
            validate_lower,
            RegexValidator(
                regex=r'^([*]|(([*][.])?[a-z0-9_.-]*))$',
                message='Subname can only use (lowercase) a-z, 0-9, ., -, and _, '
                        'may start with a \'*.\', or just be \'*\'.',
                code='invalid_subname'
            )
        ]
    )
    type = models.CharField(
        max_length=10,
        validators=[
            validate_upper,
            RegexValidator(
                regex=r'^[A-Z][A-Z0-9]*$',
                message='Type must be uppercase alphanumeric and start with a letter.',
                code='invalid_type'
            )
        ]
    )
    ttl = models.PositiveIntegerField()

    objects = RRsetManager()

    DEAD_TYPES = ('ALIAS', 'DNAME')
    RESTRICTED_TYPES = ('SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM', 'OPT')

    class Meta:
        unique_together = (("domain", "subname", "type"),)

    @staticmethod
    def construct_name(subname, domain_name):
        return '.'.join(filter(None, [subname, domain_name])) + '.'

    @property
    def name(self):
        return self.construct_name(self.subname, self.domain.name)

    def save(self, *args, **kwargs):
        self.updated = timezone.now()
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return '<RRSet domain=%s type=%s subname=%s>' % (self.domain.name, self.type, self.subname)


class RRManager(Manager):
    def bulk_create(self, rrs, **kwargs):
        ret = super().bulk_create(rrs, **kwargs)

        # For each rrset, save once to set RRset.updated timestamp and trigger signal for post-save processing
        rrsets = {rr.rrset for rr in rrs}
        for rrset in rrsets:
            rrset.save()

        return ret


class RR(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name='records')
    # max_length is determined based on the calculation in
    # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
    content = models.CharField(max_length=4092)

    objects = RRManager()

    def __str__(self):
        return '<RR %s>' % self.content


class AuthenticatedAction(models.Model):
    """
    Represents a procedure call on a defined set of arguments.

    Subclasses can define additional arguments by adding Django model fields and must define the action to be taken by
    implementing the `act` method.

    AuthenticatedAction provides the `mac` property that returns a Message Authentication Code (MAC) based on the
    state. By default, the state contains the action's name (defined by the `name` property) and a timestamp; the
    state can be extended by (carefully) overriding the `_mac_state` property. Any AuthenticatedAction instance of
    the same subclass and state will deterministically have the same MAC, effectively allowing authenticated
    procedure calls by third parties according to the following protocol:

    (1) Instantiate the AuthenticatedAction subclass representing the action to be taken with the desired state,
    (2) provide information on how to instantiate the instance and the MAC to a third party,
    (3) when provided with data that allows instantiation and a valid MAC, take the defined action, possibly with
        additional parameters chosen by the third party that do not belong to the verified state.
    """
    created = models.PositiveIntegerField(default=lambda: int(datetime.timestamp(timezone.now())))

    class Meta:
        managed = False

    def __init__(self, *args, **kwargs):
        # silently ignore any value supplied for the mac value, that makes it easier to use with DRF serializers
        kwargs.pop('mac', None)
        super().__init__(*args, **kwargs)

    @property
    def mac(self):
        """
        Deterministically generates a message authentication code (MAC) for this action, based on the state as defined
        by `self._mac_state`. Identical state is guaranteed to yield identical MAC.
        :return:
        """
        return Signer().signature(json.dumps(self._mac_state))

    def validate_mac(self, mac):
        """
        Checks if the message authentication code (MAC) provided by the first argument matches the MAC of this action.
        Note that expiration is not verified by this method.
        :param mac: Message Authentication Code
        :return: True, if MAC is valid; False otherwise.
        """
        return constant_time_compare(
            mac,
            self.mac,
        )

    def is_expired(self):
        """
        Checks if the action's timestamp is older than the given validity period. Note that the message
        authentication code itself is not verified by this method.
        :return: True if expired, False otherwise.
        """
        created = datetime.fromtimestamp(self.created, tz=timezone.utc)
        return timezone.now() - created > settings.VALIDITY_PERIOD_VERIFICATION_SIGNATURE

    @property
    def _mac_state(self):
        """
        Returns a list that defines the state of this action (used for MAC calculation).

        Return value must be JSON-serializable.

        Values not included in the return value will not be used for MAC calculation, i.e. the MAC will be independent
        of them.

        Use caution when overriding this method. You will usually want to append a value to the list returned by the
        parent. Overriding the behavior altogether could result in reducing the state to fewer variables, resulting
        in valid signatures when they were intended to be invalid. The suggested method for overriding is

            @property
            def _mac_state:
                return super()._mac_state + [self.important_value, self.another_added_value]

        :return: List of values to be signed.
        """
        # TODO consider adding a "last change" attribute of the user to the state to avoid code
        #  re-use after the the state has been changed and changed back.
        name = '.'.join([self.__module__, self.__class__.__qualname__])
        return [name, self.created]

    def act(self):
        """
        Conduct the action represented by this class.
        :return: None
        """
        raise NotImplementedError


class AuthenticatedUserAction(AuthenticatedAction):
    """
    Abstract AuthenticatedAction involving an user instance, incorporating the user's id, email, password, and
    is_active flag into the Message Authentication Code state.
    """
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)

    class Meta:
        managed = False

    @property
    def _mac_state(self):
        return super()._mac_state + [self.user.id, self.user.email, self.user.password, self.user.is_active]

    def act(self):
        raise NotImplementedError


class AuthenticatedActivateUserAction(AuthenticatedUserAction):
    domain = models.CharField(max_length=191)

    class Meta:
        managed = False

    @property
    def _mac_state(self):
        return super()._mac_state + [self.domain]

    def act(self):
        self.user.activate()


class AuthenticatedChangeEmailUserAction(AuthenticatedUserAction):
    new_email = models.EmailField()

    class Meta:
        managed = False

    @property
    def _mac_state(self):
        return super()._mac_state + [self.new_email]

    def act(self):
        self.user.change_email(self.new_email)


class AuthenticatedResetPasswordUserAction(AuthenticatedUserAction):
    new_password = models.CharField(max_length=128)

    class Meta:
        managed = False

    def act(self):
        self.user.change_password(self.new_password)


class AuthenticatedDeleteUserAction(AuthenticatedUserAction):

    class Meta:
        managed = False

    def act(self):
        self.user.delete()


def captcha_default_content():
    alphabet = (string.ascii_uppercase + string.digits).translate({ord(c): None for c in 'IO0'})
    return ''.join([secrets.choice(alphabet) for _ in range(5)])


class Captcha(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(
        max_length=24,
        default=captcha_default_content,
    )

    def verify(self, solution: str):
        age = timezone.now() - self.created
        self.delete()
        return (
            str(solution).upper().strip() == self.content  # solution correct
            and
            age <= settings.CAPTCHA_VALIDITY_PERIOD  # not expired
        )
