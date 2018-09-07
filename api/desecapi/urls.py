from django.conf.urls import include, url
from desecapi.views import *
from rest_framework.urlpatterns import format_suffix_patterns
from desecapi import views
from rest_framework.routers import SimpleRouter

router = SimpleRouter()
router.register(r'', TokenViewSet, base_name='token')
token_urls = router.urls

apiurls = [
    url(r'^$', Root.as_view(), name='root'),
    url(r'^domains/$', DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/$', DomainDetail.as_view(), name='domain-detail'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/$', RRsetList.as_view(), name='rrsets'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/(?P<subname>(\*)?[a-zA-Z\.\-_0-9=]*)\.\.\./(?P<type>[A-Z][A-Z0-9]*)/$', RRsetDetail.as_view(), name='rrset'),
    url(r'^tokens/', include(token_urls)),
    url(r'^dns$', DnsQuery.as_view(), name='dns-query'),
    url(r'^dyndns/update$', DynDNS12Update.as_view(), name='dyndns12update'),
    url(r'^donation/', DonationList.as_view(), name='donation'),
    url(r'^unlock/user/(?P<email>.+)$', views.unlock, name='unlock/byEmail'),
    url(r'^unlock/done', views.unlock_done, name='unlock/done'),
]

apiurls = format_suffix_patterns(apiurls)

urlpatterns = [
    url(r'^api/v1/auth/users/create/$', UserCreateView.as_view(), name='register'),
    url(r'^api/v1/auth/token/create/$', TokenCreateView.as_view(), name='login'),
    url(r'^api/v1/auth/token/destroy/$', TokenDestroyView.as_view(), name='logout'),
    url(r'^api/v1/auth/', include('djoser.urls')),
    url(r'^api/v1/auth/', include('djoser.urls.authtoken')),
    url(r'^api/v1/', include(apiurls)),
]
