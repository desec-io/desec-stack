from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from desecapi import permissions
from desecapi.serializers import (
    AuthenticatedCreateTOTPFactorUserActionSerializer,
    TOTPCodeSerializer,
    TOTPFactorSerializer,
)

from .base import IdempotentDestroyMixin


class TOTPViewSet(IdempotentDestroyMixin, viewsets.ModelViewSet):
    permission_classes = (
        IsAuthenticated,
        permissions.HasManageTokensPermission,
    )
    serializer_class = TOTPFactorSerializer
    throttle_scope = "account_management_passive"

    def get_queryset(self):
        return self.serializer_class.Meta.model.objects.filter(user=self.request.user)

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
        serializer = TOTPCodeSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        return Response({"detail": "The code was correct."})
