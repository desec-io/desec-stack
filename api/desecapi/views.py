import base64
import binascii
import ipaddress
import os
import re
from datetime import timedelta

import django.core.exceptions
import djoser.views
import psl_dns
from django.contrib.auth import user_logged_in, user_logged_out
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import get_template
from django.utils import timezone
from djoser import views, signals
from djoser.serializers import TokenSerializer as DjoserTokenSerializer
from dns import resolver
from rest_framework import generics
from rest_framework import mixins
from rest_framework import status
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import (NotFound, PermissionDenied, ValidationError)
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, UpdateAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

import desecapi.authentication as auth
from api import settings
from desecapi.emails import send_account_lock_email, send_token_email
from desecapi.forms import UnlockForm
from desecapi.models import Domain, User, RRset, Token
from desecapi.pdns import PDNSException
from desecapi.pdns_change_tracker import PDNSChangeTracker
from desecapi.permissions import IsOwner, IsUnlocked, IsDomainOwner
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import DomainSerializer, RRsetSerializer, DonationSerializer, TokenSerializer

patternDyn = re.compile(r'^[A-Za-z-][A-Za-z0-9_-]*\.dedyn\.io$')
patternNonDyn = re.compile(r'^([A-Za-z0-9-][A-Za-z0-9_-]*\.)*[A-Za-z]+$')


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
        except Domain.DoesNotExist:
            raise Http404


class TokenCreateView(djoser.views.TokenCreateView):

    def _action(self, serializer):
        user = serializer.user
        token = Token(user=user, name="login")
        token.save()
        user_logged_in.send(sender=user.__class__, request=self.request, user=user)
        token_serializer_class = DjoserTokenSerializer
        return Response(
            data=token_serializer_class(token).data,
            status=status.HTTP_201_CREATED,
        )


