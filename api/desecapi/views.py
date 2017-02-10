from __future__ import unicode_literals
from django.core.mail import EmailMessage
from desecapi.models import Domain, User
from desecapi.serializers import DomainSerializer, DonationSerializer
from rest_framework import generics
from desecapi.permissions import IsOwner
from rest_framework import permissions
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.authentication import TokenAuthentication, get_authorization_header
from rest_framework.renderers import StaticHTMLRenderer
from dns import resolver
from django.template.loader import get_template
from django.template import Context
from desecapi.authentication import BasicTokenAuthentication, URLParamAuthentication
import base64
from desecapi import settings
from rest_framework.exceptions import ValidationError
from djoser import views, signals
from rest_framework import status
from datetime import datetime, timedelta
from django.utils import timezone
from desecapi.forms import UnlockForm
from django.shortcuts import render
from django.http import HttpResponseRedirect
from desecapi.emails import send_account_lock_email
import re

# TODO Generalize?
patternDyn = re.compile(r'^[A-Za-z][A-Za-z0-9-]*\.dedyn\.io$')
patternNonDyn = re.compile(r'^([A-Za-z][A-Za-z0-9-]*\.)+[A-Za-z]+$')


def get_client_ip(request):
    return request.META.get('REMOTE_ADDR')


class DomainList(generics.ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def perform_create(self, serializer):
        pattern = patternDyn if self.request.user.dyn else patternNonDyn
        if pattern.match(serializer.validated_data['name']) is None or "--" in serializer.validated_data['name']:
            ex = ValidationError(detail={"detail": "This domain name is not well-formed, by policy.", "code": "domain-illformed"})
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex

        queryset = Domain.objects.filter(name=serializer.validated_data['name'])
        if queryset.exists():
            ex = ValidationError(detail={"detail": "This domain name is already registered.", "code": "domain-taken"})
            ex.status_code = status.HTTP_409_CONFLICT
            raise ex

        if self.request.user.limit_domains is not None and self.request.user.domains.count() >= self.request.user.limit_domains:
            ex = ValidationError(detail={"detail": "You reached the maximum number of domains allowed for your account.", "code": "domain-limit"})
            ex.status_code = status.HTTP_403_FORBIDDEN
            raise ex

        obj = serializer.save(owner=self.request.user)

        def sendDynDnsEmail(domain):
            content_tmpl = get_template('emails/domain-dyndns/content.txt')
            subject_tmpl = get_template('emails/domain-dyndns/subject.txt')
            from_tmpl = get_template('emails/from.txt')
            context = Context({
                'domain': domain.name,
                'url': 'https://update.dedyn.io/',
                'username': domain.name,
                'password': self.request.auth.key
            })
            email = EmailMessage(subject_tmpl.render(context),
                                 content_tmpl.render(context),
                                 from_tmpl.render(context),
                                 [self.request.user.email])
            email.send()

        if self.request.user.dyn:
            sendDynDnsEmail(obj)


class DomainDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)


class DomainDetailByName(DomainDetail):
    lookup_field = 'name'


class Root(APIView):
    def get(self, request, format=None):
        if self.request.user and self.request.user.is_authenticated():
            return Response({
                'domains': reverse('domain-list'),
                'user': reverse('user'),
                'logout:': reverse('logout'),
            })
        else:
            return Response({
                'login': reverse('login', request=request, format=format),
                'register': reverse('register', request=request, format=format),
            })

class DnsQuery(APIView):
    def get(self, request, format=None):
        desecio = resolver.Resolver()

        if not 'domain' in request.GET:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        domain = str(request.GET['domain'])

        def getRecords(domain, type):
            records = []
            try:
                for ip in desecio.query(domain, type):
                    records.append(str(ip))
            except resolver.NoAnswer:
                return []
            except resolver.NoNameservers:
                return []
            except resolver.NXDOMAIN:
                return []
            return records

        # find currently active NS records
        nsrecords = getRecords(domain, 'NS')

        # find desec.io nameserver IP address with standard nameserver
        ips = desecio.query('ns2.desec.io')
        desecio.nameservers = []
        for ip in ips:
            desecio.nameservers.append(str(ip))

        # query desec.io nameserver for A and AAAA records
        arecords = getRecords(domain, 'A')
        aaaarecords = getRecords(domain, 'AAAA')

        return Response({
            'domain': domain,
            'ns': nsrecords,
            'a': arecords,
            'aaaa': aaaarecords,
            '_nameserver': desecio.nameservers
        })


