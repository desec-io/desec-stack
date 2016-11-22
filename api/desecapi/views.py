from __future__ import unicode_literals
from django.core.mail import EmailMessage
from desecapi.models import Domain
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
import subprocess
import re
from django.template.loader import get_template
from django.template import Context
from desecapi.authentication import BasicTokenAuthentication, URLParamAuthentication
import base64
from desecapi import settings

class DomainList(generics.ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def perform_create(self, serializer):
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

        if obj.dyn:
            sendDynDnsEmail(obj)


class DomainDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def pre_save(self, obj):
        # Set the owner of this domain to the current user (important for new domains)
        obj.owner = self.request.user

    def put(self, request, pk, format=None):
        # Don't accept PUT requests for non-existent or non-owned domains.
        domain = Domain.objects.filter(owner=self.request.user.pk, pk=pk)
        if len(domain) is 0:
            raise Http404
        return super(DomainDetail, self).put(request, pk, format)


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
            return Response(status=400)

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

class ScanLogjam(APIView):
    def get(self, request, format=None):
        # retrieve address to connect to
        addr = str(request.GET['host']) + ':' + str(int(request.GET['port']))
        starttls = str(request.GET['starttls'])

        def getOpenSSLOutput(cipher, connect, starttls=None, openssl='openssl-1.0.2a'):
            if starttls not in ['smtp', 'pop3', 'imap', 'ftp', 'xmpp']:
                starttls = None

            if starttls:
                starttlsparams = ['-starttls', starttls]
            else:
                starttlsparams = []

            if cipher:
                cipherparams = ['-cipher', cipher]
            else:
                cipherparams = []

            cmd = [
                      openssl,
                      's_client',
                      '-connect',
                      connect
                  ] + starttlsparams + cipherparams
            p_openssl = subprocess.Popen(cmd,
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
            stdout, stderr = p_openssl.communicate()

            return (stdout, stderr)

        # check if there is an SSL-enabled host
        output = getOpenSSLOutput(None, addr, openssl='openssl')
        if (not re.search('SSL-Session:', output[0])):
            raise Http404('Can\'t connect via SSL/TLS')

        # find DH size
        dhsize = None
        output = getOpenSSLOutput('EDH', addr, starttls)
        res = re.search('Server Temp Key: DH, ([0-9]+) bits', output[0])
        if res:
            dhsize = int(res.group(1))
        else:
            if (re.search('handshake failure:', output[1])):
                # server does not accept EDH connections, or no connections at all
                pass
            else:
                raise Http404('Failed to determine DH key size.')

        # check EXP cipher suits
        exp = True
        output = getOpenSSLOutput('EXP', addr, starttls)
        res = re.search('handshake failure:', output[1])
        if res:
            exp = False
        else:
            if (re.search('SSL-Session:', output[0])):
                # connection was established
                exp = True
            else:
                raise Exception('Failed to check for EXP cipher suits.')

        return Response({
            'openssl': {
                'addr': addr,
                'logjam': {
                    'dhsize': dhsize,
                    'expcipher': exp
                },
                'version': 'openssl-1.0.2a',
            }
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
                return base64.b64decode(get_authorization_header(request).split(' ')[1]).split(':')[0]
            except:
                pass

            # 4. username parameter
            if 'username' in request.query_params:
                return request.query_params['username']

            # 5. only domain associated with this user account
            if len(request.user.domains.all()) == 1:
                return request.user.domains[0].name

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
        client_ip = self.get_client_ip(request)
        if lookfor in client_ip:
            return client_ip

        # give up
        return ''

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

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

    def pre_save(self, obj):
        def sendDonationEmails(donation):
            context = Context({
                'donation': donation,
                'creditoridentifier': settings.SEPA['CREDITOR_ID'],
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

