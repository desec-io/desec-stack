from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.utils import timezone
from django.core.exceptions import SuspiciousOperation, ValidationError
from desecapi import pdns, mixins
import datetime, uuid
from django.core.validators import MinValueValidator
from collections import OrderedDict
import rest_framework.authtoken.models
import time, random
from os import urandom
from base64 import b64encode


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
        user = self.create_user(email,
                                password=password
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class Token(rest_framework.authtoken.models.Token):
    key = models.CharField("Key", max_length=40, db_index=True, unique=True)
    # relation to user is a ForeignKey, so each user can have more than one token
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='auth_tokens',
        on_delete=models.CASCADE, verbose_name="User"
    )
    name = models.CharField("Name", max_length=64, default="")
    user_specific_id = models.BigIntegerField("User-Specific ID")

    def save(self, *args, **kwargs):
        if not self.user_specific_id:
            self.user_specific_id = random.randrange(16**8)
        super().save(*args, **kwargs) # Call the "real" save() method.

    def generate_key(self):
        return b64encode(urandom(21)).decode('utf-8').replace('/', '-').replace('=', '_').replace('+', '.')

    class Meta:
        abstract = False
        unique_together = (('user', 'user_specific_id'),)


class User(AbstractBaseUser):
    email = models.EmailField(
        verbose_name='email address',
        max_length=191,
        unique=True,
    )
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    registration_remote_ip = models.CharField(max_length=1024, blank=True)
    locked = models.DateTimeField(null=True,blank=True)
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

    def get_or_create_first_token(self):
        try:
            token = Token.objects.filter(user=self).earliest('created')
        except Token.DoesNotExist:
            token = Token.objects.create(user=self)
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
        # self.locked is used by domain.sync_to_pdns(), so call that first
        for domain in self.domains.all():
            domain.sync_to_pdns()
        self.locked = None
        self.save()


