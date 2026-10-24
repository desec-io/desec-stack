from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Subquery
from django.utils import timezone
from kombu.exceptions import OperationalError
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from desecapi import logger, permissions
from desecapi.models import Domain
from desecapi.pdns import get_serials
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import DomainSerializer, DomainStatusSerializer
from desecapi.tasks import (
    enqueue_domain_delegation_check,
    enqueue_user_delegation_check,
    status_check_wanted,
)

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
            permissions.MFARequiredIfEnabledOrAPIToken,
            permissions.IsOwner,
        ]
        if self.action == "status":
            # Reading is open to any token. A re-check is about the limit,
            # which concerns only tokens that can create domains; others thus
            # cannot use up the account's re-check budget as a side effect.
            if self.request.method == "POST":
                ret.append(permissions.HasCreateDomainPermission)
            return ret
        match self.request.method:
            case "POST":
                ret.append(permissions.HasCreateDomainPermission)
                ret.append(permissions.WithinDomainLimit)
            case "DELETE":
                ret.append(permissions.HasDeleteDomainPermission)
            case method if (
                method not in SAFE_METHODS and method.lower() in self.action_map
            ):
                raise RuntimeError(f"Missing permission for: {method}")
        return ret

    @property
    def throttle_scope(self):
        if self.action == "zonefile":
            self.throttle_scope_bucket = self.kwargs["name"]
            return "dns_api_per_domain_expensive"
        elif self._is_status_check:
            # Each check queries third-party nameservers.
            self.throttle_scope_bucket = self.kwargs["name"]
            return "dns_api_per_domain_status_check"
        else:
            return (
                "dns_api_cheap"
                if self.request.method in SAFE_METHODS
                else "dns_api_expensive"
            )

    @property
    def throttle_scope_account(self):
        # Re-checks share one queue across users, so one account's burst would
        # delay everyone else's.
        return "dns_api_status_check" if self._is_status_check else None

    @property
    def _is_status_check(self):
        return self.action == "status" and self.request.method == "POST"

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
            qs = qs.filter_qname(owns_qname).order_by("-name_length")

        # The status field reads the current check, which would otherwise cost
        # a query per domain in the list.
        qs = qs.select_related("current_delegation_check")
        return qs[:1] if owns_qname is not None else qs

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
        if domain.is_locally_registrable and self.request.user.limit_domains is None:
            # These are free, and we secure them ourselves rather than the
            # user doing it, so without a cap an account could hold any number
            # of domains that are correctly delegated at no cost to it. One per
            # account also matches what the names are for: a dynDNS host, not
            # an inventory. An account whose limit support has pinned is
            # exempt: that limit is the decision on how much it may hold.
            registered = self.request.user.domains.under_local_public_suffix().first()
            if registered is not None:
                suffixes = ", ".join(sorted(settings.LOCAL_PUBLIC_SUFFIXES))
                raise ValidationError(
                    {
                        "name": [
                            f"You already have {registered.name}. Only one domain "
                            f"under {suffixes} can be registered per account; "
                            "please delete it first if you would like a different "
                            "name."
                        ]
                    },
                    code="local_domain_limit_exceeded",
                )
        with PDNSChangeTracker():
            domain = serializer.save(owner=self.request.user)
            if self.request.auth.auto_policy:
                self.request.auth.tokendomainpolicy_set.create(
                    domain=domain, perm_write=True
                )

        # TODO this line raises if the local public suffix is not in our database!
        PDNSChangeTracker.track(lambda: self.auto_delegate(domain))

        # Creating a domain is when the user is thinking about delegation, so
        # it is a good moment to re-measure the ones they have not secured yet:
        # what raises their limit is the state of those, not of this one.
        user = self.request.user
        transaction.on_commit(lambda: enqueue_user_delegation_check(user))

    def permission_denied(self, request, message=None, code=None):
        if code == permissions.WithinDomainLimit.code:
            # The user is at the wall right now, which is when a fresh
            # measurement is worth most: securing a domain raises the limit.
            enqueue_user_delegation_check(request.user)
        super().permission_denied(request, message, code)

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

    @action(detail=True, methods=["get", "post"])
    def status(self, request, name=None):
        """
        GET returns what the delegation checks found. POST asks for a re-check,
        unless what is known already answers it (status_check_wanted()): 202
        when a check is coming, 200 when it is not.
        """
        domain = self.get_object()
        if request.method == "POST" and status_check_wanted(domain):
            requested = timezone.now()
            try:
                enqueue_domain_delegation_check(domain)
            except OperationalError:
                logger.exception("Could not enqueue delegation check for %s", domain)
                return Response(
                    {"detail": "Checks are currently unavailable. Please try later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            data = DomainStatusSerializer(domain).data
            # Server time, so that clients can tell when the result is in
            # (checked >= requested) without comparing against their own clock.
            data["requested"] = serializers.DateTimeField().to_representation(requested)
            return Response(data, status=status.HTTP_202_ACCEPTED)
        return Response(DomainStatusSerializer(domain).data)

    @action(detail=True, renderer_classes=[PlainTextRenderer])
    def zonefile(self, request, name=None):
        instance = self.get_object()
        prefix = f"; Zonefile for {instance.name} exported from desec.{settings.DESECSTACK_DOMAIN} at {datetime.now(UTC)}\n".encode()
        return Response(prefix + instance.zonefile, content_type="text/dns")


class SerialListView(APIView):
    permission_classes = (permissions.IsVPNClient,)
    throttle_classes = []  # don't break secondaries when they ask too often (our cached responses are cheap)

    def get(self, request, *args, **kwargs):
        key = "desecapi.views.serials"
        # Determine if the last update is older than 60s and nobody is working on it
        # If so, start working on it; other workers will keep using the old list
        our_update = cache.add(f"{key}.sentinel", True, timeout=60)
        if our_update:
            serials = get_serials()
            cache.set(key, serials, timeout=300)  # long expiration, overwritten 1/min
        else:
            serials = cache.get(key)
            if serials is None:
                return Response(
                    data={"detail": "Serial cache not ready"},
                    status=status.HTTP_409_CONFLICT,
                )
        return Response(serials)
