from django.conf.urls import include, url
from django.contrib import admin
from desecapi.views import *
from rest_framework.urlpatterns import format_suffix_patterns

apiurls = [
    url(r'^$', Root.as_view(), name='root'),
    url(r'^domains/$', DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<pk>[0-9]+)/$', DomainDetail.as_view(), name='domain-detail'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-0-9]+)/$', DomainDetailByName.as_view(), name='domain-detail/byName'),
    url(r'^dns$', DnsQuery.as_view(), name='dns-query'),
    url(r'^dyndns/update$', DynDNS12Update.as_view(), name='dyndns12update'),
    url(r'^donation/', DonationList.as_view(), name='donation'),
]

apiurls = format_suffix_patterns(apiurls)

urlpatterns = [
   url(r'^api/v1/auth/register/$', RegistrationView.as_view(), name='register'),
   url(r'^api/v1/auth/', include('djoser.urls.authtoken')),
   url(r'^api/v1/', include(apiurls)),
]
