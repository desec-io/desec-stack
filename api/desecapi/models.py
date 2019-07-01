from __future__ import annotations

import datetime
import random
import time
import uuid
from base64 import b64encode
from os import urandom

import rest_framework.authtoken.models
from django.conf import settings
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Manager
from django.utils import timezone
from rest_framework.exceptions import APIException

from desecapi import pdns


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
    def create_user(self, email, password=None, registration_remote_ip=None, lock=False, dyn=False):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
            registration_remote_ip=registration_remote_ip,
            locked=timezone.now() if lock else None,
            dyn=dyn,
        )

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
    registration_remote_ip = models.CharField(max_length=1024, blank=True)
    locked = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    limit_domains = models.IntegerField(default=settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT, null=True, blank=True)
    dyn = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def get_or_create_first_token(self):
        try:
            token = Token.objects.filter(user=self).earliest('created')
        except Token.DoesNotExist:
            token = Token.objects.create(user=self)
        return token.key

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


class Token(rest_framework.authtoken.models.Token):
    key = models.CharField("Key", max_length=40, db_index=True, unique=True)
    # relation to user is a ForeignKey, so each user can have more than one token
    user = models.ForeignKey(
        User, related_name='auth_tokens',
        on_delete=models.CASCADE, verbose_name="User"
    )
    name = models.CharField("Name", max_length=64, default="")
    user_specific_id = models.BigIntegerField("User-Specific ID")

    def save(self, *args, **kwargs):
        if not self.user_specific_id:
            self.user_specific_id = random.randrange(16 ** 8)
        super().save(*args, **kwargs)  # Call the "real" save() method.

    def generate_key(self):
        return b64encode(urandom(21)).decode('utf-8').replace('/', '-').replace('=', '_').replace('+', '.')

    class Meta:
        abstract = False
        unique_together = (('user', 'user_specific_id'),)


class Domain(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=191,
                            unique=True,
                            validators=[validate_lower,
                                        RegexValidator(regex=r'^[a-z0-9_.-]*[a-z]$',
                                                       message='Domain name malformed.',
                                                       code='invalid_domain_name')
                                        ])
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='domains')
    published = models.DateTimeField(null=True, blank=True)

    @property
    def keys(self):
        return pdns.get_keys(self)

    def partition_name(self):
        subname, _, parent_name = self.name.partition('.')
        return subname, parent_name or None

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def update_delegation(self, child_domain: Domain):
        child_subname, child_domain_name = child_domain.partition_name()
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
    return timezone.now() + datetime.timedelta(days=7)


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
    updated = models.DateTimeField(null=True)
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
    ttl = models.PositiveIntegerField(validators=[MinValueValidator(1)])

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
        return '<RRSet %i domain=%s type=%s subname=%s>' % (self.pk, self.domain.name, self.type, self.subname)


class RRManager(Manager):
    def bulk_create(self, rrs, **kwargs):
        ret = super().bulk_create(rrs, **kwargs)

        # For each rrset, save once to update published timestamp and trigger signal for post-save processing
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
        return '<RR %s %s rr_set=%i>' % (self.pk, self.content, self.rrset.pk)
