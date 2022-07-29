from __future__ import annotations

import binascii
import datetime
import ipaddress
import json
import logging
import re
import secrets
import string
import time
import uuid
from datetime import timedelta
from functools import cached_property
from hashlib import sha256

import dns
import pgtrigger
import psl_dns
import rest_framework.authtoken.models
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, BaseUserManager
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, CIEmailField, RangeOperators
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import CharField, F, Manager, Q, Value
from django.db.models.expressions import RawSQL
from django.db.models.functions import Concat, Length
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin
from dns import rdataclass, rdatatype
from dns.exception import Timeout
from dns.rdtypes import ANY, IN
from dns.resolver import NoNameservers
import netfields
from rest_framework.exceptions import APIException

from desecapi import metrics
from desecapi import pdns
from desecapi.dns import AAAA, CERT, LongQuotedTXT, MX, NS, SRV

logger = logging.getLogger(__name__)
psl = psl_dns.PSL(resolver=settings.PSL_RESOLVER, timeout=.5)


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


class User(ExportModelOperationsMixin('User'), AbstractBaseUser):
    @staticmethod
    def _limit_domains_default():
        return settings.LIMIT_USER_DOMAIN_COUNT_DEFAULT

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = CIEmailField(
        verbose_name='email address',
        unique=True,
    )
    email_verified = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, null=True)
    is_admin = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    limit_domains = models.PositiveIntegerField(default=_limit_domains_default.__func__, null=True, blank=True)
    needs_captcha = models.BooleanField(default=True)

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
        self.needs_captcha = False
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

    def delete(self):
        pk = self.pk
        ret = super().delete()
        logger.warning(f'User {pk} deleted')
        return ret

    def send_email(self, reason, context=None, recipient=None):
        fast_lane = 'email_fast_lane'
        slow_lane = 'email_slow_lane'
        immediate_lane = 'email_immediate_lane'
        lanes = {
            'activate-account': slow_lane,
            'change-email': slow_lane,
            'change-email-confirmation-old-email': fast_lane,
            'confirm-account': slow_lane,
            'password-change-confirmation': fast_lane,
            'reset-password': fast_lane,
            'delete-account': fast_lane,
            'domain-dyndns': fast_lane,
            'renew-domain': immediate_lane,
        }
        if reason not in lanes:
            raise ValueError(f'Cannot send email to user {self.pk} without a good reason: {reason}')

        context = context or {}
        content = get_template(f'emails/{reason}/content.txt').render(context)
        content += f'\nSupport Reference: user_id = {self.pk}\n'
        footer = get_template('emails/footer.txt').render()

        logger.warning(f'Queuing email for user account {self.pk} (reason: {reason}, lane: {lanes[reason]})')
        num_queued = EmailMessage(
            subject=get_template(f'emails/{reason}/subject.txt').render(context).strip(),
            body=content + footer,
            from_email=get_template('emails/from.txt').render(),
            to=[recipient or self.email],
            connection=get_connection(lane=lanes[reason], debug={'user': self.pk, 'reason': reason})
        ).send()
        metrics.get('desecapi_messages_queued').labels(reason, self.pk, lanes[reason]).observe(num_queued)
        return num_queued

    def send_confirmation_email(self, reason, recipient=None, params=None, **kwargs):
        def _generate_link(**kwargs):
            action = action_serializer.Meta.model(user=self, **kwargs)
            action_data = action_serializer(action).data
            return f'https://desec.{settings.DESECSTACK_DOMAIN}' + reverse(view_name, args=[action_data['code']])

        view_name = f'v1:confirm-{reason}'
        url = reverse(view_name, args=['code'])  # dummy value; parameter is required for reverse URL resolution
        action_serializer = resolve(url).func.view_class.serializer_class
        if action_serializer.validity_period is not None:
            kwargs['link_expiration_hours'] = action_serializer.validity_period // timedelta(hours=1)

        if isinstance(params, list):
            kwargs['confirmation_link'] = [(_generate_link(**(param or {})), param) for param in params]
        else:
            kwargs['confirmation_link'] = (_generate_link(**(params or {})), params)
        self.send_email(reason, recipient=recipient, context=dict(kwargs, params=params))


validate_domain_name = [
    validate_lower,
    RegexValidator(
        regex=r'^(([a-z0-9_-]{1,63})\.)*[a-z0-9-]{1,63}$',
        message='Domain names must be labels separated by dots. Labels may consist of up to 63 letters, digits, '
                'hyphens, and underscores. The last label may not contain an underscore.',
        code='invalid_domain_name',
        flags=re.IGNORECASE
    )
]