class DynDNS12Update(APIView):
    authentication_classes = (TokenAuthentication, BasicTokenAuthentication, URLParamAuthentication,)
    renderer_classes = [StaticHTMLRenderer]

    def findDomain(self, request):

        def findDomainname(request):
            # 1. hostname parameter
            if 'hostname' in request.query_params and request.query_params['hostname'] != 'YES':
                return request.query_params['hostname']

            # 2. host_id parameter
            if 'host_id' in request.query_params:
                return request.query_params['host_id']

            # 3. http basic auth username
            try:
                domainname = base64.b64decode(get_authorization_header(request).decode().split(' ')[1].encode()).decode().split(':')[0]
                if domainname:
                    return domainname
            except IndexError:
                pass
            except UnicodeDecodeError:
                pass

            # 4. username parameter
            if 'username' in request.query_params:
                return request.query_params['username']

            # 5. only domain associated with this user account
            if len(request.user.domains.all()) == 1:
                return request.user.domains.all()[0].name
            if len(request.user.domains.all()) > 1:
                ex = ValidationError(detail={"detail": "Request does not specify domain unambiguously.", "code": "domain-ambiguous"})
                ex.status_code = status.HTTP_409_CONFLICT
                raise ex

            return None

        domainname = findDomainname(request)
        domain = None

        # load and check permissions
        try:
            domain = Domain.objects.filter(owner=self.request.user.pk, name=domainname).all()[0]
        except:
            pass

        return domain

    def findIP(self, request, params, version=4):
        if version == 4:
            lookfor = '.'
        elif version == 6:
            lookfor = ':'
        else:
            raise Exception

        # Check URL parameters
        for p in params:
            if p in request.query_params and lookfor in request.query_params[p]:
                return request.query_params[p]

        # Check remote IP address
        client_ip = get_client_ip(request)
        if lookfor in client_ip:
            return client_ip

        # give up
        return ''

    def findIPv4(self, request):
        return self.findIP(request, ['myip', 'myipv4', 'ip'])

    def findIPv6(self, request):
        return self.findIP(request, ['myipv6', 'ipv6', 'myip', 'ip'], version=6)

    def get(self, request, format=None):
        domain = self.findDomain(request)

        if domain is None:
            raise Http404

        domain.arecord = self.findIPv4(request)
        domain.aaaarecord = self.findIPv6(request)
        domain.save()

        return Response('good')

class DonationList(generics.CreateAPIView):
    serializer_class = DonationSerializer

    def perform_create(self, serializer):
        iban = serializer.validated_data['iban']
        obj = serializer.save()

        def sendDonationEmails(donation):
            context = Context({
                'donation': donation,
                'creditoridentifier': settings.SEPA['CREDITOR_ID'],
                'complete_iban': iban
            })

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
                test = content_tmpl.render(context)
                email = EmailMessage(subject_tmpl.render(context),
                                     content_tmpl.render(context),
                                     from_tmpl.render(context),
                                     [donation.email])
                email.send()


        # send emails
        sendDonationEmails(obj)


class RegistrationView(views.RegistrationView):
    """
    Extends the djoser RegistrationView to record the remote IP address of any registration.
    """

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer, get_client_ip(request))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer, remote_ip):
        captcha = \
            (
                User.objects.filter(
                    created__gte=timezone.now()-timedelta(hours=settings.ABUSE_BY_REMOTE_IP_PERIOD_HRS),
                    registration_remote_ip=remote_ip
                ).count() >= settings.ABUSE_BY_REMOTE_IP_LIMIT
                or
                User.objects.filter(
                    created__gte=timezone.now() - timedelta(hours=settings.ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS),
                    email__endswith=serializer.validated_data['email'].split('@')[-1]
                ).count() >= settings.ABUSE_BY_EMAIL_HOSTNAME_LIMIT
            )

        user = serializer.save(registration_remote_ip=remote_ip, captcha_required=captcha)
        if captcha:
            send_account_lock_email(self.request, user)
        signals.user_registered.send(sender=self.__class__, user=user, request=self.request)


def unlock(request, email):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UnlockForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            try:
                User.objects.get(email=email).unlock()
            except User.DoesNotExist:
                pass # fail silently, otherwise people can find out if email addresses are registered with us

            return HttpResponseRedirect(reverse('unlock/done'))

    # if a GET (or any other method) we'll create a blank form
    else:
        form = UnlockForm()

    return render(request, 'unlock.html', {'form': form})


def unlock_done(request):
    return render(request, 'unlock-done.html')
