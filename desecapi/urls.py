from django.conf.urls import patterns, include, url
from django.contrib import admin
from views import *
from rest_framework.urlpatterns import format_suffix_patterns

apiurls = [
    url(r'^$', Root.as_view(), name='root'),
    url(r'^domains/$', DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<pk>[0-9]+)/$', DomainDetail.as_view(), name='domain-detail'),
]

apiurls = format_suffix_patterns(apiurls)

urlpatterns = patterns('',
                       url(r'^admin/', include(admin.site.urls)),
                       url(r'^api/', include(apiurls)),
                       url(r'^auth/', include('djoser.urls')),
)
