from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns
from desecapi import views
from rest_framework.routers import SimpleRouter

router = SimpleRouter()
router.register(r'', views.TokenViewSet, base_name='token')
token_urls = router.urls

apiurls = [
    url(r'^$', views.Root.as_view(), name='root'),
    url(r'^domains/$', views.DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/$', views.DomainDetail.as_view(), name='domain-detail'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/$', views.RRsetList.as_view(), name='rrsets'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/(?P<subname>(\*)?[a-zA-Z\.\-_0-9=]*)\.\.\./(?P<type>[A-Z][A-Z0-9]*)/$', views.RRsetDetail.as_view(), name='rrset'),
    url(r'^tokens/', include(token_urls)),
    url(r'^dns$', views.DnsQuery.as_view(), name='dns-query'),
    url(r'^dyndns/update$', views.DynDNS12Update.as_view(), name='dyndns12update'),
    url(r'^donation/', views.DonationList.as_view(), name='donation'),
    url(r'^unlock/user/(?P<email>.+)$', views.unlock, name='unlock/byEmail'),
    url(r'^unlock/done', views.unlock_done, name='unlock/done'),
]

apiurls = format_suffix_patterns(apiurls)

urlpatterns = [
    url(r'^api/v1/auth/users/create/$', views.UserCreateView.as_view(), name='user-create'),  # deprecated
    url(r'^api/v1/auth/token/create/$', views.TokenCreateView.as_view(), name='token-create'),  # deprecated
    url(r'^api/v1/auth/token/destroy/$', views.TokenDestroyView.as_view(), name='token-destroy'),  # deprecated
    url(r'^api/v1/auth/users/$', views.UserCreateView.as_view(), name='register'),
    url(r'^api/v1/auth/token/login/$', views.TokenCreateView.as_view(), name='login'),
    url(r'^api/v1/auth/token/logout/$', views.TokenDestroyView.as_view(), name='logout'),
    url(r'^api/v1/auth/', include('djoser.urls')),
    url(r'^api/v1/auth/', include('djoser.urls.authtoken')),
    url(r'^api/v1/', include(apiurls)),
]
