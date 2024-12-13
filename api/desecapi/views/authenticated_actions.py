from django.contrib.auth.hashers import is_password_usable
from django.shortcuts import redirect
from rest_framework import generics, status
from rest_framework.exceptions import NotAcceptable, ValidationError
from rest_framework.permissions import SAFE_METHODS
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer
from rest_framework.response import Response

from desecapi import permissions, serializers
from desecapi.authentication import AuthenticatedBasicUserActionAuthentication
from desecapi.models import Token
from desecapi.pdns_change_tracker import PDNSChangeTracker

from .domains import DomainViewSet
from .users import AccountDeleteView


class AuthenticatedActionView(generics.GenericAPIView):
    """
    Abstract class. Deserializes the given payload according the serializers specified by the view extending
    this class. If the `serializer.is_valid`, `act` is called on the action object.

    Summary of the behavior depending on HTTP method and Accept: header:

                        GET	                                POST                other method
    Accept: text/html	forward to `self.html_url` if any   perform action      405 Method Not Allowed
    else                HTTP 406 Not Acceptable             perform action      405 Method Not Allowed
    """

    html_url = None  # Redirect GET requests to this webapp GUI URL
    http_method_names = ["get", "post"]  # GET is for redirect only
    renderer_classes = [JSONRenderer, StaticHTMLRenderer]
    _authenticated_action = None

    @property
    def authenticated_action(self):
        if self._authenticated_action is None:
            serializer = self.get_serializer(data=self.request.data)
            serializer.is_valid(raise_exception=True)
            try:
                self._authenticated_action = serializer.Meta.model(
                    **serializer.validated_data
                )
            except ValueError:  # this happens when state cannot be verified
                ex = ValidationError(
                    "This action cannot be carried out because another operation has been performed, "
                    "invalidating this one. (Are you trying to perform this action twice?)"
                )
                ex.status_code = status.HTTP_409_CONFLICT
                raise ex
        return self._authenticated_action

    @property
    def authentication_classes(self):
        # This prevents both auth action code evaluation and user-specific throttling when we only want a redirect
        return (
            ()
            if self.request.method in SAFE_METHODS
            else (AuthenticatedBasicUserActionAuthentication,)
        )

    @property
    def permission_classes(self):
        return (
            () if self.request.method in SAFE_METHODS else (permissions.IsActiveUser,)
        )

    @property
    def throttle_scope(self):
        return (
            "account_management_passive"
            if self.request.method in SAFE_METHODS
            else "account_management_active"
        )

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "code": self.kwargs["code"],
            "validity_period": self.get_serializer_class().validity_period,
        }

    def get(self, request, *args, **kwargs):
        # Redirect browsers to frontend if available
        is_redirect = (
            request.accepted_renderer.format == "html"
        ) and self.html_url is not None
        if is_redirect:
            # Careful: This can generally lead to an open redirect if values contain slashes!
            # However, it cannot happen for Django view kwargs.
            return redirect(self.html_url.format(**kwargs))
        else:
            raise NotAcceptable

    def post(self, request, *args, **kwargs):
        self.authenticated_action.act()
        return Response(status=status.HTTP_202_ACCEPTED)


class AuthenticatedChangeOutreachPreferenceUserActionView(AuthenticatedActionView):
    html_url = "/confirm/change-outreach-preference/{code}/"
    serializer_class = (
        serializers.AuthenticatedChangeOutreachPreferenceUserActionSerializer
    )

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response(
            {
                "detail": "Thank you! We have recorded that you would not like to receive outreach messages."
            }
        )


