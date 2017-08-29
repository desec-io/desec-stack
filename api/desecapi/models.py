from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.utils import timezone
from django.core.exceptions import SuspiciousOperation, ValidationError
from desecapi import pdns, mixins
import datetime
from django.core.validators import MinValueValidator
from rest_framework.authtoken.models import Token
from collections import Counter


class MyUserManager(BaseUserManager):
    def create_user(self, email, password=None, registration_remote_ip=None, captcha_required=False, dyn=False):
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
    dyn = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def get_token(self):
        token, created = Token.objects.get_or_create(user=self)
        return token.key

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
            domain.sync_to_pdns()
        self.save()


class Domain(models.Model, mixins.SetterMixin):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=191, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='domains')
    _dirtyName = False
    _ns_records_data = [{'content': 'ns1.desec.io.'},
                        {'content': 'ns2.desec.io.'}]

    def setter_name(self, val):
        if val != self.name:
            self._dirtyName = True

        return val

    def clean(self):
        if self._dirtyName:
            raise ValidationError('You must not change the domain name')

    @property
    def keys(self):
        return pdns.get_keys(self)

    @property
    def pdns_id(self):
        if '/' in self.name or '?' in self.name:
            raise SuspiciousOperation('Invalid hostname ' + self.name)

        # Transform to be valid pdns API identifiers (:id in their docs).  The
        # '/' case here is just a safety measure (this case should never occur due
        # to the above check).
        # See also pdns code, apiZoneNameToId() in ws-api.cc
        name = self.name.translate(str.maketrans({'/': '=2F', '_': '=5F'}))

        if not name.endswith('.'):
            name += '.'

        return name

    # When this is made a property, looping over Domain.rrsets breaks
    def get_rrsets(self):
        return RRset.objects.filter(domain=self)

    def _create_pdns_zone(self):
        """
        Create zone on pdns.  This will also import any RRsets that may have
        been created already.
        """
        pdns.create_zone(self, settings.DEFAULT_NS)

        # Import RRsets that may have been created (e.g. during captcha lock).
        # Don't perform if we do not know of any RRsets (it would delete all
        # existing records from pdns).
        rrsets = self.get_rrsets()
        if rrsets:
            pdns.set_rrsets(self, rrsets)

        # Make our RRsets consistent with pdns (specifically, NS may exist)
        self.sync_from_pdns()

    def sync_to_pdns(self):
        """
        Make sure that pdns gets the latest information about this domain/zone.
        Re-Syncing is relatively expensive and should not happen routinely.
        """
        # Try to create zone, in case it does not exist yet
        try:
            self._create_pdns_zone()
        except pdns.PdnsException as e:
            if (e.status_code == 422 and e.detail.endswith(' already exists')):
                # Zone exists, purge it by deleting all RRsets and sync
                pdns.set_rrsets(self, [], notify=False)
                pdns.set_rrsets(self, self.get_rrsets())
            else:
                raise e

    @transaction.atomic
    def sync_from_pdns(self):
        RRset.objects.filter(domain=self).delete()
        rrset_datas = [rrset_data for rrset_data in pdns.get_rrset_datas(self)
                       if rrset_data['type'] not in RRset.RESTRICTED_TYPES]
        # Can't do bulk create because we need records creation in RRset.save()
        for rrset_data in rrset_datas:
            RRset(**rrset_data).save(sync=False)

    @transaction.atomic
    def set_rrsets(self, rrsets):
        """
        Writes the provided RRsets to the database, overriding any existing
        RRsets of the same subname and type.  If the user account is not locked
        for captcha, also inform pdns about the new RRsets.
        """
        for rrset in rrsets:
            if rrset.domain != self:
                raise ValueError(
                    'Cannot set RRset for domain %s on domain %s.' % (
                    rrset.domain.name, self.name))
            if rrset.type in RRset.RESTRICTED_TYPES:
                raise ValueError(
                    'You cannot tinker with the %s RRset.' % rrset.type)

        pdns_rrsets = []
        for rrset in rrsets:
            # Look up old RRset to see if it needs updating.  If exists and
            # outdated, delete it so that we can bulk-create it later.
            try:
                old_rrset = self.rrset_set.get(subname=rrset.subname,
                                               type=rrset.type)
                old_rrset.ttl = rrset.ttl
                old_rrset.records_data = rrset.records_data
                rrset = old_rrset
            except RRset.DoesNotExist:
                pass

            # At this point, rrset is an RRset to be created or possibly to be
            # updated.  RRset.save() will decide what to write to the database.
            if rrset.pk is None or 'records' in rrset.get_dirties():
                pdns_rrsets.append(rrset)

            rrset.save(sync=False)

        if not self.owner.captcha_required:
            pdns.set_rrsets(self, pdns_rrsets)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Delete delegation for dynDNS domains (direct child of dedyn.io)
        subname, parent_pdns_id = self.pdns_id.split('.', 1)
        if parent_pdns_id == 'dedyn.io.':
            parent = Domain.objects.filter(name='dedyn.io').first()

            if parent:
                rrsets = RRset.objects.filter(domain=parent, subname=subname,
                                              type__in=['NS', 'DS']).all()
                for rrset in rrsets:
                    rrset.records_data = []

                parent.set_rrsets(rrsets)

        # Delete domain
        super().delete(*args, **kwargs)
        pdns.delete_zone(self)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            new = self.pk is None
            self.clean()
            super().save(*args, **kwargs)

            if new and not self.owner.captcha_required:
                self._create_pdns_zone()

        if not new:
            return

        # If the domain is a direct subdomain of dedyn.io, set NS records in
        # parent. Don't notify slaves (we first have to enable DNSSEC).
        subname, parent_pdns_id = self.pdns_id.split('.', 1)
        if parent_pdns_id == 'dedyn.io.':
            parent = Domain.objects.filter(name='dedyn.io').first()
            if parent:
                records_data = [('content', x) for x in settings.DEFAULT_NS]
                rrset = RRset(domain=parent, subname=subname, type='NS',
                              ttl=60, records_data=records_data)
                rrset.save(notify=False)

    def __str__(self):
        """
        Return domain name.  Needed for serialization via StringRelatedField.
        (Must be unique.)
        """
        return self.name

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
        super().save(*args, **kwargs) # Call the "real" save() method.


    class Meta:
        ordering = ('created',)


