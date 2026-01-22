from datetime import timezone, datetime

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

from desecapi import permissions
from desecapi.delegation import DelegationChecker
from desecapi.models import Domain
from desecapi.pdns import get_serials
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import DomainSerializer

from .base import IdempotentDestroyMixin


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
                    ret.append(permissions.WithinInsecureDelegatedDomainLimit)
                case "destroy":
                    ret.append(permissions.HasDeleteDomainPermission)
                case "delegation_check":
                    pass
                case _:
                    raise ValueError(f"Invalid action: {self.action}")
        return ret

    @property
    def throttle_scope(self):
        if self.action == "delegation_check":
            return "delegation_check"
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
        with PDNSChangeTracker():
            domain = serializer.save(owner=self.request.user)
            if self.request.auth.auto_policy:
                self.request.auth.tokendomainpolicy_set.create(
                    domain=domain, perm_write=True
                )

        # TODO this line raises if the local public suffix is not in our database!
        PDNSChangeTracker.track(lambda: self.auto_delegate(domain))

    @staticmethod
    def auto_delegate(domain: Domain):
        if domain.is_locally_registrable:
            parent_domain = Domain.objects.get(name=domain.parent_domain_name)
            parent_domain.update_delegation(domain)

    def perform_destroy(self, instance: Domain):
        with PDNSChangeTracker():
            instance.delete()
        if instance.is_locally_registrable:
            parent_domain = Domain.objects.get(name=instance.parent_domain_name)
            with PDNSChangeTracker():
                parent_domain.update_delegation(instance)

    @action(detail=True, renderer_classes=[PlainTextRenderer])
    def zonefile(self, request, name=None):
        instance = self.get_object()
        prefix = f"; Zonefile for {instance.name} exported from desec.{settings.DESECSTACK_DOMAIN} at {datetime.now(timezone.utc)}\n".encode()
        return Response(prefix + instance.zonefile, content_type="text/dns")

    @action(detail=True, methods=["post"])
    def delegation_check(self, request, name=None):
        instance = self.get_object()
        checker = DelegationChecker()
        update = checker.check_domain(instance)
        instance.delegation_checked = update["delegation_checked"]
        instance.is_registered = update["is_registered"]
        instance.has_all_nameservers = update["has_all_nameservers"]
        instance.is_delegated = update["is_delegated"]
        instance.is_secured = update["is_secured"]
        instance.save(
            update_fields=[
                "delegation_checked",
                "is_registered",
                "has_all_nameservers",
                "is_delegated",
                "is_secured",
            ]
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


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
