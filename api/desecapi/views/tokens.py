import django.core.exceptions
from django.http import Http404
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse

from desecapi import permissions
from desecapi.models import Token
from desecapi.serializers import TokenDomainPolicySerializer, TokenSerializer

from .base import IdempotentDestroyMixin


class TokenViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    serializer_class = TokenSerializer
    permission_classes = (
        IsAuthenticated,
        permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
        permissions.HasManageTokensPermission,
    )
    throttle_scope = "account_management_passive"

    def get_queryset(self):
        return self.request.user.token_set.all()

    def get_serializer(self, *args, **kwargs):
        # When creating a new token, return the plaintext representation
        if self.action == "create":
            kwargs.setdefault("include_plain", True)
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TokenPoliciesRoot(RetrieveAPIView):
    serializer_class = TokenSerializer
    lookup_url_kwarg = "token_id"
    throttle_scope = "account_management_passive"
    permission_classes = [
        IsAuthenticated,
        permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
        permissions.HasManageTokensPermission
        | permissions.AuthTokenCorrespondsToViewToken,
    ]

    def get_queryset(self):
        return self.request.user.token_set.all()

    def get(self, request, *args, **kwargs):
        self.get_object()  # raises if token does not exist
        return Response(
            {
                "rrsets": reverse(
                    "token_domain_policies-list", request=request, kwargs=kwargs
                )
            }
        )


class TokenDomainPolicyViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = TokenDomainPolicySerializer
    throttle_scope = "account_management_passive"

    @property
    def permission_classes(self):
        ret = [
            IsAuthenticated,
            permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
        ]
        if self.request.method in SAFE_METHODS:
            ret.append(
                permissions.HasManageTokensPermission
                | permissions.AuthTokenCorrespondsToViewToken
            )
        else:
            ret.append(permissions.HasManageTokensPermission)
        return ret

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Token.DoesNotExist:
            raise Http404

    def get_queryset(self):
        qs = Token.objects.filter(user=self.request.user)
        return get_object_or_404(qs, pk=self.kwargs["token_id"]).tokendomainpolicy_set

    def perform_destroy(self, instance):
        try:
            super().perform_destroy(instance)
        except django.core.exceptions.ValidationError as exc:
            raise ValidationError(exc.message_dict, code="precedence")