def validate_upper(value):
    if value != value.upper():
        raise ValidationError('Invalid value (not uppercase): %(value)s',
                              code='invalid',
                              params={'value': value})


class RRset(models.Model, mixins.SetterMixin):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    subname = models.CharField(max_length=178, blank=True)
    type = models.CharField(max_length=10, validators=[validate_upper])
    ttl = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    _dirty = False
    RESTRICTED_TYPES = ('SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM')


    class Meta:
        unique_together = (("domain","subname","type"),)

    def __init__(self, *args, records_data=None, **kwargs):
        self.records_data = records_data
        self._dirties = set()
        super().__init__(*args, **kwargs)

    def setter_domain(self, val):
        if val != self.domain:
            self._dirties.add('domain')

        return val

    def setter_subname(self, val):
        # On PUT, RRsetSerializer sends None, denoting the unchanged value
        if val is None:
            return self.subname

        if val != self.subname:
            self._dirties.add('subname')

        return val

    def setter_type(self, val):
        if val != self.type:
            self._dirties.add('type')

        return val

    def setter_ttl(self, val):
        if val != self.ttl:
            self._dirties.add('ttl')

        return val

    def clean(self):
        errors = {}
        for field in (self._dirties & {'domain', 'subname', 'type'}):
            errors[field] = ValidationError(
                'You cannot change the `%s` field.' % field)

        if errors:
            raise ValidationError(errors)

    def get_dirties(self):
        if self.records_data is not None and 'records' not in self._dirties \
            and (self.pk is None
                or Counter([x['content'] for x in self.records_data])
                    != Counter(self.records.values_list('content', flat=True))
                ):
            self._dirties.add('records')

        return self._dirties

    @property
    def name(self):
        return '.'.join(filter(None, [self.subname, self.domain.name])) + '.'

    @transaction.atomic
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        pdns.set_rrset(self)
        self.records_data = None
        self._dirties = {}

    @transaction.atomic
    def save(self, sync=True, notify=True, *args, **kwargs):
        new = self.pk is None

        # Empty records data means deletion
        if self.records_data == []:
            if not new:
                self.delete()
            return

        # The only thing that can change is the TTL
        if new or 'ttl' in self.get_dirties():
            self.updated = timezone.now()
            self.full_clean()
            super().save(*args, **kwargs)

        # Create RRset contents
        if 'records' in self.get_dirties():
            self.records.all().delete()
            records = [RR(rrset=self, **data) for data in self.records_data]
            self.records.bulk_create(records)
            self.records_data = None

        # Sync to pdns if new or anything is dirty
        if sync and not self.domain.owner.captcha_required \
                and (new or self.get_dirties()):
            pdns.set_rrset(self, notify=notify)

        self._dirties = {}


class RR(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name='records')
    # max_length is determined based on the calculation in
    # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
    content = models.CharField(max_length=4092)
