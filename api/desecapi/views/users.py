from datetime import timedelta

from django.conf import settings
from django.contrib.auth import user_logged_in
from rest_framework import generics, mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from desecapi import authentication, permissions, serializers
from desecapi.models import Token, User


class AccountCreateView(generics.CreateAPIView):
    serializer_class = serializers.RegisterAccountSerializer
    throttle_scope = "account_management_active"

    def create(self, request, *args, **kwargs):
        # Create user and send trigger email verification.
        # Alternative would be to create user once email is verified, but this could be abused for bulk email.

        serializer = self.get_serializer(data=request.data)
        activation_required = settings.USER_ACTIVATION_REQUIRED
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            # Hide existing users
            email_detail = e.detail.pop("email", [])
            email_detail = [
                detail for detail in email_detail if detail.code != "unique"
            ]
            if email_detail:
                e.detail["email"] = email_detail
            if e.detail:
                raise e
        else:
            # create user
            user = serializer.save(is_active=None if activation_required else True)

            # send email if needed
            domain = serializer.validated_data.get("domain")
            if domain or activation_required:
                serializers.AuthenticatedActivateUserActionSerializer.build_and_save(
                    user=user, domain=domain
                )

        # This request is unauthenticated, so don't expose whether we did anything.
        message = (
            "Welcome! Please check your mailbox." if activation_required else "Welcome!"
        )
        return Response(data={"detail": message}, status=status.HTTP_202_ACCEPTED)


class AccountView(generics.RetrieveUpdateAPIView):
    permission_classes = (
        IsAuthenticated,
        permissions.IsAPIToken | permissions.MFARequiredIfEnabled,
        permissions.HasManageTokensPermission,
    )
    serializer_class = serializers.UserSerializer
    throttle_scope = "account_management_passive"

    def get_object(self):
        return self.request.user


class AccountDeleteView(APIView):
    authentication_classes = (authentication.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)
    response_still_has_domains = Response(
        data={
            "detail": "To delete your user account, first delete all of your domains."
        },
        status=status.HTTP_409_CONFLICT,
    )
    throttle_scope = "account_management_active"

    def post(self, request, *args, **kwargs):
        if request.user.domains.exists():
            return self.response_still_has_domains
        serializers.AuthenticatedDeleteUserActionSerializer.build_and_save(
            user=request.user
        )

        return Response(
            data={
                "detail": "Please check your mailbox for further account deletion instructions."
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AccountLoginView(generics.GenericAPIView):
    authentication_classes = (authentication.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.TokenSerializer
    throttle_scope = "account_management_passive"

    def post(self, request, *args, **kwargs):
        user = self.request.user

        # Clean up expired login tokens
        for token in (
            Token.objects.filter(owner=self.request.user, user_override=None)
            .exclude(mfa=None)  # exclude API tokens
            .all()
        ):
            if not token.is_valid:
                token.delete()

        # Create new login token
        token = Token.objects.create(
            owner=user,
            perm_create_domain=True,
            perm_delete_domain=True,
            perm_manage_tokens=True,
            max_age=timedelta(days=7),
            max_unused_period=timedelta(hours=1),
            mfa=False,
        )
        user_logged_in.send(sender=user.__class__, request=self.request, user=user)

        data = self.get_serializer(token, include_plain=True).data
        return Response(data)


class AccountLogoutView(APIView, mixins.DestroyModelMixin):
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    throttle_classes = []  # always allow people to log out

    def get_object(self):
        # self.request.auth contains the hashed key as it is stored in the database
        return Token.objects.get(key=self.request.auth)

    def post(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class AccountChangeEmailView(generics.GenericAPIView):
    authentication_classes = (authentication.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ChangeEmailSerializer
    throttle_scope = "account_management_active"

    def post(self, request, *args, **kwargs):
        # Check password and extract `new_email` field
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_email = serializer.validated_data["new_email"]
        serializers.AuthenticatedChangeEmailUserActionSerializer.build_and_save(
            user=request.user, new_email=new_email
        )

        # At this point, we know that we are talking to the user, so we can tell that we sent an email.
        return Response(
            data={
                "detail": "Please check your mailbox to confirm email address change."
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AccountResetPasswordView(generics.GenericAPIView):
    serializer_class = serializers.ResetPasswordSerializer
    throttle_scope = "account_management_active"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            email = serializer.validated_data["email"]
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            pass
        else:
            serializers.AuthenticatedResetPasswordUserActionSerializer.build_and_save(
                user=user
            )

        # This request is unauthenticated, so don't expose whether we did anything.
        return Response(
            data={
                "detail": "Please check your mailbox for further password reset instructions. "
                "If you did not receive an email, please contact support."
            },
            status=status.HTTP_202_ACCEPTED,
        )
