from django.http import Http404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS

from desecapi import models, permissions
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.serializers import RRsetSerializer

from .base import IdempotentDestroyMixin


class EmptyPayloadMixin:
    def initialize_request(self, request, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        request = super().initialize_request(request, *args, **kwargs)

        if request.stream is None:
            # In this case, data and files are both empty, so we can set request.data=None (instead of the default {}).
            # This allows distinguishing missing payload from empty dict payload.
            # See https://github.com/encode/django-rest-framework/pull/7195
            request._full_data = None

        return request


class DomainViewMixin:
    @property
    def domain(self):
        try:
            # noinspection PyUnresolvedReferences
            return self.request.user.domains.get(name=self.kwargs["name"])
        except models.Domain.DoesNotExist:
            raise Http404


class RRsetView(DomainViewMixin):
    serializer_class = RRsetSerializer
    permission_classes = (
        IsAuthenticated,
        permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
        permissions.IsDomainOwner,
    )

    @property
    def throttle_scope(self):
        # noinspection PyUnresolvedReferences
        return (
            "dns_api_cheap"
            if self.request.method in SAFE_METHODS
            else "dns_api_per_domain_expensive"
        )

    @property
    def throttle_scope_bucket(self):
        # Note: bucket should remain constant even when domain is recreated
        # noinspection PyUnresolvedReferences
        return None if self.request.method in SAFE_METHODS else self.kwargs["name"]

    def get_queryset(self):
        return self.domain.rrset_set

    def get_serializer_context(self):
        # noinspection PyUnresolvedReferences
        return {**super().get_serializer_context(), "domain": self.domain}

    def perform_update(self, serializer):
        with PDNSChangeTracker():
            # noinspection PyUnresolvedReferences
            super().perform_update(serializer)


class RRsetDetail(
    RRsetView, IdempotentDestroyMixin, generics.RetrieveUpdateDestroyAPIView
):
    @property
    def permission_classes(self):
        ret = list(super().permission_classes)
        if self.request.method not in SAFE_METHODS:
            ret.append(permissions.TokenHasRRsetPermission)
        return ret

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        filter_kwargs = {k: self.kwargs[k] for k in ["subname", "type"]}
        obj = generics.get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        if response.data is None:
            response.status_code = 204
        return response

    def perform_destroy(self, instance):
        # Disallow modification of apex NS RRset for locally registrable domains
        if instance.type == "NS" and self.domain.is_locally_registrable:
            if instance.subname == "":
                raise ValidationError("Cannot modify NS records for this domain.")
        with PDNSChangeTracker():
            super().perform_destroy(instance)


class RRsetList(
    RRsetView, EmptyPayloadMixin, generics.ListCreateAPIView, generics.UpdateAPIView
):
    def get_queryset(self):
        rrsets = super().get_queryset()

        for filter_field in ("subname", "type"):
            value = self.request.query_params.get(filter_field)

            if value is not None:
                # TODO consider moving this
                if (
                    filter_field == "type"
                    and value in models.records.RR_SET_TYPES_AUTOMATIC
                ):
                    raise PermissionDenied(
                        "You cannot tinker with the %s RRset." % value
                    )

                rrsets = rrsets.filter(**{filter_field: value})

        # Without .all(), cache is sometimes inconsistent with actual state in bulk tests. (Why?)
        return rrsets.all()

    def get_object(self):
        # For this view, the object we're operating on is the queryset that one can also GET. Serializing a queryset
        # is fine as per https://www.django-rest-framework.org/api-guide/serializers/#serializing-multiple-objects.
        # To avoid evaluating the queryset, object permissions are checked in the serializer for write operations only.
        # The user can read all their RRsets anyway.
        return self.filter_queryset(self.get_queryset())

    def get_serializer(self, *args, **kwargs):
        kwargs = kwargs.copy()

        if "many" not in kwargs:
            if self.request.method in ["POST"]:
                kwargs["many"] = isinstance(kwargs.get("data"), list)
            elif self.request.method in ["PATCH", "PUT"]:
                kwargs["many"] = True

        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        with PDNSChangeTracker():
            super().perform_create(serializer)