class AuthenticatedActivateUserActionView(AuthenticatedActionView):
    html_url = "/confirm/activate-account/{code}/"
    permission_classes = ()  # don't require that user is activated already
    serializer_class = serializers.AuthenticatedActivateUserActionSerializer

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        self.request.user.refresh_from_db()  # subsequent action link generation needs current state
        if not self.authenticated_action.domain:
            return self._finalize_without_domain()
        else:
            domain = self._create_domain()
            return self._finalize_with_domain(domain)

    def _create_domain(self):
        serializer = serializers.DomainSerializer(
            data={"name": self.authenticated_action.domain},
            context=self.get_serializer_context(),
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:  # e.g. domain name unavailable
            self.request.user.delete()
            reasons = ", ".join([detail.code for detail in e.detail.get("name", [])])
            raise ValidationError(
                f"The requested domain {self.authenticated_action.domain} could not be registered (reason: {reasons}). "
                f"Please start over and sign up again."
            )
        # TODO the following line is subject to race condition and can fail, as for the domain name, we have that
        #  time-of-check != time-of-action
        return PDNSChangeTracker.track(lambda: serializer.save(owner=self.request.user))

    def _finalize_without_domain(self):
        if not is_password_usable(self.request.user.password):
            serializers.AuthenticatedResetPasswordUserActionSerializer.build_and_save(
                user=self.request.user
            )
            return Response(
                {
                    "detail": "Success! We sent you instructions on how to set your password."
                }
            )
        return Response(
            {
                "detail": "Success! Your account has been activated, and you can now log in."
            }
        )

    def _finalize_with_domain(self, domain):
        if domain.is_locally_registrable:
            # TODO the following line raises Domain.DoesNotExist under unknown conditions
            PDNSChangeTracker.track(lambda: DomainViewSet.auto_delegate(domain))
            token = Token.objects.create(owner=domain.owner, name="dyndns")
            return Response(
                {
                    "detail": 'Success! Here is the password ("token") to configure your router (or any other dynDNS '
                    "client). This password is different from your account password for security reasons.",
                    "domain": serializers.DomainSerializer(domain).data,
                    **serializers.TokenSerializer(token, include_plain=True).data,
                }
            )
        else:
            return Response(
                {
                    "detail": "Success! Please check the docs for the next steps, https://desec.readthedocs.io/.",
                    "domain": serializers.DomainSerializer(
                        domain, include_keys=True
                    ).data,
                }
            )


class AuthenticatedActivateUserWithOverrideTokenActionView(AuthenticatedActionView):
    html_url = "/confirm/activate-account-with-override-token/{code}/"
    permission_classes = ()  # don't require that user is activated already
    serializer_class = (
        serializers.AuthenticatedActivateUserWithOverrideTokenActionSerializer
    )

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response(
            {
                "detail": f"Success! Welcome to deSEC. {self.authenticated_action.token.owner.email} will "
                "manage your domains for you. You can reset the password to your account at any time to "
                "access your account directly."
            }
        )


class AuthenticatedChangeEmailUserActionView(AuthenticatedActionView):
    html_url = "/confirm/change-email/{code}/"
    serializer_class = serializers.AuthenticatedChangeEmailUserActionSerializer

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response(
            {
                "detail": f"Success! Your email address has been changed to {self.authenticated_action.user.email}."
            }
        )


class AuthenticatedConfirmAccountUserActionView(AuthenticatedActionView):
    html_url = "/confirm/confirm-account/{code}"
    serializer_class = serializers.AuthenticatedConfirmAccountUserActionSerializer

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response({"detail": "Success! Your account status has been confirmed."})


class AuthenticatedCreateTOTPFactorUserActionView(AuthenticatedActionView):
    html_url = "/confirm/create-totp/{code}/"
    serializer_class = serializers.AuthenticatedCreateTOTPFactorUserActionSerializer

    def post(self, request, *args, **kwargs):
        factor = self.authenticated_action.act()
        serializer = serializers.TOTPFactorSerializer(factor, include_secret=True)
        return Response(serializer.data)


class AuthenticatedResetPasswordUserActionView(AuthenticatedActionView):
    html_url = "/confirm/reset-password/{code}/"
    serializer_class = serializers.AuthenticatedResetPasswordUserActionSerializer

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response({"detail": "Success! Your password has been changed."})


class AuthenticatedDeleteUserActionView(AuthenticatedActionView):
    html_url = "/confirm/delete-account/{code}/"
    serializer_class = serializers.AuthenticatedDeleteUserActionSerializer

    def post(self, request, *args, **kwargs):
        if self.request.user.domains.exists():
            return AccountDeleteView.response_still_has_domains
        super().post(request, *args, **kwargs)
        return Response(
            {"detail": "All your data has been deleted. Bye bye, see you soon! <3"}
        )


class AuthenticatedRenewDomainBasicUserActionView(AuthenticatedActionView):
    html_url = "/confirm/renew-domain/{code}/"
    serializer_class = serializers.AuthenticatedRenewDomainBasicUserActionSerializer

    def post(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)
        return Response(
            {
                "detail": f"We recorded that your domain {self.authenticated_action.domain} is still in use."
            }
        )
