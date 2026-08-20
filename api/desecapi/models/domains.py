from __future__ import annotations

from functools import cached_property

import dns
import psl_dns
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CharField, F, Manager, Q, Value
from django.db.models.functions import Concat, Length
from django_prometheus.models import ExportModelOperationsMixin
from dns.exception import Timeout
from dns.resolver import NoNameservers
from rest_framework.exceptions import APIException

from desecapi import logger, metrics, pdns

from .base import validate_domain_name
from .records import RR, RRset


psl = psl_dns.PSL(resolver=settings.PSL_RESOLVER, timeout=0.5)

DELEGATION_NS_TTL = 3600
DELEGATION_DS_TTL = 300


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

    def parent_zone(self, name: str, *, exclude=()) -> Domain | None:
        """
        Returns the closest ancestor domain of the given name that exists in the database,
        ignoring the domains given by `exclude`, or None if there is none. No ownership check
        is performed; callers who need one have to do it themselves.
        """
        return (
            self.filter_qname(name)
            .exclude(name__in=[name, *exclude])
            .order_by("-name_length")
            .first()
        )


class Domain(ExportModelOperationsMixin("Domain"), models.Model):
    @staticmethod
    def _minimum_ttl_default():
        return settings.MINIMUM_TTL_DEFAULT

    class RenewalState(models.IntegerChoices):
        IMMORTAL = 0
        FRESH = 1
        NOTIFIED = 2
        WARNED = 3

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

        # Domains registered under a local public suffix can't have subdomains registered
        if (
            private_generation > 1
            and self.public_suffix in settings.LOCAL_PUBLIC_SUFFIXES
        ):
            parent_zone = self.parent_zone
            # Both names are suffixes of self.name, so the longer one is the deeper one
            if parent_zone is not None and len(parent_zone.name) > len(
                self.public_suffix
            ):
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
            self._keys = [{**key, "managed": True} for key in pdns.get_keys(self)]
            try:
                unmanaged_keys = (
                    self.rrset_set.get(subname="", type="DNSKEY")
                    .records.order_by("content")
                    .all()
                )
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
        parent_zone = self.parent_zone
        return (
            parent_zone is not None
            and parent_zone.name in settings.LOCAL_PUBLIC_SUFFIXES
        )

    @property
    def _owner_or_none(self):
        try:
            return self.owner
        except Domain.owner.RelatedObjectDoesNotExist:
            return None

    @property
    def delegation_parent(self) -> Domain | None:
        """
        Returns the domain in which this domain's delegation is maintained automatically,
        or None if there is none.
        """
        parent_zone = self.parent_zone
        if parent_zone is not None and (
            parent_zone.owner_id == self.owner_id
            or parent_zone.name in settings.LOCAL_PUBLIC_SUFFIXES
        ):
            return parent_zone
        return None

    def delegation_error(self) -> str | None:
        """
        Returns why this domain cannot be delegated by the domain that would delegate it, or
        None if nothing stands in the way (or if there is no such domain).
        """
        parent = self.delegation_parent
        if parent is None:
            return None
        subname = parent._delegation_subname(self.name)
        max_length = RRset._meta.get_field("subname").max_length
        if len(subname) > max_length:
            return (
                f"Cannot delegate {self.name} in {parent.name}: the name of the delegation "
                f"point exceeds {max_length} characters."
            )
        if parent.rrset_set.filter(subname=subname, type="CNAME").exists():
            return (
                f"Cannot delegate {self.name} in {parent.name}: there is a CNAME RRset at "
                f"this name."
            )
        return None

    @property
    def ds_contents(self) -> list[str]:
        return [ds for key in self.keys for ds in key["ds"]]

    @property
    def parent_zone(self) -> Domain | None:
        # Not cached: creating or deleting an intermediate domain changes the result.
        return Domain.objects.parent_zone(self.name)

    @property
    def zonefile(self):
        return pdns.get_zonefile(self)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False)
        super().save(*args, **kwargs)

    def _delegation_subname(self, child_name: str) -> str:
        if not child_name.endswith(f".{self.name}"):
            raise ValueError(
                "Cannot delegate %s in %s, as it is not a child domain."
                % (child_name, self.name)
            )
        return child_name.removesuffix(f".{self.name}")

    def _update_delegation_rrset(
        self, subname: str, type_: str, ttl: int, *, add=(), remove=()
    ) -> set[str]:
        """
        Adds and removes the given record contents at the given name, creating or deleting the
        RRset as needed (an existing RRset keeps its TTL). Returns the resulting contents.
        """
        add = {RR.canonical_presentation_format(content, type_) for content in add}
        remove = {
            RR.canonical_presentation_format(content, type_) for content in remove
        }
        try:
            rrset = self.rrset_set.get(subname=subname, type=type_)
        except RRset.DoesNotExist:
            if add:
                RRset.objects.create(
                    domain=self, subname=subname, type=type_, ttl=ttl, contents=add
                )
            return add

        contents = ({rr.content for rr in rrset.records.all()} - remove) | add
        if contents:
            rrset.save_records(contents)
        else:
            rrset.delete()
        return contents

    def add_delegation(self, child_name: str, ds: list[str]) -> None:
        """
        Adds our NS records and the given DS records to the delegation of the given child
        domain, keeping any records that are there already.
        """
        subname = self._delegation_subname(child_name)
        # TODO Joining a delegation that carries foreign NS/DS records makes the child domain
        #  multi-signer (RFC 8901). Automating this requires importing the other providers'
        #  ZSKs into the child's DNSKEY RRset (and exporting the child's ZSK to them); until
        #  then, such setups have to be configured manually.
        self._update_delegation_rrset(
            subname, "NS", DELEGATION_NS_TTL, add=settings.DEFAULT_NS
        )
        self._update_delegation_rrset(subname, "DS", DELEGATION_DS_TTL, add=ds)
        metrics.get("desecapi_autodelegation_created").inc()

    def remove_delegation(self, child_name: str, ds: list[str]) -> None:
        """
        Removes our NS records and the given DS records from the delegation of the given child
        domain, keeping any other records. If no NS records remain, the delegation is removed
        entirely.
        """
        subname = self._delegation_subname(child_name)
        ns = self._update_delegation_rrset(
            subname, "NS", DELEGATION_NS_TTL, remove=settings.DEFAULT_NS
        )
        if ns:
            self._update_delegation_rrset(subname, "DS", DELEGATION_DS_TTL, remove=ds)
        else:
            # DS records are only allowed at a delegation point
            self.rrset_set.filter(subname=subname, type="DS").delete()
        metrics.get("desecapi_autodelegation_deleted").inc()

    def auto_delegate(self) -> None:
        """
        Creates this domain's delegation in the domain that delegates it, if any.
        """
        parent = self.delegation_parent
        if parent is None:
            return
        if not self.keys:
            raise APIException(
                "Cannot delegate %s, as it currently has no keys." % self.name
            )
        parent.add_delegation(self.name, self.ds_contents)

    def delegation_state(self):
        """
        Returns what is needed to withdraw this domain's delegation. Has to be called before
        deleting the domain, while its DNSSEC keys are still available.
        """
        parent = self.delegation_parent
        return parent, self.ds_contents if parent is not None else []

    def auto_undelegate(self, delegation_state) -> None:
        """
        Removes this domain's delegation from the domain that delegated it, using the state
        captured by delegation_state() before the domain was deleted.
        """
        parent, ds = delegation_state
        if parent is not None:
            parent.remove_delegation(self.name, ds)

    def delete(self, *args, **kwargs):
        ret = super().delete(*args, **kwargs)
        logger.warning(f"Domain {self.name} deleted (owner: {self.owner.pk})")
        return ret

    def __str__(self):
        return self.name
