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
