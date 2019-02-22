from django.conf.urls import include, url
from desecapi import views
from djoser.views import UserView
from rest_framework.routers import SimpleRouter

tokens_router = SimpleRouter()
tokens_router.register(r'', views.TokenViewSet, base_name='token')

auth_urls = [
    url(r'^users/create/$', views.UserCreateView.as_view(), name='user-create'),  # deprecated
    url(r'^token/create/$', views.TokenCreateView.as_view(), name='token-create'),  # deprecated
    url(r'^token/destroy/$', views.TokenDestroyView.as_view(), name='token-destroy'),  # deprecated
    url(r'^users/$', views.UserCreateView.as_view(), name='register'),
    url(r'^token/login/$', views.TokenCreateView.as_view(), name='login'),
    url(r'^token/logout/$', views.TokenDestroyView.as_view(), name='logout'),
    url(r'^tokens/', include(tokens_router.urls)),
    url(r'^me/?$', UserView.as_view(), name='user'),
    url(r'^', include('djoser.urls.authtoken')),
]

api_urls = [
    url(r'^$', views.Root.as_view(), name='root'),
    url(r'^domains/$', views.DomainList.as_view(), name='domain-list'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/$', views.DomainDetail.as_view(), name='domain-detail'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/$', views.RRsetList.as_view(), name='rrsets'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/(?P<subname>(\*)?[a-zA-Z\.\-_0-9=]*)\.\.\./(?P<type>[A-Z][A-Z0-9]*)/$', views.RRsetDetail.as_view(), name='rrset'),
    url(r'^domains/(?P<name>[a-zA-Z\.\-_0-9]+)/rrsets/(?P<subname>[*@]|[a-zA-Z\.\-_0-9=]+)/(?P<type>[A-Z][A-Z0-9]*)/$', views.RRsetDetail.as_view(), name='rrset@'),
    url(r'^dns$', views.DnsQuery.as_view(), name='dns-query'),
    url(r'^dyndns/update$', views.DynDNS12Update.as_view(), name='dyndns12update'),
    url(r'^donation/', views.DonationList.as_view(), name='donation'),
    url(r'^unlock/user/(?P<email>.+)$', views.unlock, name='unlock/byEmail'),
    url(r'^unlock/done', views.unlock_done, name='unlock/done'),
]

urlpatterns = [
    url(r'^api/v1/auth/', include(auth_urls)),
    url(r'^api/v1/', include(api_urls)),
]
