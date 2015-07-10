from django.conf.urls import patterns, include, url
from django.contrib import admin
from views import *
from rest_framework.urlpatterns import format_suffix_patterns

apiurls = [
    url(r'^$', Root.as_view(), name='root'),
    url(r'^domains/$', DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<pk>[0-9]+)/$', DomainDetail.as_view(), name='domain-detail'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-0-9]+)/$', DomainDetailByName.as_view(), name='domain-detail/byName'),
    url(r'^dns$', DnsQuery.as_view(), name='dns-query'),
    url(r'^scan/logjam$', ScanLogjam.as_view(), name='scan-logjam'),
    url(r'^dyndns/update$', DynDNS12Update.as_view(), name='dyndns12update'),
]

apiurls = format_suffix_patterns(apiurls)

urlpatterns = patterns('',
                       url(r'^admin/', include(admin.site.urls)),
                       url(r'^api/auth/', include('djoser.urls')),
                       url(r'^api/', include(apiurls)),
)
