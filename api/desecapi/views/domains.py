from datetime import timezone, datetime
import logging

import dns.rdata
import dns.rdataclass
import dns.rdatatype
from django.conf import settings
from django.core.cache import cache
from django.db.models import Subquery
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from desecapi import dnssec, knot, nslord, pdns, permissions
from desecapi.models import Domain
from desecapi.pdns import get_serials
from desecapi.pdns_change_tracker import NSLordChangeTracker
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import DomainSerializer

from .base import IdempotentDestroyMixin

logger = logging.getLogger(__name__)


class DomainViewSet(
    IdempotentDestroyMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DomainSerializer
    lookup_field = "name"
    lookup_value_regex = r"[^/]+"

    @property
    def permission_classes(self):
        ret = [
            IsAuthenticated,
            permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
            permissions.IsOwner,
        ]
        if self.request.method not in SAFE_METHODS:
            match self.action:
                case None:
                    pass  # occurs when HTTP method is not allowed; leads to status 405
                case "create":
                    ret.append(permissions.HasCreateDomainPermission)
                    ret.append(permissions.WithinDomainLimit)
                case "destroy":
                    ret.append(permissions.HasDeleteDomainPermission)
                case "nslord":
                    ret.append(permissions.HasCreateDomainPermission)
                    ret.append(permissions.HasDeleteDomainPermission)
                case _:
                    raise ValueError(f"Invalid action: {self.action}")
        return ret

    @property
    def throttle_scope(self):
        if self.action == "zonefile":
            self.throttle_scope_bucket = self.kwargs["name"]
            return "dns_api_per_domain_expensive"
        else:
            return (
                "dns_api_cheap"
                if self.request.method in SAFE_METHODS
                else "dns_api_expensive"
            )

    @property
    def pagination_class(self):
        # Turn off pagination when filtering for covered qname, as pagination would re-order by `created` (not what we
        # want here) after taking a slice (that's forbidden anyway). But, we don't need pagination in this case anyways.
        if "owns_qname" in self.request.query_params:
            return None
        else:
            return api_settings.DEFAULT_PAGINATION_CLASS

    @property
    def domain(self):
        return self.get_object()

    def get_queryset(self):
        qs = self.request.user.domains
        policy_set = self.request.auth.tokendomainpolicy_set

        if self.request.auth.user_override is not None and policy_set.exists():
            qs = qs.filter(pk__in=Subquery(policy_set.values("domain")))

        owns_qname = self.request.query_params.get("owns_qname")
        if owns_qname is not None:
            qs = qs.filter_qname(owns_qname).order_by("-name_length")[:1]

        return qs

    def get_serializer(self, *args, **kwargs):
        include_keys = self.action in ["create", "retrieve"]
        return super().get_serializer(*args, include_keys=include_keys, **kwargs)

    def perform_create(self, serializer):
        domain = Domain(name=serializer.validated_data["name"])
        if not settings.REGISTER_LPS and domain.is_locally_registrable:
            raise ValidationError(
                {
                    "name": [
                        f"Domain registration under {domain.parent_domain_name} is currently suspended."
                    ]
                },
                code="registration_suspended",
            )
        with NSLordChangeTracker():
            domain = serializer.save(owner=self.request.user)
            if self.request.auth.auto_policy:
                self.request.auth.tokendomainpolicy_set.create(
                    domain=domain, perm_write=True
                )

        # TODO this line raises if the local public suffix is not in our database!
        NSLordChangeTracker.track(lambda: self.auto_delegate(domain))

    @staticmethod
    def auto_delegate(domain: Domain):
        if domain.is_locally_registrable:
            parent_domain = Domain.objects.get(name=domain.parent_domain_name)
            parent_domain.update_delegation(domain)

    def perform_destroy(self, instance: Domain):
        with NSLordChangeTracker():
            instance.delete()
        if instance.is_locally_registrable:
            parent_domain = Domain.objects.get(name=instance.parent_domain_name)
            with NSLordChangeTracker():
                parent_domain.update_delegation(instance)

    @action(detail=True, renderer_classes=[PlainTextRenderer])
    def zonefile(self, request, name=None):
        instance = self.get_object()
        prefix = f"; Zonefile for {instance.name} exported from desec.{settings.DESECSTACK_DOMAIN} at {datetime.now(timezone.utc)}\n".encode()
        return Response(prefix + instance.zonefile, content_type="text/dns")

    @action(detail=True, methods=["post"])
    def nslord(self, request, name=None):
        domain = self.get_object()
        target = request.data.get("nslord")
        logger.info("nslord move requested for %s: target=%s", domain.name, target)
        if target not in Domain.NSLord.values:
            raise ValidationError({"nslord": ["Invalid nslord value."]})
        if target == domain.nslord:
            return Response(self.get_serializer(domain).data)

        private_key = nslord.get_csk_private_key(domain)
        if not private_key:
            raise ValidationError({"nslord": ["No CSK private key available."]})
        if domain.get_csk_private_key() is None:
            domain.set_csk_private_key(private_key)
        dnskey = dnssec.parse_csk_private_key(private_key)["dnskey"]
        try:
            key_rdata = dns.rdata.from_text(
                dns.rdataclass.IN, dns.rdatatype.DNSKEY, dnskey
            )
            logger.info(
                "nslord move %s: CSK alg=%d keytag=%d",
                domain.name,
                key_rdata.algorithm,
                dns.dnssec.key_id(key_rdata),
            )
        except Exception:
            logger.info("nslord move %s: CSK parse failed", domain.name)
        zonefile = nslord.get_zonefile_without_dnssec(domain).decode()
        rrsets = nslord.zonefile_to_rrsets(domain.name, zonefile)
        zonefile_serial = None
        for rrset in rrsets:
            if rrset["type"] == "SOA" and rrset["records"]:
                soa_rdata = dns.rdata.from_text(
                    dns.rdataclass.IN, dns.rdatatype.SOA, rrset["records"][0]
                )
                zonefile_serial = soa_rdata.serial
                break
        old_serial = nslord.get_soa_serial(domain) or zonefile_serial
        if zonefile_serial is None:
            logger.warning(
                "nslord move %s: SOA serial not found in zonefile", domain.name
            )
        else:
            logger.info(
                "nslord move %s: zonefile SOA serial=%d",
                domain.name,
                zonefile_serial,
            )
        if old_serial is not None and old_serial != zonefile_serial:
            logger.info("nslord move %s: DNS SOA serial=%d", domain.name, old_serial)
        logger.info(
            "nslord move %s: rrsets=%d zonefile_bytes=%d",
            domain.name,
            len(rrsets),
            len(zonefile),
        )

        if target == Domain.NSLord.PDNS:
            logger.info("nslord move %s: creating zone on PDNS", domain.name)
            pdns.create_zone_lord(domain.name)
            pdns.import_csk_key(domain.name, dnskey=dnskey, private_key=private_key)
            pdns.import_zonefile_rrsets(domain.name, rrsets)
        else:
            logger.info("nslord move %s: creating zone on Knot", domain.name)
            knot.prepare_csk_key(domain.name, dnskey=dnskey, private_key=private_key)
            knot.create_zone(domain.name)
            knot.wait_for_csk_key_ready(domain.name)
            knot.ensure_default_ns(domain.name)
            knot.import_zonefile_rrsets(domain.name, rrsets)
            if old_serial is not None:
                knot.ensure_soa_serial_min(domain.name, old_serial)
            knot.import_csk_key(domain.name, dnskey=dnskey, private_key=private_key)

        pdns.delete_zone_master(domain.name)
        master_host = (
            settings.NSLORD_KNOT_HOST if target == Domain.NSLord.KNOT else "nslord"
        )
        logger.info(
            "nslord move %s: updating nsmaster master_host=%s",
            domain.name,
            master_host,
        )
        pdns.create_zone_master(domain.name, master_host=master_host)
        pdns.axfr_to_master(domain.name)
        if target == Domain.NSLord.PDNS:
            if not pdns.wait_for_master_zone(domain.name):
                logger.warning(
                    "nslord move %s: nsmaster zone not ready after AXFR trigger",
                    domain.name,
                )

        old_nslord = domain.nslord
        domain.nslord = target
        domain.save(update_fields=["nslord"])

        if old_nslord == Domain.NSLord.PDNS:
            logger.info("nslord move %s: deleting zone from PDNS", domain.name)
            pdns.delete_zone_lord(domain.name)
        else:
            logger.info("nslord move %s: deleting zone from Knot", domain.name)
            knot.delete_zone(domain.name)

        return Response(self.get_serializer(domain).data)


class SerialListView(APIView):
    permission_classes = (permissions.IsVPNClient,)
    throttle_classes = []  # don't break secondaries when they ask too often (our cached responses are cheap)

    def get(self, request, *args, **kwargs):
        key = "desecapi.views.serials"
        serials = cache.get(key)
        if serials is None:
            serials = get_serials()
            cache.get_or_set(key, serials, timeout=60)
        return Response(serials)
