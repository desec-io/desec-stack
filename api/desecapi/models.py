from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.utils import timezone
from django.core.exceptions import SuspiciousOperation, ValidationError
from desecapi import pdns, mixins
import datetime, uuid
from django.core.validators import MinValueValidator
from rest_framework.authtoken.models import Token


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

    def _create_pdns_zone(self):
        """
        Create zone on pdns.  This will also import any RRsets that may have
        been created already.
        """
        pdns.create_zone(self, settings.DEFAULT_NS)

        # Import RRsets that may have been created (e.g. during captcha lock).
        # Don't perform if we do not know of any RRsets (it would delete all
        # existing records from pdns).
        rrsets = self.rrset_set.all()
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
                pdns.set_rrsets(self, self.rrset_set.all())
            else:
                raise e

    @transaction.atomic
    def sync_from_pdns(self):
        self.rrset_set.all().delete()
        rrsets = []
        rrs = []
        for rrset_data in pdns.get_rrset_datas(self):
            if rrset_data['type'] in RRset.RESTRICTED_TYPES:
                continue
            records = rrset_data.pop('records')
            rrset = RRset(**rrset_data)
            rrsets.append(rrset)
            rrs.extend([RR(rrset=rrset, content=record) for record in records])
        RRset.objects.bulk_create(rrsets)
        RR.objects.bulk_create(rrs)

    def write_rrsets(self, datas):
        rrsets = {}
        for data in datas:
            rrset = RRset(domain=self, subname=data['subname'],
                          type=data['type'], ttl=data['ttl'])
            rrsets[rrset] = [RR(rrset=rrset, content=content)
                             for content in data['contents']]
        self._write_rrsets(rrsets)

    @transaction.atomic
    def _write_rrsets(self, rrsets):
        # Always-false Q object: https://stackoverflow.com/a/35894246/6867099
        rrsets_index = {}
        q_update = models.Q(pk__isnull=True)
        q_delete = models.Q(pk__isnull=True)

        # Determine which RRsets need to be updated or deleted
        for rrset, rrs in rrsets.items():
            if rrset.domain is not self:
                raise ValueError('RRset has wrong domain')
            if (rrset.subname, rrset.type) in rrsets_index:
                raise ValueError('RRset repeated with same subname and type')
            if not all(rr.rrset is rrset for rr in rrs):
                raise ValueError('RR has wrong parent RRset')

            # Book-keeping
            rrsets_index[(rrset.subname, rrset.type)] = rrset

            q = models.Q(subname=rrset.subname) & models.Q(type=rrset.type)
            if rrs:
                q_update |= q
            else:
                q_delete |= q

        # Lock RRsets
        RRset.objects.filter(q_update | q_delete, domain=self).select_for_update()

        # Figure out which RRsets are unchanged and can be excluded
        exclude_from_update = []
        qs_update = RRset.objects.filter(q_update, domain=self)
        for rrset_old in qs_update.prefetch_related('records').all():
            rrset_new = rrsets_index[(rrset_old.subname, rrset_old.type)]
            if rrset_old.ttl != rrset_new.ttl:
                continue
            rrs_new = {rr.content for rr in rrsets[rrset_new]}
            rrs_old = {rr.content for rr in rrset_old.records.all()}
            if rrs_new != rrs_old:
                continue
            # Old and new contents do not differ, so we can skip this RRset
            del rrsets[rrset_new]
            exclude_from_update.append(rrset_old)

        # Do not process new RRsets that are empty (and did not exist before)
        # This is to avoid unnecessary pdns requests like (A: ...; AAAA: None)
        qs_delete = RRset.objects.filter(q_delete, domain=self)
        qs_delete_values = qs_delete.values_list('subname', 'type')
        # We modify the rrsets dictionary and thus loop over a copy of it
        for rrset, rrs in list(rrsets.items()):
            if rrs or (rrset.subname, rrset.type) in qs_delete_values:
                continue
            # RRset up for deletion does not exist
            del rrsets[rrset]

        # Clear or delete RRsets
        RR.objects.filter(rrset__in=qs_update).exclude(rrset__in=exclude_from_update).delete()
        RRset.objects.filter(q_delete, domain=self).delete()

        # Prepare and save new RRset contents
        # We modify the rrsets dictionary and thus loop over a copy of it
        for rrset, rrs in list(rrsets.items()):
            if not rrs:
                continue
            # (Create and) get correct RRset and update dictionary accordingly
            del rrsets[rrset]
            (rrset, _) = RRset.objects.get_or_create(domain=self,
                                                     subname=rrset.subname,
                                                     type=rrset.type,
                                                     ttl=rrset.ttl)
            rrsets[rrset] = [RR(rrset=rrset, content=rr.content) for rr in rrs]

        RR.objects.bulk_create([rr for rrs in rrsets.values() for rr in rrs])

        # Send changed RRsets to pdns
        if rrsets and not self.owner.captcha_required:
            pdns.set_rrsets(self, rrsets)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        # Delete delegation for dynDNS domains (direct child of dedyn.io)
        subname, parent_pdns_id = self.pdns_id.split('.', 1)
        if parent_pdns_id == 'dedyn.io.':
            try:
                parent = Domain.objects.get(name='dedyn.io')
            except Domain.DoesNotExist:
                pass
            else:
                rrsets = parent.rrset_set.filter(subname=subname,
                                                 type__in=['NS', 'DS']).all()
                # Need to go RRset by RRset to trigger pdns sync
                # TODO can optimize using write_rrsets()
                for rrset in rrsets:
                    rrset.delete()

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
            try:
                parent = Domain.objects.get(name='dedyn.io')
            except Domain.DoesNotExist:
                return

            with transaction.atomic():
                rrset = parent.rrset_set.create(subname=subname, type='NS',
                                                ttl=60)
                rrset.set_rrs(settings.DEFAULT_NS, notify=False)

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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

    def __init__(self, *args, **kwargs):
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
        return self._dirties

    @property
    def name(self):
        return '.'.join(filter(None, [self.subname, self.domain.name])) + '.'

    @transaction.atomic
    def set_rrs(self, contents, sync=True, notify=True):
        self.records.all().delete()
        self.records.set([RR(content=x) for x in contents], bulk=False)
        if sync and not self.domain.owner.captcha_required:
            pdns.set_rrset(self, notify=notify)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        pdns.set_rrset(self)
        self._dirties = {}

    def save(self, *args, **kwargs):
        # If not new, the only thing that can change is the TTL
        if self.created is None or 'ttl' in self.get_dirties():
            self.updated = timezone.now()
            self.full_clean()
            super().save(*args, **kwargs)
            self._dirties = {}


class RR(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name='records')
    # max_length is determined based on the calculation in
    # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
    content = models.CharField(max_length=4092)
