from __future__ import annotations

from functools import cache, cached_property
from socket import getaddrinfo

import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes
import dns.resolver
import psl_dns
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CharField, F, Manager, Q, Value
from django.db.models.functions import Concat, Length
from django.utils import timezone
from django_prometheus.models import ExportModelOperationsMixin
from dns.exception import Timeout
from dns.resolver import NoNameservers
from rest_framework.exceptions import APIException

from desecapi import logger, metrics, pdns

from .base import validate_domain_name
from .records import RRset


psl = psl_dns.PSL(resolver=settings.PSL_RESOLVER, timeout=0.5)

# CHECKING DISABLED general-purpose resolver for queries to the public DNS
resolver_CD = dns.resolver.Resolver(configure=False)
resolver_CD.nameservers = settings.RESOLVERS
resolver_CD.flags = (resolver_CD.flags or 0) | dns.flags.CD | dns.flags.AD | dns.flags.RD


class DomainManager(Manager):
    def filter_qname(self, qname: str, **kwargs) -> models.query.QuerySet:
        qs = self.annotate(
            name_length=Length("name")
        )  # callers expect this to be present after returning
        try:
            Domain._meta.get_field("name").run_validators(
                qname.removeprefix("*.").lower()
            )
        except ValidationError:
            return qs.none()
        return qs.annotate(
            dotted_name=Concat(Value("."), "name", output_field=CharField()),
            dotted_qname=Value(f".{qname}", output_field=CharField()),
        ).filter(dotted_qname__endswith=F("dotted_name"), **kwargs)


