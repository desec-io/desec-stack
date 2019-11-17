import base64
import binascii

import django.core.exceptions
from django.conf import settings
from django.contrib.auth import user_logged_in
from django.core.mail import EmailMessage
from django.http import Http404
from django.template.loader import get_template
from rest_framework import generics
from rest_framework import mixins
from rest_framework import status
from rest_framework.authentication import get_authorization_header, BaseAuthentication
from rest_framework.exceptions import (NotFound, PermissionDenied, ValidationError)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

import desecapi.authentication as auth
from desecapi import serializers, models
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.permissions import IsOwner, IsDomainOwner, WithinDomainLimitOnPOST
from desecapi.renderers import PlainTextRenderer


class IdempotentDestroy:

    def destroy(self, request, *args, **kwargs):
        try:
            # noinspection PyUnresolvedReferences
            super().destroy(request, *args, **kwargs)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class DomainView:

    def initial(self, request, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        super().initial(request, *args, **kwargs)
        try:
            # noinspection PyAttributeOutsideInit, PyUnresolvedReferences
            self.domain = self.request.user.domains.get(name=self.kwargs['name'])
        except models.Domain.DoesNotExist:
            raise Http404


class TokenViewSet(IdempotentDestroy,
                   mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
    serializer_class = serializers.TokenSerializer
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        return self.request.user.auth_tokens.all()

    def get_serializer(self, *args, **kwargs):
        # When creating a new token, return the plaintext representation
        if self.request.method == 'POST':
            kwargs.setdefault('include_plain', True)
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DomainList(generics.ListCreateAPIView):
    serializer_class = serializers.DomainSerializer
    permission_classes = (IsAuthenticated, IsOwner, WithinDomainLimitOnPOST)

    def get_queryset(self):
        return models.Domain.objects.filter(owner=self.request.user.pk)

    def perform_create(self, serializer):
        with PDNSChangeTracker():
            domain = serializer.save(owner=self.request.user)

        # TODO this line raises if the local public suffix is not in our database!
        PDNSChangeTracker.track(lambda: self.auto_delegate(domain))

    @staticmethod
    def auto_delegate(domain: models.Domain):
        if domain.is_locally_registrable:
            parent_domain = models.Domain.objects.get(name=domain.parent_domain_name)
            parent_domain.update_delegation(domain)


class DomainDetail(IdempotentDestroy, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = serializers.DomainSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    lookup_field = 'name'

    def perform_destroy(self, instance: models.Domain):
        with PDNSChangeTracker():
            instance.delete()
        if instance.is_locally_registrable:
            parent_domain = models.Domain.objects.get(name=instance.parent_domain_name)
            with PDNSChangeTracker():
                parent_domain.update_delegation(instance)

    def get_queryset(self):
        return models.Domain.objects.filter(owner=self.request.user.pk)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except django.core.exceptions.ValidationError as e:
            raise ValidationError(detail={"detail": e.message})


class RRsetDetail(IdempotentDestroy, DomainView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = serializers.RRsetSerializer
    permission_classes = (IsAuthenticated, IsDomainOwner,)

    def get_queryset(self):
        return self.domain.rrset_set

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        filter_kwargs = {k: self.kwargs[k] for k in ['subname', 'type']}
        obj = generics.get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def get_serializer(self, *args, **kwargs):
        kwargs['domain'] = self.domain
        return super().get_serializer(*args, **kwargs)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)

        if response.data is None:
            response.status_code = 204
        return response

    def perform_update(self, serializer):
        with PDNSChangeTracker():
            super().perform_update(serializer)

    def perform_destroy(self, instance):
        with PDNSChangeTracker():
            super().perform_destroy(instance)


class RRsetList(DomainView, generics.ListCreateAPIView, generics.UpdateAPIView):
    serializer_class = serializers.RRsetSerializer
    permission_classes = (IsAuthenticated, IsDomainOwner,)

    def get_queryset(self):
        rrsets = models.RRset.objects.filter(domain=self.domain)

        for filter_field in ('subname', 'type'):
            value = self.request.query_params.get(filter_field)

            if value is not None:
                # TODO consider moving this
                if filter_field == 'type' and value in models.RRset.RESTRICTED_TYPES:
                    raise PermissionDenied("You cannot tinker with the %s RRset." % value)

                rrsets = rrsets.filter(**{'%s__exact' % filter_field: value})

        return rrsets

    def get_object(self):
        # For this view, the object we're operating on is the queryset that one can also GET. Serializing a queryset
        # is fine as per https://www.django-rest-framework.org/api-guide/serializers/#serializing-multiple-objects.
        # We skip checking object permissions here to avoid evaluating the queryset. The user can access all his RRsets
        # anyways.
        return self.filter_queryset(self.get_queryset())

    def get_serializer(self, *args, **kwargs):
        data = kwargs.get('data')
        if data and 'many' not in kwargs:
            if self.request.method == 'POST':
                kwargs['many'] = isinstance(data, list)
            elif self.request.method in ['PATCH', 'PUT']:
                kwargs['many'] = True
        return super().get_serializer(domain=self.domain, *args, **kwargs)

    def perform_create(self, serializer):
        with PDNSChangeTracker():
            serializer.save(domain=self.domain)

    def perform_update(self, serializer):
        with PDNSChangeTracker():
            serializer.save(domain=self.domain)


class Root(APIView):
    def get(self, request, *_):
        if self.request.user.is_authenticated:
            routes = {
                'account': {
                    'show': reverse('account', request=request),
                    'delete': reverse('account-delete', request=request),
                    'change-email': reverse('account-change-email', request=request),
                    'reset-password': reverse('account-reset-password', request=request),
                },
                'logout': reverse('logout', request=request),
                'tokens': reverse('token-list', request=request),
                'domains': reverse('domain-list', request=request),
            }
        else:
            routes = {
                'register': reverse('register', request=request),
                'login': reverse('login', request=request),
                'reset-password': reverse('account-reset-password', request=request),
            }
        return Response(routes)


class DynDNS12Update(APIView):
    authentication_classes = (auth.TokenAuthentication, auth.BasicTokenAuthentication, auth.URLParamAuthentication,)
    renderer_classes = [PlainTextRenderer]

    def _find_domain(self, request):
        def find_domain_name(r):
            # 1. hostname parameter
            if 'hostname' in r.query_params and r.query_params['hostname'] != 'YES':
                return r.query_params['hostname']

            # 2. host_id parameter
            if 'host_id' in r.query_params:
                return r.query_params['host_id']

            # 3. http basic auth username
            try:
                domain_name = base64.b64decode(
                    get_authorization_header(r).decode().split(' ')[1].encode()).decode().split(':')[0]
                if domain_name and '@' not in domain_name:
                    return domain_name
            except IndexError:
                pass
            except UnicodeDecodeError:
                pass
            except binascii.Error:
                pass

            # 4. username parameter
            if 'username' in r.query_params:
                return r.query_params['username']

            # 5. only domain associated with this user account
            if len(r.user.domains.all()) == 1:
                return r.user.domains.all()[0].name
            if len(r.user.domains.all()) > 1:
                ex = ValidationError(detail={
                    "detail": "Request does not specify domain unambiguously.",
                    "code": "domain-ambiguous"
                })
                ex.status_code = status.HTTP_409_CONFLICT
                raise ex

            return None

        name = find_domain_name(request).lower()

        try:
            return self.request.user.domains.get(name=name)
        except models.Domain.DoesNotExist:
            return None

    @staticmethod
    def find_ip(request, params, version=4):
        if version == 4:
            look_for = '.'
        elif version == 6:
            look_for = ':'
        else:
            raise Exception

        # Check URL parameters
        for p in params:
            if p in request.query_params:
                if not len(request.query_params[p]):
                    return None
                if look_for in request.query_params[p]:
                    return request.query_params[p]

        # Check remote IP address
        client_ip = request.META.get('REMOTE_ADDR')
        if look_for in client_ip:
            return client_ip

        # give up
        return None

    def _find_ip_v4(self, request):
        return self.find_ip(request, ['myip', 'myipv4', 'ip'])

    def _find_ip_v6(self, request):
        return self.find_ip(request, ['myipv6', 'ipv6', 'myip', 'ip'], version=6)

    def get(self, request, *_):
        domain = self._find_domain(request)

        if domain is None:
            raise NotFound('nohost')

        ipv4 = self._find_ip_v4(request)
        ipv6 = self._find_ip_v6(request)

        data = [
            {'type': 'A', 'subname': '', 'ttl': 60, 'records': [ipv4] if ipv4 else []},
            {'type': 'AAAA', 'subname': '', 'ttl': 60, 'records': [ipv6] if ipv6 else []},
        ]

        instances = domain.rrset_set.filter(subname='', type__in=['A', 'AAAA']).all()
        serializer = serializers.RRsetSerializer(instances, domain=domain, data=data, many=True, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            raise e

        with PDNSChangeTracker():
            serializer.save(domain=domain)

        return Response('good', content_type='text/plain')


class DonationList(generics.CreateAPIView):
    serializer_class = serializers.DonationSerializer

    def perform_create(self, serializer):
        iban = serializer.validated_data['iban']
        obj = serializer.save()

        def send_donation_emails(donation):
            context = {
                'donation': donation,
                'creditoridentifier': settings.SEPA['CREDITOR_ID'],
                'creditorname': settings.SEPA['CREDITOR_NAME'],
                'complete_iban': iban
            }

            # internal desec notification
            content_tmpl = get_template('emails/donation/desec-content.txt')
            subject_tmpl = get_template('emails/donation/desec-subject.txt')
            attachment_tmpl = get_template('emails/donation/desec-attachment-jameica.txt')
            from_tmpl = get_template('emails/from.txt')
            email = EmailMessage(subject_tmpl.render(context),
                                 content_tmpl.render(context),
                                 from_tmpl.render(context),
                                 ['donation@desec.io'],
                                 attachments=[
                                     ('jameica-directdebit.xml',
                                      attachment_tmpl.render(context),
                                      'text/xml')
                                 ])
            email.send()

            # donor notification
            if donation.email:
                content_tmpl = get_template('emails/donation/donor-content.txt')
                subject_tmpl = get_template('emails/donation/donor-subject.txt')
                email = EmailMessage(subject_tmpl.render(context),
                                     content_tmpl.render(context),
                                     from_tmpl.render(context),
                                     [donation.email])
                email.send()

        # send emails
        send_donation_emails(obj)


class AccountCreateView(generics.CreateAPIView):
    serializer_class = serializers.RegisterAccountSerializer

    def create(self, request, *args, **kwargs):
        # Create user and send trigger email verification.
        # Alternative would be to create user once email is verified, but this could be abused for bulk email.

        serializer = self.get_serializer(data=request.data)
        activation_required = settings.USER_ACTIVATION_REQUIRED
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            # Hide existing users
            email_detail = e.detail.pop('email', [])
            email_detail = [detail for detail in email_detail if detail.code != 'unique']
            if email_detail:
                e.detail['email'] = email_detail
            if e.detail:
                raise e
        else:
            # create user
            user = serializer.save(is_active=(not activation_required))

            # send email if needed
            domain = serializer.validated_data.get('domain')
            if domain or activation_required:
                action = models.AuthenticatedActivateUserAction(user=user, domain=domain)
                verification_code = serializers.AuthenticatedActivateUserActionSerializer(action).data['code']
                user.send_email('activate-with-domain' if domain else 'activate', context={
                    'confirmation_link': reverse('confirm-activate-account', request=request, args=[verification_code])
                })

        # This request is unauthenticated, so don't expose whether we did anything.
        message = 'Welcome! Please check your mailbox.' if activation_required else 'Welcome!'
        return Response(data={'detail': message}, status=status.HTTP_202_ACCEPTED)


class AccountView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.UserSerializer

    def get_object(self):
        return self.request.user


class AccountDeleteView(generics.GenericAPIView):
    authentication_classes = (auth.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)
    response_still_has_domains = Response(
        data={'detail': 'To delete your user account, first delete all of your domains.'},
        status=status.HTTP_409_CONFLICT,
    )

    def post(self, request, *args, **kwargs):
        if self.request.user.domains.exists():
            return self.response_still_has_domains
        action = models.AuthenticatedDeleteUserAction(user=self.request.user)
        verification_code = serializers.AuthenticatedDeleteUserActionSerializer(action).data['code']
        request.user.send_email('delete-user', context={
            'confirmation_link': reverse('confirm-delete-account', request=request, args=[verification_code])
        })

        return Response(data={'detail': 'Please check your mailbox for further account deletion instructions.'},
                        status=status.HTTP_202_ACCEPTED)


class AccountLoginView(generics.GenericAPIView):
    authentication_classes = (auth.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        user = self.request.user

        token = models.Token.objects.create(user=user, name="login")
        user_logged_in.send(sender=user.__class__, request=self.request, user=user)

        data = serializers.TokenSerializer(token, include_plain=True).data
        return Response(data)


class AccountLogoutView(generics.GenericAPIView, mixins.DestroyModelMixin):
    authentication_classes = (auth.TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        # self.request.auth contains the hashed key as it is stored in the database
        return models.Token.objects.get(key=self.request.auth)

    def post(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


class AccountChangeEmailView(generics.GenericAPIView):
    authentication_classes = (auth.EmailPasswordPayloadAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ChangeEmailSerializer

    def post(self, request, *args, **kwargs):
        # Check password and extract email
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_email = serializer.validated_data['new_email']

        action = models.AuthenticatedChangeEmailUserAction(user=request.user, new_email=new_email)
        verification_code = serializers.AuthenticatedChangeEmailUserActionSerializer(action).data['code']
        request.user.send_email('change-email', recipient=new_email, context={
            'confirmation_link': reverse('confirm-change-email', request=request, args=[verification_code]),
            'old_email': request.user.email,
            'new_email': new_email,
        })

        # At this point, we know that we are talking to the user, so we can tell that we sent an email.
        return Response(data={'detail': 'Please check your mailbox to confirm email address change.'},
                        status=status.HTTP_202_ACCEPTED)


class AccountResetPasswordView(generics.GenericAPIView):
    serializer_class = serializers.EmailSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            email = serializer.validated_data['email']
            user = models.User.objects.get(email=email, is_active=True)
        except models.User.DoesNotExist:
            pass
        else:
            action = models.AuthenticatedResetPasswordUserAction(user=user)
            verification_code = serializers.AuthenticatedResetPasswordUserActionSerializer(action).data['code']
            user.send_email('reset-password', context={
                'confirmation_link': reverse('confirm-reset-password', request=request, args=[verification_code])
            })

        # This request is unauthenticated, so don't expose whether we did anything.
        return Response(data={'detail': 'Please check your mailbox for further password reset instructions. '
                                        'If you did not receive an email, please contact support.'},
                        status=status.HTTP_202_ACCEPTED)


class AuthenticatedActionView(generics.GenericAPIView):
    """
    Abstract class. Deserializes the given payload according the serializers specified by the view extending
    this class. If the `serializer.is_valid`, `act` is called on the action object.
    """

    class AuthenticatedActionAuthenticator(BaseAuthentication):
        """
        Authenticates a request based on whether the serializer determines the validity of the given verification code
        and additional data (using `serializer.is_valid()`). The serializer's input data will be determined by (a) the
        view's 'code' kwarg and (b) the request payload for POST requests. Request methods other than GET and POST will
        fail authentication regardless of other conditions.

        If the request is valid, the AuthenticatedAction instance will be attached to the view as `authenticated_action`
        attribute.

        Note that this class will raise ValidationError instead of AuthenticationFailed, usually resulting in status
        400 instead of 403.
        """

        def __init__(self, view):
            super().__init__()
            self.view = view

        def authenticate(self, request):
            data = {**request.data, 'code': self.view.kwargs['code']}  # order crucial to avoid override from payload!
            serializer = self.view.serializer_class(data=data, context=self.view.get_serializer_context())
            serializer.is_valid(raise_exception=True)
            self.view.authenticated_action = serializer.instance

            return self.view.authenticated_action.user, None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.authenticated_action = None

    def get_authenticators(self):
        return [self.AuthenticatedActionAuthenticator(self)]

    def get(self, request, *args, **kwargs):
        return self.take_action()

    def post(self, request, *args, **kwargs):
        return self.take_action()

    def finalize(self):
        raise NotImplementedError

    def take_action(self):
        # execute the action
        self.authenticated_action.act()

        return self.finalize()


class AuthenticatedActivateUserActionView(AuthenticatedActionView):
    http_method_names = ['get']
    serializer_class = serializers.AuthenticatedActivateUserActionSerializer

    def finalize(self):
        action = self.authenticated_action

        if not action.domain:
            return Response({
                'detail': 'Success! Please log in at {}.'.format(self.request.build_absolute_uri(reverse('v1:login')))
            })

        serializer = serializers.DomainSerializer(
            data={'name': action.domain},
            context=self.get_serializer_context()
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:  # e.g. domain name unavailable
            action.user.delete()
            reasons = ', '.join([detail.code for detail in e.detail.get('name', [])])
            raise ValidationError(
                f'The requested domain {action.domain} could not be registered (reason: {reasons}). '
                f'Please start over and sign up again.'
            )
        domain = PDNSChangeTracker.track(lambda: serializer.save(owner=action.user))

        if domain.is_locally_registrable:
            # TODO the following line raises Domain.DoesNotExist under unknown conditions
            PDNSChangeTracker.track(lambda: DomainList.auto_delegate(domain))
            token = models.Token.objects.create(user=action.user, name='dyndns')
            return Response({
                'detail': "Success! Here is the secret token required for updating your domain's DNS information. When "
                          "configuring a router (or other DNS client), place it into the password field of the "
                          "configuration. Do not confuse the secret token with your account password! Your password is "
                          "not needed for DNS configuration, and you should not store it anywhere in plain text.",
                **serializers.TokenSerializer(token, include_plain=True).data,
            })
        else:
            return Response({
                'detail': 'Success! Please check the docs for the next steps, https://desec.readthedocs.io/.'
            })


class AuthenticatedChangeEmailUserActionView(AuthenticatedActionView):
    http_method_names = ['get']
    serializer_class = serializers.AuthenticatedChangeEmailUserActionSerializer

    def finalize(self):
        return Response({
            'detail': f'Success! Your email address has been changed to {self.authenticated_action.user.email}.'
        })


class AuthenticatedResetPasswordUserActionView(AuthenticatedActionView):
    http_method_names = ['post']
    serializer_class = serializers.AuthenticatedResetPasswordUserActionSerializer

    def finalize(self):
        return Response({'detail': 'Success! Your password has been changed.'})


class AuthenticatedDeleteUserActionView(AuthenticatedActionView):
    http_method_names = ['get']
    serializer_class = serializers.AuthenticatedDeleteUserActionSerializer

    def take_action(self):
        if self.request.user.domains.exists():
            return AccountDeleteView.response_still_has_domains
        return super().take_action()

    def finalize(self):
        return Response({'detail': 'All your data has been deleted. Bye bye, see you soon! <3'})


class CaptchaView(generics.CreateAPIView):
    serializer_class = serializers.CaptchaSerializer