class Domain(models.Model, mixins.SetterMixin):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=191, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='domains')
    published = models.DateTimeField(null=True)
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

    def sync_to_pdns(self):
        """
        Make sure that pdns gets the latest information about this domain/zone.
        Re-syncing is relatively expensive and should not happen routinely.

        This method should only be called for new domains or on user unlocking.
        For unlocked users, it assumes that the domain is a new one.
        """

        # Determine if this domain is expected to be new on pdns. This is the
        # case if the user is not locked (by assumption) or if the domain was
        # created after the user was locked. (If the user had this domain
        # before locking, it is not new on pdns.)
        new = self.owner.locked is None or self.owner.locked < self.created

        if new:
            # Create zone
            # Throws exception if pdns already knows this zone for some reason
            # which means that it is not ours and we should not mess with it.
            # We escalate the exception to let the next level deal with the
            # response.
            pdns.create_zone(self, settings.DEFAULT_NS)

            # Send RRsets to pdns that may have been created (e.g. during lock).
            self._publish()

            # Make our RRsets consistent with pdns (specifically, NS may exist)
            self.sync_from_pdns()

            # For dedyn.io domains, propagate NS and DS delegation RRsets
            subname, parent_pdns_id = self.pdns_id.split('.', 1)
            if parent_pdns_id == 'dedyn.io.':
                try:
                    parent = Domain.objects.get(name='dedyn.io')
                except Domain.DoesNotExist:
                    pass
                else:
                    rrsets = RRset.plain_to_RRsets([
                        {'subname': subname, 'type': 'NS', 'ttl': 3600,
                         'contents': settings.DEFAULT_NS},
                        {'subname': subname, 'type': 'DS', 'ttl': 60,
                         'contents': [ds for k in self.keys for ds in k['ds']]}
                    ], domain=parent)
                    parent.write_rrsets(rrsets)
        else:
            # Zone exists. For the case that pdns knows records that we do not
            # (e.g. if a locked account has deleted an RRset), it is necessary
            # to purge all records here. However, there is currently no way to
            # do this through the pdns API (not to mention doing it atomically
            # with setting the new RRsets). So for now, we have disabled RRset
            # deletion for locked accounts.
            self._publish()

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

    @transaction.atomic
    def write_rrsets(self, rrsets):
        # Base queryset for all RRsets of the current domain
        rrset_qs = RRset.objects.filter(domain=self)

        # Set to check RRset uniqueness
        rrsets_seen = set()

        # We want to return all new, changed, and unchanged RRsets (but not
        # deleted ones). We store them here, indexed by (subname, type).
        rrsets_to_return = OrderedDict()

        # Record contents to send to pdns, indexed by their RRset
        rrsets_for_pdns = {}

        # Always-false Q object: https://stackoverflow.com/a/35894246/6867099
        q_meaty = models.Q(pk__isnull=True)
        q_empty = models.Q(pk__isnull=True)

        # Determine which RRsets need to be updated or deleted
        for rrset, rrs in rrsets.items():
            if rrset.domain != self:
                raise ValueError('RRset has wrong domain')
            if (rrset.subname, rrset.type) in rrsets_seen:
                raise ValueError('RRset repeated with same subname and type')
            if rrs is not None and not all(rr.rrset is rrset for rr in rrs):
                raise ValueError('RR has wrong parent RRset')

            rrsets_seen.add((rrset.subname, rrset.type))

            q = models.Q(subname=rrset.subname, type=rrset.type)
            if rrs or rrs is None:
                rrsets_to_return[(rrset.subname, rrset.type)] = rrset
                q_meaty |= q
            else:
                # Set TTL so that pdns does not get confused if missing
                rrset.ttl = 1
                rrsets_for_pdns[rrset] = []
                q_empty |= q

        # Construct querysets representing RRsets that do (not) have RR
        # contents and lock them
        qs_meaty = rrset_qs.filter(q_meaty).select_for_update()
        qs_empty = rrset_qs.filter(q_empty).select_for_update()

        # For existing RRsets, execute TTL updates and/or mark for RR update.
        # First, let's create a to-do dict; we'll need it later for new RRsets.
        rrsets_with_new_rrs = []
        rrsets_meaty_todo = dict(rrsets_to_return)
        for rrset in qs_meaty.all():
            rrsets_to_return[(rrset.subname, rrset.type)] = rrset

            rrset_temp = rrsets_meaty_todo.pop((rrset.subname, rrset.type))
            rrs = {rr.content for rr in rrset.records.all()}

            partial = rrsets[rrset_temp] is None
            if partial:
                rrs_temp = rrs
            else:
                rrs_temp = {rr.content for rr in rrsets[rrset_temp]}

            # Take current TTL if none was given
            rrset_temp.ttl = rrset_temp.ttl or rrset.ttl

            changed_ttl = (rrset_temp.ttl != rrset.ttl)
            changed_rrs = not partial and (rrs_temp != rrs)

            if changed_ttl:
                rrset.ttl = rrset_temp.ttl
                rrset.save()
            if changed_rrs:
                rrsets_with_new_rrs.append(rrset)
            if changed_ttl or changed_rrs:
                rrsets_for_pdns[rrset] = [RR(rrset=rrset, content=rr_content)
                                          for rr_content in rrs_temp]

        # At this point, rrsets_meaty_todo contains new RRsets only, with
        # a list of RRs or with None associated.
        for key, rrset in list(rrsets_meaty_todo.items()):
            if rrsets[rrset] is None:
                # None means "don't change RRs". In the context of a new RRset,
                # this really is no-op, and we do not need to return the RRset.
                rrsets_to_return.pop((rrset.subname, rrset.type))
            else:
                # If there are associated RRs, let's save the RRset. This does
                # not save the RRs yet.
                rrsets_with_new_rrs.append(rrset)
                rrset.save()

            # In either case, send a request to pdns so that we can take
            # advantage of pdns' type validation check (even if no RRs given).
            rrsets_for_pdns[rrset] = rrsets[rrset]

        # Repeat lock to make sure new RRsets are also locked
        rrset_qs.filter(q_meaty).select_for_update()

        # Delete empty RRsets
        qs_empty.delete()

        # Update contents of modified RRsets
        RR.objects.filter(rrset__in=rrsets_with_new_rrs).delete()
        RR.objects.bulk_create([rr
                                for (rrset, rrs) in rrsets_for_pdns.items()
                                if rrs and rrset in rrsets_with_new_rrs
                                for rr in rrs])

        # Send RRsets to pdns
        if not self.owner.locked:
            self._publish(rrsets_for_pdns)

        # Return RRsets
        return list(rrsets_to_return.values())

    @transaction.atomic
    def _publish(self, rrsets = None):
        if rrsets is None:
            rrsets = self.rrset_set.all()

        self.published = timezone.now()
        self.save()

        if rrsets:
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
                parent.write_rrsets({rrset: [] for rrset in rrsets})

        # Delete domain
        super().delete(*args, **kwargs)
        pdns.delete_zone(self)

    @transaction.atomic
    def save(self, *args, **kwargs):
        new = self.pk is None
        self.clean()
        super().save(*args, **kwargs)

        if new and not self.owner.locked:
            self.sync_to_pdns()

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
    return "ONDON" + str(time.time())


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
    DEAD_TYPES = ('ALIAS', 'DNAME')
    RESTRICTED_TYPES = ('SOA', 'RRSIG', 'DNSKEY', 'NSEC3PARAM', 'OPT')


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
    def delete(self, *args, **kwargs):
        # For locked users, we can't easily sync deleted RRsets to pdns later,
        # so let's forbid it for now.
        assert not self.domain.owner.locked
        self.domain.write_rrsets({self: []})
        self._dirties = {}

    def save(self, *args, **kwargs):
        # If not new, the only thing that can change is the TTL
        if self.created is None or 'ttl' in self.get_dirties():
            self.updated = timezone.now()
            self.full_clean()
            # Tell Django to not attempt an update, although the pk is not None
            kwargs['force_insert'] = (self.created is None)
            super().save(*args, **kwargs)
            self._dirties = {}

    @staticmethod
    def plain_to_RRsets(datas, *, domain):
        rrsets = {}
        for data in datas:
            rrset = RRset(domain=domain, subname=data['subname'],
                          type=data['type'], ttl=data['ttl'])
            rrsets[rrset] = [RR(rrset=rrset, content=content)
                             for content in data['contents']]
        return rrsets


class RR(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name='records')
    # max_length is determined based on the calculation in
    # https://lists.isc.org/pipermail/bind-users/2008-April/070148.html
    content = models.CharField(max_length=4092)