class DomainManager(Manager):
    def filter_qname(self, qname: str, **kwargs) -> models.query.QuerySet:
        try:
            Domain._meta.get_field('name').run_validators(qname.removeprefix('*.').lower())
        except ValidationError:
            raise ValueError
        return self.annotate(
            dotted_name=Concat(Value('.'), 'name', output_field=CharField()),
            dotted_qname=Value(f'.{qname}', output_field=CharField()),
            name_length=Length('name'),
        ).filter(dotted_qname__endswith=F('dotted_name'), **kwargs)


class Domain(ExportModelOperationsMixin('Domain'), models.Model):
    @staticmethod
    def _minimum_ttl_default():
        return settings.MINIMUM_TTL_DEFAULT

    class RenewalState(models.IntegerChoices):
        IMMORTAL = 0
        FRESH = 1
        NOTIFIED = 2
        WARNED = 3

    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=191,
                            unique=True,
                            validators=validate_domain_name)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='domains')
    published = models.DateTimeField(null=True, blank=True)
    replicated = models.DateTimeField(null=True, blank=True)
    replication_duration = models.DurationField(null=True, blank=True)
    minimum_ttl = models.PositiveIntegerField(default=_minimum_ttl_default.__func__)
    renewal_state = models.IntegerField(choices=RenewalState.choices, default=RenewalState.IMMORTAL)
    renewal_changed = models.DateTimeField(auto_now_add=True)
    pdns_master = models.CharField(max_length=128, null=True, blank=True)
    pdns_last_check = models.IntegerField(null=True, blank=True)
    pdns_type = models.CharField(max_length=6, default='MASTER')
    pdns_notified_serial = models.BigIntegerField(null=True, blank=True)
    pdns_account = models.CharField(max_length=40, null=True, blank=True)
    pdns_meta_nsec3param = models.CharField(max_length=142, default='1 0 0 -')

    _keys = None
    objects = DomainManager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['id', 'owner'], name='unique_id_owner')]
        ordering = ('created',)

    def __init__(self, *args, **kwargs):
        if isinstance(kwargs.get('owner'), AnonymousUser):
            kwargs = {**kwargs, 'owner': None}  # make a copy and override
        # Avoid super().__init__(owner=None, ...) to not mess up *values instantiation in django.db.models.Model.from_db
        super().__init__(*args, **kwargs)
        if self.pk is None and kwargs.get('renewal_state') is None and self.is_locally_registrable:
            self.renewal_state = Domain.RenewalState.FRESH

    @cached_property
    def public_suffix(self):
        try:
            public_suffix = psl.get_public_suffix(self.name)
            is_public_suffix = psl.is_public_suffix(self.name)
        except (Timeout, NoNameservers):
            public_suffix = self.name.rpartition('.')[2]
            is_public_suffix = ('.' not in self.name)  # TLDs are public suffixes

        if is_public_suffix:
            return public_suffix

        # Take into account that any of the parent domains could be a local public suffix. To that
        # end, identify the longest local public suffix that is actually a suffix of domain_name.
        for local_public_suffix in settings.LOCAL_PUBLIC_SUFFIXES:
            has_local_public_suffix_parent = ('.' + self.name).endswith('.' + local_public_suffix)
            if has_local_public_suffix_parent and len(local_public_suffix) > len(public_suffix):
                public_suffix = local_public_suffix

        return public_suffix

    def is_covered_by_foreign_zone(self):
        # Generate a list of all domains connecting this one and its public suffix.
        # If another user owns a zone with one of these names, then the requested
        # domain is unavailable because it is part of the other user's zone.
        private_components = self.name.rsplit(self.public_suffix, 1)[0].rstrip('.')
        private_components = private_components.split('.') if private_components else []
        private_domains = ['.'.join(private_components[i:]) for i in range(0, len(private_components))]
        private_domains = [f'{private_domain}.{self.public_suffix}' for private_domain in private_domains]
        assert self.name == next(iter(private_domains), self.public_suffix)

        # Determine whether domain is covered by other users' zones
        return Domain.objects.filter(Q(name__in=private_domains) & ~Q(owner=self._owner_or_none)).exists()

    def covers_foreign_zone(self):
        # Note: This is not completely accurate: Ideally, we should only consider zones with identical public suffix.
        # (If a public suffix lies in between, it's ok.) However, as there could be many descendant zones, the accurate
        # check is expensive, so currently not implemented (PSL lookups for each of them).
        return Domain.objects.filter(Q(name__endswith=f'.{self.name}') & ~Q(owner=self._owner_or_none)).exists()

    def is_registrable(self):
        """
        Returns False if the domain name is reserved, a public suffix, or covered by / covers another user's domain.
        Otherwise, True is returned.
        """
        self.clean()  # ensure .name is a domain name
        private_generation = self.name.count('.') - self.public_suffix.count('.')
        assert private_generation >= 0

        # .internal is reserved
        if f'.{self.name}'.endswith('.internal'):
            return False

        # Public suffixes can only be registered if they are local
        if private_generation == 0 and self.name not in settings.LOCAL_PUBLIC_SUFFIXES:
            return False

        # Disallow _acme-challenge.dedyn.io and the like. Rejects reserved direct children of public suffixes.
        reserved_prefixes = ('_', 'autoconfig.', 'autodiscover.',)
        if private_generation == 1 and any(self.name.startswith(prefix) for prefix in reserved_prefixes):
            return False

        # Domains covered by another user's zone can't be registered
        if self.is_covered_by_foreign_zone():
            return False

        # Domains that would cover another user's zone can't be registered
        if self.covers_foreign_zone():
            return False

        return True

    @property
    def keys(self):
        if not self._keys:
            self._keys = [{**key, 'managed': True} for key in pdns.get_keys(self)]
            try:
                unmanaged_keys = self.rrset_set.get(subname='', type='DNSKEY').records.all()
            except RRset.DoesNotExist:
                pass
            else:
                name = dns.name.from_text(self.name)
                for rr in unmanaged_keys:
                    key = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.DNSKEY, rr.content)
                    key_is_sep = key.flags & dns.rdtypes.ANY.DNSKEY.SEP
                    self._keys.append({
                        'dnskey': rr.content,
                        'ds': [dns.dnssec.make_ds(name, key, algo).to_text() for algo in (2, 4)] if key_is_sep else [],
                        'flags': key.flags,  # deprecated
                        'keytype': None,  # deprecated
                        'managed': False,
                    })
        return self._keys

    @property
    def touched(self):
        try:
            rrset_touched = max(updated for updated in self.rrset_set.values_list('touched', flat=True))
        except ValueError:  # no RRsets (but there should be at least NS)
            return self.published  # may be None if the domain was never published
        return max(rrset_touched, self.published or rrset_touched)

    @property
    def is_locally_registrable(self):
        return self.parent_domain_name in settings.LOCAL_PUBLIC_SUFFIXES

    @property
    def _owner_or_none(self):
        try:
            return self.owner
        except Domain.owner.RelatedObjectDoesNotExist:
            return None

    @property
    def parent_domain_name(self):
        return self._partitioned_name[1]

    @property
    def _partitioned_name(self):
        subname, _, parent_name = self.name.partition('.')
        return subname, parent_name or None

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        new = self.id is None
        super().save(*args, **kwargs)
        if new:
            # Create NS records
            rr_set = RRset(
                domain=self,
                type='NS', subname='',
                ttl=settings.DEFAULT_NS_TTL,
            )
            rr_set.save()

            rrs = [RR(rrset=rr_set, content=ns) for ns in settings.DEFAULT_NS]
            RR.objects.bulk_create(rrs)  # One INSERT

            # Create SOA record
            rr_set = RRset(
                domain=self,
                type='SOA', subname='',
                ttl=300,  # SOA RRset TTL: 300 (used as TTL for negative replies including NSEC3 records)
            )
            rr_set.save()
            get_desec_io = dns.name.from_text('get.desec.io')
            rr_set.save_records([dns.rdtypes.ANY.SOA.SOA(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.SOA,
                mname=get_desec_io,
                rname=get_desec_io,
                serial=int(f'{datetime.date.today().year:4n}{datetime.date.today().month:02n}0000'),
                refresh=86400,
                retry=3600,
                expire=2419200,
                minimum=3600,
            ).to_text()])

    def update_delegation(self, child_domain: Domain):
        child_subname, child_domain_name = child_domain._partitioned_name
        if self.name != child_domain_name:
            raise ValueError('Cannot update delegation of %s as it is not an immediate child domain of %s.' %
                             (child_domain.name, self.name))

        # Always remove delegation so that we con properly recreate it
        for rrset in self.rrset_set.filter(subname=child_subname, type__in=['NS', 'DS']):
            rrset.delete()

        if child_domain.pk:
            # Domain real: (re-)set delegation
            child_keys = child_domain.keys
            if not child_keys:
                raise APIException('Cannot delegate %s, as it currently has no keys.' % child_domain.name)

            RRset.objects.create(domain=self, subname=child_subname, type='NS', ttl=3600, contents=settings.DEFAULT_NS)
            RRset.objects.create(domain=self, subname=child_subname, type='DS', ttl=300,
                                 contents=[ds for k in child_keys for ds in k['ds']])
            metrics.get('desecapi_autodelegation_created').inc()
        else:
            # Domain not real: that's it
            metrics.get('desecapi_autodelegation_deleted').inc()

    def soa(self) -> RRset:
        return self.rrset_set.get(type='SOA', subname='')

    def increase_serial(self):
        # TODO this needs to be an atomic change to the database to avoid concurrency with pdns
        soa = self.soa()
        soa_rr = soa.object[0]
        soa_rr = dns.rdtypes.ANY.SOA.SOA(
            rdclass=soa_rr.rdclass,
            rdtype=soa_rr.rdtype,
            mname=soa_rr.mname,
            rname=soa_rr.rname,
            serial=max(int(time.time()), soa_rr.serial + 1),
            refresh=soa_rr.refresh,
            retry=soa_rr.retry,
            expire=soa_rr.expire,
            minimum=soa_rr.minimum,
        )
        soa.save_records([soa_rr.to_text()])

    def delete(self):
        ret = super().delete()
        logger.warning(f'Domain {self.name} deleted (owner: {self.owner.pk})')
        return ret

    def __str__(self):
        return self.name


