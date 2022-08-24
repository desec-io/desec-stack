from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response

from desecapi import permissions
from desecapi.serializers import (
    AuthenticatedCreateTOTPFactorUserActionSerializer,
    TOTPCodeSerializer,
    TOTPFactorSerializer,
)

from .base import IdempotentDestroyMixin


class TOTPViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    serializer_class = TOTPFactorSerializer
    throttle_scope = "account_management_passive"

    @property
    def permission_classes(self):
        if self.action == "verify":
            return [AllowAny]  # temporary for anonymous activation
        ret = [IsAuthenticated, permissions.HasManageTokensPermission]
        if self.request.method not in SAFE_METHODS and self.action != "verify":
            ret.append(permissions.MFARequiredIfEnabled)
        else:
            ret.append(permissions.IsLoginToken)
        return ret

    def get_queryset(self):
        qs = self.serializer_class.Meta.model.objects
        if self.action == "verify" and self.request.method == "POST":
            return qs
        else:
            return qs.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, include_secret=True)
        serializer.is_valid(raise_exception=True)
        if request.user.mfa_enabled:
            serializer.save(user=request.user)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        else:
            AuthenticatedCreateTOTPFactorUserActionSerializer.build_and_save(
                user=request.user, name=serializer.validated_data.get("name", "")
            )
            message = "This operation requires confirmation. Please check your mailbox for instructions!"
            return Response(data={"detail": message}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        new = self.get_object().last_used is None
        authenticated = bool(request.user and request.user.is_authenticated)
        if not new and not authenticated:
            raise NotAuthenticated

        serializer = TOTPCodeSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        if authenticated and not new:  # don't step up during activation
            request.auth.mfa = True  # Step-up token
            request.auth.save()

        message = (
            "Your TOTP token has been activated!" if new else "The code was correct."
        )
        return Response({"detail": message})