class Domain(ExportModelOperationsMixin("Domain"), models.Model):
    @staticmethod
    def _minimum_ttl_default():
        return settings.MINIMUM_TTL_DEFAULT

    class RenewalState(models.IntegerChoices):
        IMMORTAL = 0
        FRESH = 1
        NOTIFIED = 2
        WARNED = 3

    class DelegationStatus(models.IntegerChoices):
        NOT_DELEGATED = 0
        ELSEWHERE = 1
        PARTIAL = 2
        EXCLUSIVE = 3
        MULTI = 4
        ERROR_NXDOMAIN = 128
        ERROR_NO_NAMESERVERS = 129
        ERROR_TIMEOUT = 130

    class SecurityStatus(models.IntegerChoices):
        INSECURE = 0
        FOREIGN_KEYS = 1
        SECURE_EXCLUSIVE = 2
        SECURE = 3
        ERROR_NXDOMAIN = 128
        ERROR_NO_NAMESERVERS = 130
        ERROR_TIMEOUT = 131

    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(
        max_length=191, unique=True, validators=validate_domain_name
    )
    owner = models.ForeignKey("User", on_delete=models.PROTECT, related_name="domains")
    published = models.DateTimeField(null=True, blank=True)
    minimum_ttl = models.PositiveIntegerField(default=_minimum_ttl_default.__func__)
    renewal_state = models.IntegerField(
        choices=RenewalState.choices, db_index=True, default=RenewalState.IMMORTAL
    )
    renewal_changed = models.DateTimeField(auto_now_add=True)
    delegation_status = models.IntegerField(
        choices=DelegationStatus.choices,
        default=None,
        null=True,
        blank=True,
    )
    delegation_status_touched = models.DateTimeField(
        default=None, null=True, blank=True
    )
    delegation_status_changed = models.DateTimeField(
        default=None, null=True, blank=True
    )
    security_status = models.IntegerField(
        choices=SecurityStatus.choices,
        default=None,
        null=True,
        blank=True,
    )
    security_status_touched = models.DateTimeField(default=None, null=True, blank=True)
    security_status_changed = models.DateTimeField(default=None, null=True, blank=True)

    _keys = None
    objects = DomainManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "owner"], name="unique_id_owner")
        ]
        ordering = ("created",)

    def __init__(self, *args, **kwargs):
        if isinstance(kwargs.get("owner"), AnonymousUser):
            kwargs = {**kwargs, "owner": None}  # make a copy and override
        # Avoid super().__init__(owner=None, ...) to not mess up *values instantiation in django.db.models.Model.from_db
        super().__init__(*args, **kwargs)
        if (
            # self._state.adding may be incorrect during signal processing (change tracker)
            self.pk is None
            and kwargs.get("renewal_state") is None
            and self.is_locally_registrable
        ):
            self.renewal_state = Domain.RenewalState.FRESH

    @cached_property
    def public_suffix(self):
        try:
            public_suffix = psl.get_public_suffix(self.name)
            is_public_suffix = psl.is_public_suffix(self.name)
        except (Timeout, NoNameservers):
            public_suffix = self.name.rpartition(".")[2]
            is_public_suffix = "." not in self.name  # TLDs are public suffixes

        if is_public_suffix:
            return public_suffix

        # Take into account that any of the parent domains could be a local public suffix. To that
        # end, identify the longest local public suffix that is actually a suffix of domain_name.
        for local_public_suffix in settings.LOCAL_PUBLIC_SUFFIXES:
            has_local_public_suffix_parent = ("." + self.name).endswith(
                "." + local_public_suffix
            )
            if has_local_public_suffix_parent and len(local_public_suffix) > len(
                public_suffix
            ):
                public_suffix = local_public_suffix

        return public_suffix

    def is_covered_by_foreign_zone(self):
        # Generate a list of all domains connecting this one and its public suffix.
        # If another user owns a zone with one of these names, then the requested
        # domain is unavailable because it is part of the other user's zone.
        private_components = self.name.rsplit(self.public_suffix, 1)[0].rstrip(".")
        private_components = private_components.split(".") if private_components else []
        private_domains = [
            ".".join(private_components[i:]) for i in range(0, len(private_components))
        ]
        private_domains = [
            f"{private_domain}.{self.public_suffix}"
            for private_domain in private_domains
        ]
        assert self.name == next(iter(private_domains), self.public_suffix)

        # Determine whether domain is covered by other users' zones
        return Domain.objects.filter(
            Q(name__in=private_domains) & ~Q(owner=self._owner_or_none)
        ).exists()

    def covers_foreign_zone(self):
        # Note: This is not completely accurate: Ideally, we should only consider zones with identical public suffix.
        # (If a public suffix lies in between, it's ok.) However, as there could be many descendant zones, the accurate
        # check is expensive, so currently not implemented (PSL lookups for each of them).
        return Domain.objects.filter(
            Q(name__endswith=f".{self.name}") & ~Q(owner=self._owner_or_none)
        ).exists()

    def is_registrable(self):
        """
        Returns False if the domain name is reserved, a public suffix, or covered by / covers another user's domain.
        Otherwise, True is returned.
        """
        self.clean()  # ensure .name is a domain name
        private_generation = self.name.count(".") - self.public_suffix.count(".")
        assert private_generation >= 0

        # .internal is reserved
        if f".{self.name}".endswith(".internal"):
            return False

        # Public suffixes can only be registered if they are local
        if private_generation == 0 and self.name not in settings.LOCAL_PUBLIC_SUFFIXES:
            return False

        # Disallow _acme-challenge.dedyn.io and the like. Rejects reserved direct children of public suffixes.
        reserved_prefixes = (
            "_",
            "autoconfig.",
            "autodiscover.",
        )
        if private_generation == 1 and any(
            self.name.startswith(prefix) for prefix in reserved_prefixes
        ):
            return False

        # Domains covered by another user's zone can't be registered
        if self.is_covered_by_foreign_zone():
            return False

        # Domains that would cover another user's zone can't be registered
        if self.covers_foreign_zone():
            return False

        return True

    @staticmethod
    @cache  # located at object-level to start with clear cache for new objects
    def _lookup(target) -> set[str]:
        try:
            addrinfo = getaddrinfo(str(target), None)
        except OSError:
            return set()
        return {v[-1][0] for v in addrinfo}

    def update_dns_delegation_status(self) -> DelegationStatus:
        """Queries the DNS to determine the delegation status of this domian and
        update the delegation status on record."""
        old_delegation_status = self.delegation_status
        our_ns_names = {dns.name.from_text(ns) for ns in settings.DEFAULT_NS}

        try:
            auth_ns_names = {
                rr.target for rr in resolver_CD.resolve(self.name, dns.rdatatype.NS, raise_on_no_answer=False)
            }
        except dns.resolver.NXDOMAIN:
            self.delegation_status = self.DelegationStatus.ERROR_NXDOMAIN
        except dns.resolver.NoNameservers:
            self.delegation_status = self.DelegationStatus.ERROR_NO_NAMESERVERS
        except dns.resolver.LifetimeTimeout:
            self.delegation_status = self.DelegationStatus.ERROR_TIMEOUT
        else:

            if our_ns_names == auth_ns_names:
                # just ours
                self.delegation_status = self.DelegationStatus.EXCLUSIVE
            elif our_ns_names < auth_ns_names:
                # all of ours, and others
                self.delegation_status = self.DelegationStatus.MULTI
            elif our_ns_names & auth_ns_names:
                # some of ours, and others
                self.delegation_status = self.DelegationStatus.PARTIAL
            elif auth_ns_names:
                # none of ours, but not empty
                self.delegation_status = self.DelegationStatus.ELSEWHERE
            elif auth_ns_names == set():
                # empty
                self.delegation_status = self.DelegationStatus.NOT_DELEGATED
            elif auth_ns_names is None:
                # error
                self.delegation_status = self.DelegationStatus

        now = timezone.now()
        self.delegation_status_touched = now
        if old_delegation_status != self.delegation_status:
            self.delegation_status_changed = now
        return self.delegation_status

    def update_dns_security_status(self) -> SecurityStatus:
        """Queries the DNS to determine the security status of this domain and
        updates the security status on record."""
        old_security_status = self.security_status

        if self.delegation_status not in [
            self.DelegationStatus.MULTI,
            self.DelegationStatus.EXCLUSIVE,
        ]:
            self.security_status = None
            return None

        try:
            auth_ds = set(resolver_CD.resolve(self.name, dns.rdatatype.DS, raise_on_no_answer=False))
        except dns.resolver.NXDOMAIN:
            self.security_status = self.SecurityStatus.ERROR_NXDOMAIN
        except dns.resolver.NoNameservers:
            self.delegation_status = self.SecurityStatus.ERROR_NO_NAMESERVERS
        except dns.resolver.LifetimeTimeout:
            self.delegation_status = self.SecurityStatus.ERROR_TIMEOUT
        else:
            auth_ds = {ds for ds in auth_ds if ds.digest_type == 2}

            # Compute overlap of delegation DS records with ours
            our_ds_set = {
                dns.rdata.from_text(rdclass="IN", rdtype="DS", tok=ds)
                for key in self.keys
                for ds in key.get("ds", [])
                if dns.rdata.from_text(rdclass="IN", rdtype="DS", tok=ds).digest_type
                == 2  # only digest type 2 is mandatory
            }

            if our_ds_set == auth_ds:
                self.security_status = self.SecurityStatus.SECURE_EXCLUSIVE
            elif our_ds_set < auth_ds:
                self.security_status = self.SecurityStatus.SECURE
            elif auth_ds != set():
                self.security_status = self.SecurityStatus.FOREIGN_KEYS
            else:
                self.security_status = self.SecurityStatus.INSECURE

        now = timezone.now()
        self.security_status_touched = now
        if old_security_status != self.security_status:
            self.security_status_changed = now
        return self.security_status

    @property
    def keys(self):
        if not self._keys:
            self._keys = [{**key, "managed": True} for key in pdns.get_keys(self)]
            try:
                unmanaged_keys = self.rrset_set.get(
                    subname="", type="DNSKEY"
                ).records.all()
            except RRset.DoesNotExist:
                pass
            else:
                name = dns.name.from_text(self.name)
                for rr in unmanaged_keys:
                    key = dns.rdata.from_text(
                        dns.rdataclass.IN, dns.rdatatype.DNSKEY, rr.content
                    )
                    key_is_sep = key.flags & dns.rdtypes.ANY.DNSKEY.SEP
                    self._keys.append(
                        {
                            "dnskey": rr.content,
                            "ds": (
                                [
                                    dns.dnssec.make_ds(name, key, algo).to_text()
                                    for algo in (2, 4)
                                ]
                                if key_is_sep
                                else []
                            ),
                            "flags": key.flags,  # deprecated
                            "keytype": None,  # deprecated
                            "managed": False,
                        }
                    )
        return self._keys

    @property
    def touched(self):
        try:
            rrset_touched = max(
                updated for updated in self.rrset_set.values_list("touched", flat=True)
            )
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
        subname, _, parent_name = self.name.partition(".")
        return subname, parent_name or None

    @property
    def zonefile(self):
        return pdns.get_zonefile(self)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def update_delegation(self, child_domain: Domain):
        child_subname, child_domain_name = child_domain._partitioned_name
        if self.name != child_domain_name:
            raise ValueError(
                "Cannot update delegation of %s as it is not an immediate child domain of %s."
                % (child_domain.name, self.name)
            )

        # Always remove delegation so that we con properly recreate it
        for rrset in self.rrset_set.filter(
            subname=child_subname, type__in=["NS", "DS"]
        ):
            rrset.delete()

        if child_domain.pk:
            # Domain real: (re-)set delegation
            child_keys = child_domain.keys
            if not child_keys:
                raise APIException(
                    "Cannot delegate %s, as it currently has no keys."
                    % child_domain.name
                )

            RRset.objects.create(
                domain=self,
                subname=child_subname,
                type="NS",
                ttl=3600,
                contents=settings.DEFAULT_NS,
            )
            RRset.objects.create(
                domain=self,
                subname=child_subname,
                type="DS",
                ttl=300,
                contents=[ds for k in child_keys for ds in k["ds"]],
            )
            metrics.get("desecapi_autodelegation_created").inc()
        else:
            # Domain not real: that's it
            metrics.get("desecapi_autodelegation_deleted").inc()

    def delete(self, *args, **kwargs):
        ret = super().delete(*args, **kwargs)
        logger.warning(f"Domain {self.name} deleted (owner: {self.owner.pk})")
        return ret

    def __str__(self):
        return self.name
