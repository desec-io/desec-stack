from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
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
        return [IsAuthenticated, permissions.HasManageTokensPermission]

    def get_queryset(self):
        qs = self.serializer_class.Meta.model.objects
        if self.action == "verify" and self.request.method == "POST":
            return qs
        else:
            return qs.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        message = "This operation requires manual confirmation. Please check your mailbox for instructions!"
        return Response(data={"detail": message}, status=status.HTTP_202_ACCEPTED)

    def perform_create(self, serializer):
        AuthenticatedCreateTOTPFactorUserActionSerializer.build_and_save(
            user=self.request.user, name=serializer.validated_data.get("name", "")
        )

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

        message = (
            "Your TOTP token has been activated!" if new else "The code was correct."
        )
        return Response({"detail": message})