class Token(ExportModelOperationsMixin('Token'), rest_framework.authtoken.models.Token):
    @staticmethod
    def _allowed_subnets_default():
        return [ipaddress.IPv4Network('0.0.0.0/0'), ipaddress.IPv6Network('::/0')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField("Key", max_length=128, db_index=True, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField('Name', blank=True, max_length=64)
    last_used = models.DateTimeField(null=True, blank=True)
    perm_manage_tokens = models.BooleanField(default=False)
    allowed_subnets = ArrayField(netfields.CidrAddressField(), default=_allowed_subnets_default.__func__)
    max_age = models.DurationField(null=True, default=None, validators=[MinValueValidator(timedelta(0))])
    max_unused_period = models.DurationField(null=True, default=None, validators=[MinValueValidator(timedelta(0))])
    domain_policies = models.ManyToManyField(Domain, through='TokenDomainPolicy')

    plain = None
    objects = netfields.NetManager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['id', 'user'], name='unique_id_user')]

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
        return make_password(plain, salt='static', hasher='pbkdf2_sha256_iter1')

    def get_policy(self, *, domain=None):
        order_by = F('domain').asc(nulls_last=True)  # default Postgres sorting, but: explicit is better than implicit
        return self.tokendomainpolicy_set.filter(Q(domain=domain) | Q(domain__isnull=True)).order_by(order_by).first()

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
        name='token_user',
        operation=pgtrigger.Update | pgtrigger.Insert,
        when=pgtrigger.Before,
        func='NEW.token_user_id = (SELECT user_id FROM desecapi_token WHERE id = NEW.token_id); RETURN NEW;',
    ),

    # Ensure that if there is *any* domain policy for a given token, there is always one with domain=None.
    pgtrigger.Trigger(
        name='default_policy_on_insert',
        operation=pgtrigger.Insert,
        when=pgtrigger.Before,
        # Trigger `condition` arguments (corresponding to WHEN clause) don't support subqueries, so we use `func`
        func="IF (NEW.domain_id IS NOT NULL and NOT EXISTS(SELECT * FROM desecapi_tokendomainpolicy WHERE domain_id IS NULL AND token_id = NEW.token_id)) THEN "
             "  RAISE EXCEPTION 'Cannot insert non-default policy into % table when default policy is not present', TG_TABLE_NAME; "
             "END IF; RETURN NEW;",
    ),
    pgtrigger.Protect(
        name='default_policy_on_update',
        operation=pgtrigger.Update,
        when=pgtrigger.Before,
        condition=pgtrigger.Q(old__domain__isnull=True, new__domain__isnull=False),
    ),
    # Ideally, this would be a deferred trigger, but depends on https://github.com/Opus10/django-pgtrigger/issues/14
    pgtrigger.Trigger(
        name='default_policy_on_delete',
        operation=pgtrigger.Delete,
        when=pgtrigger.Before,
        # Trigger `condition` arguments (corresponding to WHEN clause) don't support subqueries, so we use `func`
        func="IF (OLD.domain_id IS NULL and EXISTS(SELECT * FROM desecapi_tokendomainpolicy WHERE domain_id IS NOT NULL AND token_id = OLD.token_id)) THEN "
             "  RAISE EXCEPTION 'Cannot delete default policy from % table when non-default policy is present', TG_TABLE_NAME; "
             "END IF; RETURN OLD;",
    ),
)
class TokenDomainPolicy(ExportModelOperationsMixin('TokenDomainPolicy'), models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True)
    perm_dyndns = models.BooleanField(default=False)
    perm_rrsets = models.BooleanField(default=False)
    # Token user, filled via trigger. Used by compound FK constraints to tie domain.owner to token.user (see migration).
    token_user = models.ForeignKey(User, on_delete=models.CASCADE, db_constraint=False, related_name='+')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['token', 'domain'], name='unique_entry'),
            models.UniqueConstraint(fields=['token'], condition=Q(domain__isnull=True), name='unique_entry_null_domain')
        ]

    def clean(self):
        default_policy = self.token.get_policy(domain=None)
        if self.pk:  # update
            # Can't change policy's default status ("domain NULLness") to maintain policy precedence
            if (self.domain is None) != (self.pk == default_policy.pk):
                raise ValidationError({'domain': 'Policy precedence: Cannot disable default policy when others exist.'})
        else:  # create
            # Can't violate policy precedence (default policy has to be first)
            if (self.domain is not None) and (default_policy is None):
                raise ValidationError({'domain': 'Policy precedence: The first policy must be the default policy.'})

    def delete(self):
        # Can't delete default policy when others exist
        if (self.domain is None) and self.token.tokendomainpolicy_set.exclude(domain__isnull=True).exists():
            raise ValidationError({'domain': "Policy precedence: Can't delete default policy when there exist others."})
        return super().delete()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Donation(ExportModelOperationsMixin('Donation'), models.Model):
    @staticmethod
    def _created_default():
        return timezone.now()

    @staticmethod
    def _due_default():
        return timezone.now() + timedelta(days=7)

    @staticmethod
    def _mref_default():
        return "ONDON" + str(time.time())

    class Interval(models.IntegerChoices):
        ONCE = 0
        MONTHLY = 1
        QUARTERLY = 3

    created = models.DateTimeField(default=_created_default)
    name = models.CharField(max_length=255)
    iban = models.CharField(max_length=34)
    bic = models.CharField(max_length=11, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    message = models.CharField(max_length=255, blank=True)
    due = models.DateTimeField(default=_due_default)
    mref = models.CharField(max_length=32, default=_mref_default)
    interval = models.IntegerField(choices=Interval.choices, default=Interval.ONCE)
    email = models.EmailField(max_length=255, blank=True)

    class Meta:
        managed = False

    @property
    def interval_label(self):
        return dict(self.Interval.choices)[self.interval]


# RR set types: the good, the bad, and the ugly
# known, but unsupported types
RR_SET_TYPES_UNSUPPORTED = {
    'ALIAS',  # Requires signing at the frontend, hence unsupported in desec-stack
    'IPSECKEY',  # broken in pdns, https://github.com/PowerDNS/pdns/issues/10589 TODO enable with pdns auth >= 4.7.0
    'KEY',  # Application use restricted by RFC 3445, DNSSEC use replaced by DNSKEY and handled automatically
    'WKS',  # General usage not recommended, "SHOULD NOT" be used in SMTP (RFC 1123)
}
# restricted types are managed in use by the API, and cannot directly be modified by the API client
RR_SET_TYPES_AUTOMATIC = {
    # corresponding functionality is automatically managed:
    'KEY', 'NSEC', 'NSEC3', 'OPT', 'RRSIG',
    # automatically managed by the API:
    'NSEC3PARAM', 'SOA'
}
# backend types are types that are the types supported by the backend(s)
RR_SET_TYPES_BACKEND = pdns.SUPPORTED_RRSET_TYPES
# validation types are types supported by the validation backend, currently: dnspython
RR_SET_TYPES_VALIDATION = set(ANY.__all__) | set(IN.__all__) \
                          | {'L32', 'L64', 'LP', 'NID'}  # https://github.com/rthalley/dnspython/pull/751
# manageable types are directly managed by the API client
RR_SET_TYPES_MANAGEABLE = \
        (RR_SET_TYPES_BACKEND & RR_SET_TYPES_VALIDATION) - RR_SET_TYPES_UNSUPPORTED - RR_SET_TYPES_AUTOMATIC


class RRsetManager(Manager):
    def create(self, contents=None, **kwargs):
        rrset = super().create(**kwargs)
        for content in contents or []:
            RR.objects.create(rrset=rrset, content=content)
        return rrset


class RRset(ExportModelOperationsMixin('RRset'), models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    touched = models.DateTimeField(auto_now=True, db_index=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    subname = models.CharField(
        max_length=178,
        blank=True,
        validators=[
            validate_lower,
            RegexValidator(
                regex=r'^([*]|(([*][.])?([a-z0-9_-]{1,63}[.])*[a-z0-9_-]{1,63}))$',
                message='Subname can only use (lowercase) a-z, 0-9, ., -, and _, '
                        'may start with a \'*.\', or just be \'*\'. Components may not exceed 63 characters.',
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

    class Meta:
        constraints = [
            ExclusionConstraint(
                name='cname_exclusivity',
                expressions=[
                    ('domain', RangeOperators.EQUAL),
                    ('subname', RangeOperators.EQUAL),
                    (RawSQL("int4(type = 'CNAME')", ()), RangeOperators.NOT_EQUAL),
                ],
            ),
        ]
        unique_together = (("domain", "subname", "type"),)

    @staticmethod
    def construct_name(subname, domain_name):
        return '.'.join(filter(None, [subname, domain_name])) + '.'

    @property
    def name(self):
        return self.construct_name(self.subname, self.domain.name)

    @property
    def object(self):
        # TODO name of this property?
        # TODO parsing may fail in certain situations, need to be same as validation!
        return dns.rrset.from_text(self.name, self.ttl, 'IN', self.type, *[rr.content for rr in self.records.all()])

    def save(self, *args, **kwargs):
        # TODO Enforce that subname and type aren't changed. https://github.com/desec-io/desec-stack/issues/553
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def clean_records(self, records_presentation_format):
        """
        Validates the records belonging to this set. Validation rules follow the DNS specification; some types may
        incur additional validation rules.

        Raises ValidationError if violation of DNS specification is found.

        Returns a set of records in canonical presentation format.

        :param records_presentation_format: iterable of records in presentation format
        """
        errors = []

        # Singletons
        if self.type in ('CNAME', 'DNAME',):
            if len(records_presentation_format) > 1:
                errors.append(f'{self.type} RRset cannot have multiple records.')

        # Non-apex
        if self.type in ('CNAME', 'DS',):
            if self.subname == '':
                errors.append(f'{self.type} RRset cannot have empty subname.')

        if self.type in ('DNSKEY',):
            if self.subname != '':
                errors.append(f'{self.type} RRset must have empty subname.')

        def _error_msg(record, detail):
            return f'Record content of {self.type} {self.name} invalid: \'{record}\': {detail}'

        records_canonical_format = set()
        for r in records_presentation_format:
            try:
                r_canonical_format = RR.canonical_presentation_format(r, self.type)
            except ValueError as ex:
                errors.append(_error_msg(r, str(ex)))
            else:
                if r_canonical_format in records_canonical_format:
                    errors.append(_error_msg(r, f'Duplicate record content: this is identical to '
                                                f'\'{r_canonical_format}\''))
                else:
                    records_canonical_format.add(r_canonical_format)

        if any(errors):
            raise ValidationError(errors)

        return records_canonical_format

    def save_records(self, records):
        """
        Updates this RR set's resource records, discarding any old values.

        Records are expected in presentation format and are converted to canonical
        presentation format (e.g., 127.00.0.1 will be converted to 127.0.0.1).
        Raises if a invalid set of records is provided.

        This method triggers the following database queries:
        - one DELETE query
        - one SELECT query for comparison of old with new records
        - one INSERT query, if one or more records were added

        Changes are saved to the database immediately.

        :param records: list of records in presentation format
        """
        new_records = self.clean_records(records)

        # Delete RRs that are not in the new record list from the DB
        self.records.exclude(content__in=new_records).delete()  # one DELETE

        # Retrieve all remaining RRs from the DB
        unchanged_records = set(r.content for r in self.records.all())  # one SELECT

        # Save missing RRs from the new record list to the DB
        added_records = new_records - unchanged_records
        rrs = [RR(rrset=self, content=content) for content in added_records]
        RR.objects.bulk_create(rrs)  # One INSERT

    def __str__(self):
        return '<RRSet %s domain=%s type=%s subname=%s>' % (self.pk, self.domain.name, self.type, self.subname)


class RRManager(Manager):
    def bulk_create(self, rrs, **kwargs):
        ret = super().bulk_create(rrs, **kwargs)

        # For each rrset, save once to set RRset.updated timestamp and trigger signal for post-save processing
        rrsets = {rr.rrset for rr in rrs}
        for rrset in rrsets:
            rrset.save()

        return ret


class RR(ExportModelOperationsMixin('RR'), models.Model):
    created = models.DateTimeField(auto_now_add=True)
    rrset = models.ForeignKey(RRset, on_delete=models.CASCADE, related_name='records')
    content = models.TextField()

    objects = RRManager()

    _type_map = {
        dns.rdatatype.AAAA: AAAA,  # TODO remove when https://github.com/PowerDNS/pdns/issues/8182 is fixed
        dns.rdatatype.CERT: CERT,  # do DNS name validation the same way as pdns
        dns.rdatatype.MX: MX,  # do DNS name validation the same way as pdns
        dns.rdatatype.NS: NS,  # do DNS name validation the same way as pdns
        dns.rdatatype.SRV: SRV,  # do DNS name validation the same way as pdns
        dns.rdatatype.TXT: LongQuotedTXT,  # we slightly deviate from RFC 1035 and allow tokens longer than 255 bytes
        dns.rdatatype.SPF: LongQuotedTXT,  # we slightly deviate from RFC 1035 and allow tokens longer than 255 bytes
    }

    @staticmethod
    def canonical_presentation_format(any_presentation_format, type_):
        """
        Converts any valid presentation format for a RR into it's canonical presentation format.
        Raises if provided presentation format is invalid.
        """
        rdtype = rdatatype.from_text(type_)

        try:
            # Convert to wire format, ensuring input validation.
            cls = RR._type_map.get(rdtype, dns.rdata)
            wire = cls.from_text(
                rdclass=rdataclass.IN,
                rdtype=rdtype,
                tok=dns.tokenizer.Tokenizer(any_presentation_format),
                relativize=False
            ).to_digestable()

            if len(wire) > 64000:
                raise ValidationError(f'Ensure this value has no more than 64000 byte in wire format (it has {len(wire)}).')

            parser = dns.wire.Parser(wire, current=0)
            with parser.restrict_to(len(wire)):
                rdata = cls.from_wire_parser(rdclass=rdataclass.IN, rdtype=rdtype, parser=parser)

            # Convert to canonical presentation format, disable chunking of records.
            # Exempt types which have chunksize hardcoded (prevents "got multiple values for keyword argument 'chunksize'").
            chunksize_exception_types = (dns.rdatatype.OPENPGPKEY, dns.rdatatype.EUI48, dns.rdatatype.EUI64)
            if rdtype in chunksize_exception_types:
                return rdata.to_text()
            else:
                return rdata.to_text(chunksize=0)
        except binascii.Error:
            # e.g., odd-length string
            raise ValueError('Cannot parse hexadecimal or base64 record contents')
        except dns.exception.SyntaxError as e:
            # e.g., A/127.0.0.999
            if 'quote' in e.args[0]:
                raise ValueError(f'Data for {type_} records must be given using quotation marks.')
            else:
                raise ValueError(f'Record content for type {type_} malformed: {",".join(e.args)}')
        except dns.name.NeedAbsoluteNameOrOrigin:
            raise ValueError('Hostname must be fully qualified (i.e., end in a dot: "example.com.")')
        except ValueError as ex:
            # e.g., string ("asdf") cannot be parsed into int on base 10
            raise ValueError(f'Cannot parse record contents: {ex}')
        except Exception as e:
            # TODO see what exceptions raise here for faulty input
            raise e

    def __str__(self):
        return '<RR %s %s rr_set=%s>' % (self.pk, self.content, self.rrset.pk)


class AuthenticatedAction(models.Model):
    """
    Represents a procedure call on a defined set of arguments.

    Subclasses can define additional arguments by adding Django model fields and must define the action to be taken by
    implementing the `_act` method.

    AuthenticatedAction provides the `state` property which by default is a hash of the action type (defined by the
    action's class path). Other information such as user state can be included in the state hash by (carefully)
    overriding the `_state_fields` property. Instantiation of the model, if given a `state` kwarg, will raise an error
    if the given state argument does not match the state computed from `_state_fields` at the moment of instantiation.
    The same applies to the `act` method: If called on an object that was instantiated without a `state` kwargs, an
    error will be raised.

    This effectively allows hash-authenticated procedure calls by third parties as long as the server-side state is
    unaltered, according to the following protocol:

    (1) Instantiate the AuthenticatedAction subclass representing the action to be taken (no `state` kwarg here),
    (2) provide information on how to instantiate the instance, and the state hash, to a third party,
    (3) when provided with data that allows instantiation and a valid state hash, take the defined action, possibly with
        additional parameters chosen by the third party that do not belong to the verified state.
    """
    _validated = False

    class Meta:
        managed = False

    def __init__(self, *args, **kwargs):
        state = kwargs.pop('state', None)
        super().__init__(*args, **kwargs)

        if state is not None:
            self._validated = self.validate_state(state)
            if not self._validated:
                raise ValueError

    @property
    def _state_fields(self) -> list:
        """
        Returns a list that defines the state of this action (used for authentication of this action).

        Return value must be JSON-serializable.

        Values not included in the return value will not be used for authentication, i.e. those values can be varied
        freely and function as unauthenticated action input parameters.

        Use caution when overriding this method. You will usually want to append a value to the list returned by the
        parent. Overriding the behavior altogether could result in reducing the state to fewer variables, resulting
        in valid signatures when they were intended to be invalid. The suggested method for overriding is

            @property
            def _state_fields:
                return super()._state_fields + [self.important_value, self.another_added_value]

        :return: List of values to be signed.
        """
        name = '.'.join([self.__module__, self.__class__.__qualname__])
        return [name]

    @staticmethod
    def state_of(fields: list):
        state = json.dumps(fields).encode()
        h = sha256()
        h.update(state)
        return h.hexdigest()

    @property
    def state(self):
        return self.state_of(self._state_fields)

    def validate_state(self, value):
        return value == self.state

    def _act(self):
        """
        Conduct the action represented by this class.
        :return: None
        """
        raise NotImplementedError

    def act(self):
        if not self._validated:
            raise RuntimeError('Action state could not be verified.')
        return self._act()


class AuthenticatedBasicUserAction(AuthenticatedAction):
    """
    Abstract AuthenticatedAction involving a user instance.
    """
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [str(self.user.id)]


class AuthenticatedUserAction(AuthenticatedBasicUserAction):
    """
    Abstract AuthenticatedBasicUserAction, incorporating the user's id, email, password, and is_active flag into the
    Message Authentication Code state.
    """
    class Meta:
        managed = False

    @property
    def _state_fields(self):
        # TODO consider adding a "last change" attribute of the user to the state to avoid code
        # re-use after the state has been changed and changed back.
        return super()._state_fields + [self.user.email, self.user.password, self.user.is_active]

    def validate_legacy_state(self, value):
        return value == self.state_of(self._state_fields[:-1] + [False])

    def validate_state(self, value):
        is_valid = super().validate_state(value)

        # Retry with state structure before migration 0019 (activation link transition period)
        # TODO Remove once legacy links have expired (DESECSTACK_API_AUTHACTION_VALIDITY hours after deployment)
        if not is_valid and self._state_fields[-1] is None and self.user.last_login is None:
            is_valid = self.validate_legacy_state(value)

        return is_valid


class AuthenticatedActivateUserAction(AuthenticatedUserAction):
    domain = models.CharField(max_length=191)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [self.domain]

    def _act(self):
        self.user.activate()


class AuthenticatedChangeEmailUserAction(AuthenticatedUserAction):
    new_email = models.EmailField()

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [self.new_email]

    def _act(self):
        self.user.change_email(self.new_email)


class AuthenticatedNoopUserAction(AuthenticatedUserAction):

    class Meta:
        managed = False

    def _act(self):
        pass


class AuthenticatedResetPasswordUserAction(AuthenticatedUserAction):
    new_password = models.CharField(max_length=128)

    class Meta:
        managed = False

    def _act(self):
        self.user.change_password(self.new_password)


class AuthenticatedDeleteUserAction(AuthenticatedUserAction):

    class Meta:
        managed = False

    def _act(self):
        self.user.delete()


class AuthenticatedDomainBasicUserAction(AuthenticatedBasicUserAction):
    """
    Abstract AuthenticatedUserAction involving an domain instance, incorporating the domain's id, name as well as the
    owner ID into the Message Authentication Code state.
    """
    domain = models.ForeignKey(Domain, on_delete=models.DO_NOTHING)

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [
            str(self.domain.id),  # ensures the domain object is identical
            self.domain.name,  # exclude renamed domains
            str(self.domain.owner.id),  # exclude transferred domains
        ]


class AuthenticatedRenewDomainBasicUserAction(AuthenticatedDomainBasicUserAction):

    class Meta:
        managed = False

    @property
    def _state_fields(self):
        return super()._state_fields + [str(self.domain.renewal_changed)]

    def _act(self):
        self.domain.renewal_state = Domain.RenewalState.FRESH
        self.domain.renewal_changed = timezone.now()
        self.domain.save(update_fields=['renewal_state', 'renewal_changed'])


def captcha_default_content(kind: str) -> str:
    if kind == Captcha.Kind.IMAGE:
        alphabet = (string.ascii_uppercase + string.digits).translate({ord(c): None for c in 'IO0'})
        length = 5
    elif kind == Captcha.Kind.AUDIO:
        alphabet = string.digits
        length = 8
    else:
        raise ValueError(f'Unknown Captcha kind: {kind}')

    content = ''.join([secrets.choice(alphabet) for _ in range(length)])
    metrics.get('desecapi_captcha_content_created').labels(kind).inc()
    return content


class Captcha(ExportModelOperationsMixin('Captcha'), models.Model):

    class Kind(models.TextChoices):
        IMAGE = 'image'
        AUDIO = 'audio'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=24, default="")
    kind = models.CharField(choices=Kind.choices, default=Kind.IMAGE, max_length=24)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.content:
            self.content = captcha_default_content(self.kind)

    def verify(self, solution: str):
        age = timezone.now() - self.created
        self.delete()
        return (
            str(solution).upper().strip() == self.content  # solution correct
            and
            age <= settings.CAPTCHA_VALIDITY_PERIOD  # not expired
        )


class PDNSSupermaster(models.Model):
    ip = netfields.InetAddressField()
    nameserver = models.CharField(max_length=255)
    account = models.CharField(max_length=40)

    class Meta:
        unique_together = (("ip", "nameserver"),)


class PDNSComment(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10)
    modified_at = models.IntegerField()
    account = models.CharField(max_length=40)
    comment = models.CharField(max_length=65535)


class PDNSCryptokey(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE)
    flags = models.IntegerField()
    active = models.BooleanField()
    published = models.BooleanField(default=True)
    content = models.TextField()


class PDNSTsigkey(models.Model):
    name = models.CharField(max_length=255)
    algorithm = models.CharField(max_length=50)
    secret = models.CharField(max_length=255)

    class Meta:
        unique_together = (("name", "algorithm"),)
