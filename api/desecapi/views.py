import base64
import binascii
import ipaddress
import os
import re
from datetime import timedelta

import django.core.exceptions
import djoser.views
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
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_bulk import ListBulkCreateUpdateAPIView

import desecapi.authentication as auth
from api import settings
from desecapi.emails import send_account_lock_email, send_token_email
from desecapi.forms import UnlockForm
from desecapi.models import Domain, User, RRset, Token
from desecapi.permissions import *
from desecapi.renderers import PlainTextRenderer
from desecapi.serializers import DomainSerializer, RRsetSerializer, DonationSerializer, TokenSerializer

patternDyn = re.compile(r'^[A-Za-z-][A-Za-z0-9_-]*\.dedyn\.io$')
patternNonDyn = re.compile(r'^([A-Za-z0-9-][A-Za-z0-9_-]*\.)+[A-Za-z]+$')


def get_client_ip(request):
    return request.META.get('REMOTE_ADDR')


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


class TokenViewSet(mixins.CreateModelMixin,
                   mixins.DestroyModelMixin,
                   mixins.ListModelMixin,
                   GenericViewSet):
    serializer_class = TokenSerializer
    permission_classes = (permissions.IsAuthenticated, )
    lookup_field = 'user_specific_id'

    def get_queryset(self):
        return self.request.user.auth_tokens.all()

    def destroy(self, request, *args, **kwargs):
        try:
            super().destroy(request, *args, **kwargs)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DomainList(generics.ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner, IsUnlockedOrDyn,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def perform_create(self, serializer):
        pattern = patternDyn if self.request.user.dyn else patternNonDyn
        if pattern.match(serializer.validated_data['name']) is None:
            ex = ValidationError(detail={
                "detail": "This domain name is not well-formed, by policy.",
                "code": "domain-illformed"}
            )
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex

        # Generate a list containing this and all higher-level domain names
        domain_name = serializer.validated_data['name']
        domain_parts = domain_name.split('.')
        domain_list = {'.'.join(domain_parts[i:]) for i in range(1, len(domain_parts))}

        # Remove public suffixes and then use this list to control registration
        public_suffixes = {'dedyn.io'}
        domain_list = domain_list - public_suffixes

        queryset = Domain.objects.filter(Q(name=domain_name) | (Q(name__in=domain_list) & ~Q(owner=self.request.user)))
        if queryset.exists():
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

        try:
            obj = serializer.save(owner=self.request.user)
        except Exception as e:
            if str(e).endswith(' already exists'):
                ex = ValidationError(detail={
                    "detail": "This domain name is unavailable.",
                    "code": "domain-unavailable"}
                )
                ex.status_code = status.HTTP_409_CONFLICT
                raise ex
            else:
                raise e

        def send_dyn_dns_email(domain):
            content_tmpl = get_template('emails/domain-dyndns/content.txt')
            subject_tmpl = get_template('emails/domain-dyndns/subject.txt')
            from_tmpl = get_template('emails/from.txt')
            context = {
                'domain': domain.name,
                'url': 'https://update.dedyn.io/',
                'username': domain.name,
                'password': self.request.auth.key
            }
            email = EmailMessage(subject_tmpl.render(context),
                                 content_tmpl.render(context),
                                 from_tmpl.render(context),
                                 [self.request.user.email])
            email.send()

        if obj.name.endswith('.dedyn.io'):
            send_dyn_dns_email(obj)


class DomainDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner, IsUnlocked,)
    lookup_field = 'name'

    def delete(self, request, *args, **kwargs):
        try:
            super().delete(request, *args, **kwargs)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except django.core.exceptions.ValidationError as e:
            raise ValidationError(detail={"detail": e.message})


class RRsetDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RRsetSerializer
    permission_classes = (permissions.IsAuthenticated, IsDomainOwner, IsUnlocked,)

    def delete(self, request, *args, **kwargs):
        try:
            super().delete(request, *args, **kwargs)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        domain_name = self.kwargs['name']

        try:
            return self.request.user.domains.get(name=domain_name).rrset_set
        except Domain.DoesNotExist:
            raise Http404()

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        rrset_type = self.kwargs['type']

        if rrset_type in RRset.RESTRICTED_TYPES:
            raise PermissionDenied("You cannot tinker with the %s RRset." % rrset_type)

        obj = get_object_or_404(queryset, type=rrset_type, subname=self.kwargs['subname'])

        self.check_object_permissions(self.request, obj)

        return obj

    def update(self, request, *args, **kwargs):
        if not isinstance(request.data, dict):
            raise ValidationError({
                api_settings.NON_FIELD_ERRORS_KEY: ['Invalid input, expected a JSON object.']
            }, code='invalid')

        records = request.data.get('records')
        if records is not None and len(records) == 0:
            return self.delete(request, *args, **kwargs)

        # Attach URL parameters (self.kwargs) to the request body object (request.data),
        # the latter having preference with both are given.
        for k in ('type', 'subname'):
            # This works because we exclusively use JSONParser which causes request.data to be
            # a dict (and not an immutable QueryDict, as is the case for other parsers)
            request.data[k] = request.data.pop(k, self.kwargs[k])

        try:
            return super().update(request, *args, **kwargs)
        except django.core.exceptions.ValidationError as e:
            ex = ValidationError(detail=e.message_dict)
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex


class RRsetList(ListBulkCreateUpdateAPIView):
    serializer_class = RRsetSerializer
    permission_classes = (permissions.IsAuthenticated, IsDomainOwner, IsUnlocked,)

    def get_queryset(self):
        name = self.kwargs['name']
        try:
            rrsets = self.request.user.domains.get(name=name).rrset_set
        except Domain.DoesNotExist:
            raise Http404

        for filter_field in ('subname', 'type'):
            value = self.request.query_params.get(filter_field)

            if value is not None:
                if filter_field == 'type' and value in RRset.RESTRICTED_TYPES:
                    raise PermissionDenied("You cannot tinker with the %s RRset." % value)

                rrsets = rrsets.filter(**{'%s__exact' % filter_field: value})

        return rrsets

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Domain.DoesNotExist:
            raise Http404
        except ValidationError as e:
            if isinstance(e.detail, dict):
                detail = e.detail.get('__all__')
                if isinstance(detail, list) \
                        and any(m.endswith(' already exists.') for m in detail):
                    e.status_code = status.HTTP_409_CONFLICT
            raise e

    def perform_create(self, serializer):
        # For new RRsets without a subname, set it empty. We don't use
        # default='' in the serializer field definition so that during PUT, the
        # subname value is retained if omitted.
        if isinstance(self.request.data, list):
            serializer._validated_data = [
                {**{'subname': ''}, **data}
                for data in serializer.validated_data
            ]
        else:
            serializer._validated_data = {**{'subname': ''}, **serializer.validated_data}

        # Associate RRset with proper domain
        domain = self.request.user.domains.get(name=self.kwargs['name'])
        serializer.save(domain=domain)

    def get(self, request, *args, **kwargs):
        name = self.kwargs['name']

        if not Domain.objects.filter(name=name, owner=self.request.user.pk):
            raise Http404

        return super().get(request, *args, **kwargs)


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
        ips = dns_resolver.query('ns2.desec.io')
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
                if domain_name:
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
        client_ip = get_client_ip(request)
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

        datas = {'A': self._find_ip_v4(request), 'AAAA': self._find_ip_v6(request)}
        rrsets = RRset.plain_to_rrsets(
            [{'subname': '', 'type': type_, 'ttl': 60,
              'contents': [ip] if ip is not None else []}
             for type_, ip in datas.items()],
            domain=domain)
        domain.write_rrsets(rrsets)

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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer, get_client_ip(request))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer, remote_ip):
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
            try:
                user = User.objects.get(email=email)
                if user.locked:
                    user.unlock()
                    if not user.dyn:
                        context = {'token': user.get_or_create_first_token()}
                        send_token_email(context, user)
            except User.DoesNotExist:
                # fail silently, so people can't probe registered addresses
                pass

            return HttpResponseRedirect(reverse('v1:unlock/done', request=request))  # TODO remove dependency on v1

    # if a GET (or any other method) we'll create a blank form
    else:
        form = UnlockForm()

    return render(request, 'unlock.html', {'form': form})


def unlock_done(request):
    return render(request, 'unlock-done.html')
