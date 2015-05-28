from models import Domain
from serializers import DomainSerializer
from rest_framework import generics
from permissions import IsOwner
from rest_framework import permissions
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.reverse import reverse
from dns import resolver
import subprocess
import re


class DomainList(generics.ListCreateAPIView):
    serializer_class = DomainSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner,)

    def get_queryset(self):
        return Domain.objects.filter(owner=self.request.user.pk)

    def pre_save(self, obj):
        obj.owner = self.request.user


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
                'login': reverse('login'),
                'register': reverse('register'),
            })

class DnsQuery(APIView):
    def get(self, request, format=None):
        desecio = resolver.Resolver()
        domain = str(request.GET['domain'])

        def getRecords(domain, type):
            records = []
            try:
                for ip in desecio.query(domain, type):
                    records.append(str(ip))
            except resolver.NoAnswer:
                return []
            return records

        # find currently active NS records
        nsrecords = getRecords(domain, 'NS')

        # find desec.io IP address with standard nameserver
        ips = desecio.query('desec.io')
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
            p_openssl.stdin.close()
            p_openssl.wait()

            stdout = p_openssl.stdout.read()
            stderr = p_openssl.stderr.read()
            return (stdout, stderr)

        # check if there is an SSL-enabled host
        output = getOpenSSLOutput(None, addr, openssl='openssl')
        if (not re.search('SSL-Session:', output[0])):
            raise Exception('Can\'t connect via SSL/TLS')

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
                raise Exception('Failed to determine DH key size.')

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