class TokenDestroyView(djoser.views.TokenDestroyView):

    def post(self, request):
        _, token = auth.TokenAuthentication().authenticate(request)
        token.delete()
        user_logged_out.send(
            sender=request.user.__class__, request=request, user=request.user
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TokenViewSet(IdempotentDestroy,
                   mixins.CreateModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
    serializer_class = TokenSerializer
    permission_classes = (IsAuthenticated, )
    lookup_field = 'user_specific_id'

    def get_queryset(self):
        return self.request.user.auth_tokens.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DomainList(ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    psl = psl_dns.PSL(resolver=settings.PSL_RESOLVER)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def perform_create(self, serializer):
        domain_name = serializer.validated_data['name']

        pattern = patternDyn if self.request.user.dyn else patternNonDyn
        if pattern.match(domain_name) is None:
            ex = ValidationError(detail={
                "detail": "This domain name is not well-formed, by policy.",
                "code": "domain-illformed"}
            )
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex

        # Check if domain is a public suffix
        try:
            public_suffix = self.psl.get_public_suffix(domain_name)
            is_public_suffix = self.psl.is_public_suffix(domain_name)
        except psl_dns.exceptions.UnsupportedRule as e:
            # It would probably be fine to just create the domain (with the TLD acting as the
            # public suffix and setting both public_suffix and is_public_suffix accordingly).
            # However, in order to allow to investigate the situation, it's better not catch
            # this exception. Our error handler turns it into a 503 error and makes sure
            # admins are notified.
            raise e

        is_restricted_suffix = is_public_suffix and domain_name not in settings.LOCAL_PUBLIC_SUFFIXES

        # Generate a list of all domains connecting this one and its public suffix.
        # If another user owns a zone with one of these names, then the requested
        # domain is unavailable because it is part of the other user's zone.
        private_components = domain_name.rsplit(public_suffix, 1)[0].rstrip('.')
        private_components = private_components.split('.') if private_components else []
        private_components += [public_suffix]
        private_domains = ['.'.join(private_components[i:]) for i in range(0, len(private_components) - 1)]
        assert is_public_suffix or domain_name == private_domains[0]

        # Deny registration for non-local public suffixes and for domains covered by other users' zones
        queryset = Domain.objects.filter(Q(name__in=private_domains) & ~Q(owner=self.request.user))
        if is_restricted_suffix or queryset.exists():
            ex = ValidationError(detail={"detail": "This domain name is unavailable.", "code": "domain-unavailable"})
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex

        if (self.request.user.limit_domains is not None and
                self.request.user.domains.count() >= self.request.user.limit_domains):
            ex = ValidationError(detail={
                "detail": "You reached the maximum number of domains allowed for your account.",
                "code": "domain-limit"
            })
            ex.status_code = status.HTTP_403_FORBIDDEN
            raise ex

        parent_domain_name = Domain.partition_name(domain_name)[1]
        domain_is_local = parent_domain_name in settings.LOCAL_PUBLIC_SUFFIXES
        try:
            with PDNSChangeTracker():
                domain_kwargs = {'owner': self.request.user}
                if domain_is_local:
                    domain_kwargs['minimum_ttl'] = 60
                domain = serializer.save(**domain_kwargs)
            if domain_is_local:
                parent_domain = Domain.objects.get(name=parent_domain_name)
                # NOTE we need two change trackers here, as the first transaction must be committed to
                # pdns in order to have keys available for the delegation
                with PDNSChangeTracker():
                    parent_domain.update_delegation(domain)
        except PDNSException as e:
            if not str(e).endswith(' already exists'):
                raise e
            ex = ValidationError(detail={
                "detail": "This domain name is unavailable.",
                "code": "domain-unavailable"}
            )
            ex.status_code = status.HTTP_400_BAD_REQUEST
            raise ex

        def send_dyn_dns_email():
            content_tmpl = get_template('emails/domain-dyndns/content.txt')
            subject_tmpl = get_template('emails/domain-dyndns/subject.txt')
            from_tmpl = get_template('emails/from.txt')
            context = {
                'domain': domain_name,
                'url': 'https://update.dedyn.io/',
                'username': domain_name,
                'password': self.request.auth.key
            }
            email = EmailMessage(subject_tmpl.render(context),
                                 content_tmpl.render(context),
                                 from_tmpl.render(context),
                                 [self.request.user.email])
            email.send()

        if domain.name.endswith('.dedyn.io'):
            send_dyn_dns_email()


class DomainDetail(IdempotentDestroy, RetrieveUpdateDestroyAPIView):
    serializer_class = DomainSerializer
    permission_classes = (IsAuthenticated, IsOwner,)
    lookup_field = 'name'

    def perform_destroy(self, instance: Domain):
        with PDNSChangeTracker():
            instance.delete()
        parent_domain_name = instance.partition_name()[1]
        if parent_domain_name in settings.LOCAL_PUBLIC_SUFFIXES:
            parent_domain = Domain.objects.get(name=parent_domain_name)
            with PDNSChangeTracker():
                parent_domain.update_delegation(instance)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except django.core.exceptions.ValidationError as e:
            raise ValidationError(detail={"detail": e.message})


class RRsetDetail(IdempotentDestroy, DomainView, RetrieveUpdateDestroyAPIView):
    serializer_class = RRsetSerializer
    permission_classes = (IsAuthenticated, IsDomainOwner, IsUnlocked,)

    def get_queryset(self):
        return self.domain.rrset_set

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        filter_kwargs = {k: self.kwargs[k] for k in ['subname', 'type']}
        obj = get_object_or_404(queryset, **filter_kwargs)

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


class RRsetList(DomainView, ListCreateAPIView, UpdateAPIView):
    serializer_class = RRsetSerializer
    permission_classes = (IsAuthenticated, IsDomainOwner, IsUnlocked,)

    def get_queryset(self):
        rrsets = RRset.objects.filter(domain=self.domain)

        for filter_field in ('subname', 'type'):
            value = self.request.query_params.get(filter_field)

            if value is not None:
                # TODO consider moving this
                if filter_field == 'type' and value in RRset.RESTRICTED_TYPES:
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

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if not response.data:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return response

    def perform_create(self, serializer):
        with PDNSChangeTracker():
            serializer.save(domain=self.domain)

    def perform_update(self, serializer):
        with PDNSChangeTracker():
            serializer.save(domain=self.domain)


class Root(APIView):
    def get(self, request, *_):
        if self.request.user and self.request.user.is_authenticated:
            return Response({
                'domains': reverse('domain-list', request=request),
                'user': reverse('user', request=request),
                'logout': reverse('token-destroy', request=request),  # TODO change interface to token-destroy, too?
            })
        else:
            return Response({
                'login': reverse('token-create', request=request),
                'register': reverse('register', request=request),
            })


class DnsQuery(APIView):

    @staticmethod
    def get(request, *_):
        dns_resolver = resolver.Resolver()

        if 'domain' not in request.GET:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        domain = str(request.GET['domain'])

        def get_records(domain_name, type_):
            records = []
            try:
                for address in dns_resolver.query(domain_name, type_):
                    records.append(str(address))
            except resolver.NoAnswer:
                return []
            except resolver.NoNameservers:
                return []
            except resolver.NXDOMAIN:
                return []
            return records

        # find currently active NS records
        ns_records = get_records(domain, 'NS')

        # find desec.io name server IP address with standard name server
        ips = dns_resolver.query('ns1.desec.io')
        dns_resolver.nameservers = []
        for ip in ips:
            dns_resolver.nameservers.append(str(ip))

        # query desec.io name server for A and AAAA records
        a_records = get_records(domain, 'A')
        aaaa_records = get_records(domain, 'AAAA')

        return Response({
            'domain': domain,
            'ns': ns_records,
            'a': a_records,
            'aaaa': aaaa_records,
            '_nameserver': dns_resolver.nameservers
        })


class DynDNS12Update(APIView):
    authentication_classes = (auth.TokenAuthentication, auth.BasicTokenAuthentication, auth.URLParamAuthentication,)
    renderer_classes = [PlainTextRenderer]

    def _find_domain(self, request):
        if self.request.user.locked:
            # Error code from https://help.dyn.com/remote-access-api/return-codes/
            raise PermissionDenied('abuse')

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
        except Domain.DoesNotExist:
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
        serializer = RRsetSerializer(instances, domain=domain, data=data, many=True, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            raise e

        with PDNSChangeTracker():
            serializer.save(domain=domain)

        return Response('good', content_type='text/plain')


class DonationList(generics.CreateAPIView):
    serializer_class = DonationSerializer

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


class UserCreateView(views.UserCreateView):
    """
    Extends the djoser UserCreateView to record the remote IP address of any registration.
    """

    def perform_create(self, serializer):
        remote_ip = self.request.META.get('REMOTE_ADDR')
        lock = (
                ipaddress.ip_address(remote_ip) not in ipaddress.IPv6Network(os.environ['DESECSTACK_IPV6_SUBNET'])
                and (
                    User.objects.filter(
                        created__gte=timezone.now()-timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS),
                        registration_remote_ip=remote_ip
                    ).count() >= settings.ABUSE_BY_REMOTE_IP_LIMIT
                    or
                    User.objects.filter(
                        created__gte=timezone.now() - timedelta(hours=settings.ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS),
                        email__endswith='@{0}'.format(serializer.validated_data['email'].split('@')[-1])
                    ).count() >= settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT
                )
            )

        user = serializer.save(registration_remote_ip=remote_ip, lock=lock)
        if user.locked:
            send_account_lock_email(self.request, user)
        if not user.dyn:
            context = {'token': user.get_or_create_first_token()}
            send_token_email(context, user)
        signals.user_registered.send(sender=self.__class__, user=user, request=self.request)


def unlock(request, email):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UnlockForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            User.objects.filter(email=email).update(locked=None)

            return HttpResponseRedirect(reverse('v1:unlock/done', request=request))  # TODO remove dependency on v1

    # if a GET (or any other method) we'll create a blank form
    else:
        form = UnlockForm()

    return render(request, 'unlock.html', {'form': form})


def unlock_done(request):
    return render(request, 'unlock-done.html')
