from django.urls import include, path, re_path
from rest_framework.routers import SimpleRouter

from desecapi import views

tokens_router = SimpleRouter()
tokens_router.register(r'', views.TokenViewSet, base_name='token')

auth_urls = [
    # User management
    path('', views.AccountCreateView.as_view(), name='register'),
    path('account/', views.AccountView.as_view(), name='account'),
    path('account/delete/', views.AccountDeleteView.as_view(), name='account-delete'),
    path('account/change-email/', views.AccountChangeEmailView.as_view(), name='account-change-email'),
    path('account/reset-password/', views.AccountResetPasswordView.as_view(), name='account-reset-password'),
    path('login/', views.AccountLoginView.as_view(), name='login'),

    # Token management
    path('tokens/', include(tokens_router.urls)),
]

api_urls = [
    # API home
    path('', views.Root.as_view(), name='root'),

    # Domain and RRSet management
    path('domains/', views.DomainList.as_view(), name='domain-list'),
    path('domains/<name>/', views.DomainDetail.as_view(), name='domain-detail'),
    path('domains/<name>/rrsets/', views.RRsetList.as_view(), name='rrsets'),
    path('domains/<name>/rrsets/.../<type>/', views.RRsetDetail.as_view(), kwargs={'subname': ''}),
    re_path(r'domains/(?P<name>[^/]+)/rrsets/(?P<subname>[^/]*)\.\.\./(?P<type>[^/]+)/',
            views.RRsetDetail.as_view(), name='rrset'),
    path('domains/<name>/rrsets/@/<type>/', views.RRsetDetail.as_view(), kwargs={'subname': ''}),
    re_path(r'domains/(?P<name>[^/]+)/rrsets/(?P<subname>[^/]*)@/(?P<type>[^/]+)/',
            views.RRsetDetail.as_view(), name='rrset@'),
    path('domains/<name>/rrsets/<subname>/<type>/', views.RRsetDetail.as_view()),

    # DynDNS update
    path('dyndns/update', views.DynDNS12Update.as_view(), name='dyndns12update'),

    # Donation
    path('donation/', views.DonationList.as_view(), name='donation'),

    # Authenticated Actions
    path('v/activate-account/<code>/', views.AuthenticatedActivateUserActionView.as_view(), name='confirm-activate-account'),
    path('v/change-email/<code>/', views.AuthenticatedChangeEmailUserActionView.as_view(), name='confirm-change-email'),
    path('v/reset-password/<code>/', views.AuthenticatedResetPasswordUserActionView.as_view(), name='confirm-reset-password'),
    path('v/delete-account/<code>/', views.AuthenticatedDeleteUserActionView.as_view(), name='confirm-delete-account'),

    # CAPTCHA
    path('captcha/', views.CaptchaView.as_view(), name='captcha'),
]

app_name = 'desecapi'
urlpatterns = [
    path('auth/', include(auth_urls)),
    path('', include(api_urls)),
]
