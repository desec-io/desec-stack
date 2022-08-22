import django.core.exceptions
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from desecapi import permissions
from desecapi.models import TokenDomainPolicy
from desecapi.serializers import TokenDomainPolicySerializer, TokenSerializer

from .base import IdempotentDestroyMixin
from .domains import DomainViewSet


class TokenViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    serializer_class = TokenSerializer
    permission_classes = (IsAuthenticated, permissions.HasManageTokensPermission,)
    throttle_scope = 'account_management_passive'

    def get_queryset(self):
        return self.request.user.token_set.all()

    def get_serializer(self, *args, **kwargs):
        # When creating a new token, return the plaintext representation
        if self.action == 'create':
            kwargs.setdefault('include_plain', True)
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TokenPoliciesRoot(APIView):
    permission_classes = [
        IsAuthenticated,
        permissions.HasManageTokensPermission | permissions.AuthTokenCorrespondsToViewToken,
    ]

    def get(self, request, *args, **kwargs):
        return Response({'domain': reverse('token_domain_policies-list', request=request, kwargs=kwargs)})


class TokenDomainPolicyViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    lookup_field = 'domain__name'
    lookup_value_regex = DomainViewSet.lookup_value_regex
    pagination_class = None
    serializer_class = TokenDomainPolicySerializer
    throttle_scope = 'account_management_passive'

    @property
    def permission_classes(self):
        ret = [IsAuthenticated]
        if self.request.method in SAFE_METHODS:
            ret.append(permissions.HasManageTokensPermission | permissions.AuthTokenCorrespondsToViewToken)
        else:
            ret.append(permissions.HasManageTokensPermission)
        return ret

    def dispatch(self, request, *args, **kwargs):
        # map default policy onto domain_id IS NULL
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        try:
            if kwargs[lookup_url_kwarg] == 'default':
                kwargs[lookup_url_kwarg] = None
        except KeyError:
            pass
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return TokenDomainPolicy.objects.filter(token_id=self.kwargs['token_id'], token__user=self.request.user)

    def perform_destroy(self, instance):
        try:
            super().perform_destroy(instance)
        except django.core.exceptions.ValidationError as exc:
            raise ValidationError(exc.message_dict, code='precedence')
