from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)
from django.utils import timezone
from django.core.exceptions import ValidationError
from desecapi import pdns
import datetime, time
import django.core.exceptions
import rest_framework.exceptions
from django.core.validators import MinValueValidator


class MyUserManager(BaseUserManager):
    def create_user(self, email, password=None, registration_remote_ip=None, captcha_required=False):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
            registration_remote_ip=registration_remote_ip,
            captcha_required=captcha_required,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(email,
                                password=password
        )
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
    captcha_required = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    limit_domains = models.IntegerField(default=settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT,null=True,blank=True)
    dyn = models.BooleanField(default=True)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        # Simplest possible answer: All admins are staff
        return self.is_admin

    def unlock(self):
        self.captcha_required = False
        for domain in self.domains.all():
            domain.pdns_resync()
        self.save()


class Domain(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True)
    name = models.CharField(max_length=191, unique=True)
    arecord = models.GenericIPAddressField(protocol='IPv4', blank=False, null=True)
    aaaarecord = models.GenericIPAddressField(protocol='IPv6', blank=False, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='domains')
    acme_challenge = models.CharField(max_length=255, blank=True)
    _dirtyName = False
    _dirtyRecords = False

    def __setattr__(self, attrname, val):
        setter_func = 'setter_' + attrname
        if attrname in self.__dict__ and callable(getattr(self, setter_func, None)):
            super(Domain, self).__setattr__(attrname, getattr(self, setter_func)(val))
        else:
            super(Domain, self).__setattr__(attrname, val)

    def setter_name(self, val):
        if val != self.name:
            self._dirtyName = True

        return val

    def setter_arecord(self, val):
        if val != self.arecord:
            self._dirtyRecords = True

        return val

    def setter_aaaarecord(self, val):
        if val != self.aaaarecord:
            self._dirtyRecords = True

        return val

    def setter_acme_challenge(self, val):
        if val != self.acme_challenge:
            self._dirtyRecords = True

        return val

    def clean(self):
        if self._dirtyName:
            raise ValidationError('You must not change the domain name')

    def pdns_resync(self):
        """
        Make sure that pdns gets the latest information about this domain/zone.
        Re-Syncing is relatively expensive and should not happen routinely.
        """

        # Create zone if needed
        if not pdns.zone_exists(self.name):
            pdns.create_zone(self.name)

        # update zone to latest information
        pdns.set_dyn_records(self.name, self.arecord, self.aaaarecord, self.acme_challenge)

    def pdns_sync(self, new_domain):
        """
        Command pdns updates as indicated by the local changes.
        """

        if self.owner.captcha_required:
            # suspend all updates
            return

        # if this zone is new, create it and set dirty flag if necessary
        if new_domain:
            pdns.create_zone(self.name)
            self._dirtyRecords = bool(self.arecord) or bool(self.aaaarecord) or bool(self.acme_challenge)

        # make changes if necessary
        if self._dirtyRecords:
            pdns.set_dyn_records(self.name, self.arecord, self.aaaarecord, self.acme_challenge)

        self._dirtyRecords = False

    @transaction.atomic
    def delete(self, *args, **kwargs):
        super(Domain, self).delete(*args, **kwargs)

        pdns.delete_zone(self.name)
        if self.name.endswith('.dedyn.io'):
            pdns.set_rrset('dedyn.io', self.name, 'DS', '')
            pdns.set_rrset('dedyn.io', self.name, 'NS', '')

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Record here if this is a new domain (self.pk is only None until we call super.save())
        new_domain = self.pk is None

        self.updated = timezone.now()
        self.clean()
        super(Domain, self).save(*args, **kwargs)

        self.pdns_sync(new_domain)

    class Meta:
        ordering = ('created',)


def get_default_value_created():
    return timezone.now()


def get_default_value_due():
    return timezone.now() + datetime.timedelta(days=7)


def get_default_value_mref():
    return "ONDON" + str((timezone.now() - timezone.datetime(1970,1,1,tzinfo=timezone.utc)).total_seconds())


class Donation(models.Model):

    created = models.DateTimeField(default=get_default_value_created)
    name = models.CharField(max_length=255)
    iban = models.CharField(max_length=34)
    bic = models.CharField(max_length=11)
    amount = models.DecimalField(max_digits=8,decimal_places=2)
    message = models.CharField(max_length=255, blank=True)
    due = models.DateTimeField(default=get_default_value_due)
    mref = models.CharField(max_length=32,default=get_default_value_mref)
    email = models.EmailField(max_length=255, blank=True)


    def save(self, *args, **kwargs):
        self.iban = self.iban[:6] + "xxx" # do NOT save account details
        super(Donation, self).save(*args, **kwargs) # Call the "real" save() method.


    class Meta:
        ordering = ('created',)


class RRset(models.Model):
    # TODO Do these two fields really make sense? Meaning is limited when deleting + recreating an RRset
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='rrsets')
    subname = models.CharField(max_length=178, blank=True)
    type = models.CharField(max_length=10)
    records = models.CharField(max_length=64000, blank=True)
    ttl = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    _dirty = False

    class Meta:
        unique_together = (("domain","subname","type"),)

    def __setattr__(self, attrname, val):
        setter_func = 'setter_' + attrname
        if attrname in self.__dict__ and callable(getattr(self, setter_func, None)):
            super().__setattr__(attrname, getattr(self, setter_func)(val))
        else:
            super().__setattr__(attrname, val)

    def setter_records(self, val):
        if val != self.records:
            self._dirty = True

        return val

    def setter_ttl(self, val):
        if val != self.ttl:
            self._dirty = True

        return val

    def update_pdns(self):
        from .serializers import RRsetSerializer
        serializer = RRsetSerializer(self)

        pdns.set_rrsets(self.domain.name, [serializer.data])
        pdns.notify_zone(self.domain.name)


    @transaction.atomic
    def delete(self, *args, **kwargs):
        if self.type == 'SOA':
            raise ValidationError('You cannot touch the SOA record')

        # Reset records so that our pdns update later will cause deletion
        self.records = '[]'
        super().delete(*args, **kwargs)

        self.update_pdns()

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.type == 'SOA':
            raise ValidationError('You cannot touch the SOA record')

        new = self.pk is None
        self.updated = timezone.now()
        super().save(*args, **kwargs)

        if self._dirty or new:
            self.update_pdns()
