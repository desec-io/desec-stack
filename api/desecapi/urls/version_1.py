from django.urls import include, path, re_path
from djoser.views import UserView
from rest_framework.routers import SimpleRouter

from desecapi import views


tokens_router = SimpleRouter()
tokens_router.register(r'', views.TokenViewSet, base_name='token')

auth_urls = [
    # Old user management
    # TODO deprecated, remove
    path('users/create/', views.UserCreateView.as_view(), name='user-create'),  # deprecated
    path('token/create/', views.TokenCreateView.as_view(), name='token-create'),  # deprecated
    path('token/destroy/', views.TokenDestroyView.as_view(), name='token-destroy'),  # deprecated

    # New user management
    path('users/', views.UserCreateView.as_view(), name='register'),

    # Token management
    path('token/login/', views.TokenCreateView.as_view(), name='login'),
    path('token/logout/', views.TokenDestroyView.as_view(), name='logout'),
    path('', include('djoser.urls.authtoken')),  # note: this is partially overwritten by the two lines above
    path('tokens/', include(tokens_router.urls)),

    # User home
    path('me/', UserView.as_view(), name='user'),
]

api_urls = [
    # API home
    path('', views.Root.as_view(), name='root'),

    # Domain and RRSet endpoints
    path('domains/', views.DomainList.as_view(), name='domain-list'),
    path('domains/<name>/', views.DomainDetail.as_view(), name='domain-detail'),
    path('domains/<name>/rrsets/', views.RRsetList.as_view(), name='rrsets'),
    path('domains/<name>/rrsets/.../<type>/', views.RRsetDetail.as_view()),
    re_path(r'domains/(?P<name>[^/]+)/rrsets/(?P<subname>(\*)?[a-zA-Z.\-_0-9]*)\.\.\./(?P<type>[A-Z][A-Z0-9]*)/',
                views.RRsetDetail.as_view(), name='rrset'),
    path('domains/<name>/rrsets/@/<type>/', views.RRsetDetail.as_view()),
    path('domains/<name>/rrsets/<subname>/<type>/', views.RRsetDetail.as_view()),
    re_path(r'domains/(?P<name>[^/]+)/rrsets/(?P<subname>(\*)?[a-zA-Z.\-_0-9]*)@/(?P<type>[A-Z][A-Z0-9]*)/',
            views.RRsetDetail.as_view(), name='rrset@'),

    # DNS query endpoint
    # TODO remove?
    path('dns', views.DnsQuery.as_view(), name='dns-query'),

    # DynDNS update endpoint
    path('dyndns/update', views.DynDNS12Update.as_view(), name='dyndns12update'),

    # Donation endpoints
    path('donation/', views.DonationList.as_view(), name='donation'),

    # Unlock endpoints
    path('unlock/user/<email>', views.unlock, name='unlock/byEmail'),
    path('unlock/done', views.unlock_done, name='unlock/done'),
]

app_name = 'desecapi'
urlpatterns = [
    path('auth/', include(auth_urls)),
    path('', include(api_urls)),
]
