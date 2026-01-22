import django.core.exceptions
from django.conf import settings
from django.db.models import Q
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse

from desecapi import permissions, serializers
from desecapi.models import Token, User
from desecapi.serializers import TokenDomainPolicySerializer, TokenSerializer

from .base import IdempotentDestroyMixin


class TokenViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    serializer_class = TokenSerializer
    throttle_scope = "account_management_passive"

    @property
    def permission_classes(self):
        ret = [
            IsAuthenticated,
            permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
            permissions.HasManageTokensPermission,
        ]
        # The effective user may manage the token; its owner can only delete it
        if self.request.method not in SAFE_METHODS and self.action != "destroy":
            ret.append(permissions.IsUser)
        return ret

    def get_queryset(self):
        return Token.objects.filter(
            Q(owner=self.request.user) | Q(user_override=self.request.user)
        ).all()

    def get_serializer(self, *args, **kwargs):
        # When creating a new token, return the plaintext representation
        if self.action == "create":
            kwargs.setdefault("include_plain", True)
        return super().get_serializer(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Remove user_override field to prevent it from being written to the database,
        # and instead perform special treatment.
        # Do not re-add for rendering the response, as existing accounts would have their
        # email address rewritten to uppercase/lowercase as in the database, which would
        # expose their existence.
        user_override = serializer.validated_data.pop("user_override")
        self.perform_create(serializer)
        if user_override:
            http_status = status.HTTP_202_ACCEPTED
            if user_override._state.adding:  # user does not exist
                account_serializer = serializers.RegisterAccountSerializer(
                    data={"email": user_override.email, "password": None}
                )
                account_serializer.is_valid(raise_exception=True)
                user_override = account_serializer.save(
                    is_active=None if settings.USER_ACTIVATION_REQUIRED else True,
                    limit_domains=15,
                    limit_insecure_domains=settings.LIMIT_USER_INSECURE_DOMAIN_COUNT_DEFAULT,
                    outreach_preference=False,
                )
                serializers.AuthenticatedActivateUserWithOverrideTokenActionSerializer.build_and_save(
                    user=user_override,
                    token=self.get_queryset().get(pk=serializer.data["id"]),
                )
            else:  # user exists
                pass  # for now, not supported
        else:
            http_status = status.HTTP_201_CREATED

        return Response(serializer.data, status=http_status)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


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

    get_queryset = TokenViewSet.get_queryset

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
            ret.append(permissions.IsTokenUser)
        return ret

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Token.DoesNotExist:
            raise Http404

    def get_queryset(self):
        qs = TokenViewSet.get_queryset(self)
        return get_object_or_404(qs, pk=self.kwargs["token_id"]).tokendomainpolicy_set

    def perform_destroy(self, instance):
        try:
            super().perform_destroy(instance)
        except django.core.exceptions.ValidationError as exc:
            raise ValidationError(exc.message_dict, code="precedence")
