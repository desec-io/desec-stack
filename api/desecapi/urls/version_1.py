from django.urls import include, path, re_path
from rest_framework.routers import SimpleRouter

from desecapi import views

tokens_router = SimpleRouter()
tokens_router.register(r"", views.TokenViewSet, basename="token")

tokendomainpolicies_router = SimpleRouter()
tokendomainpolicies_router.register(
    r"", views.TokenDomainPolicyViewSet, basename="token_domain_policies"
)

totp_router = SimpleRouter()
totp_router.register(r"", views.TOTPViewSet, basename="totp")

auth_urls = [
    # User management
    path("", views.AccountCreateView.as_view(), name="register"),
    path("account/", views.AccountView.as_view(), name="account"),
    path("account/delete/", views.AccountDeleteView.as_view(), name="account-delete"),
    path(
        "account/change-email/",
        views.AccountChangeEmailView.as_view(),
        name="account-change-email",
    ),
    path(
        "account/reset-password/",
        views.AccountResetPasswordView.as_view(),
        name="account-reset-password",
    ),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", views.AccountLogoutView.as_view(), name="logout"),
    # Token management
    path("tokens/", include(tokens_router.urls)),
    path(
        "tokens/<uuid:token_id>/policies/",
        views.TokenPoliciesRoot.as_view(),
        name="token-policies-root",
    ),
    path(
        "tokens/<uuid:token_id>/policies/domain/",
        include(tokendomainpolicies_router.urls),
    ),
    path("totp/", include(totp_router.urls)),
]

domains_router = SimpleRouter()
domains_router.register(r"", views.DomainViewSet, basename="domain")

api_urls = [
    # API home
    path("", views.Root.as_view(), name="root"),
    # Domain and RRSet management
    path("domains/", include(domains_router.urls)),
    path("domains/<name>/rrsets/", views.RRsetList.as_view(), name="rrsets"),
    path(
        "domains/<name>/rrsets/.../<type>/",
        views.RRsetDetail.as_view(),
        kwargs={"subname": ""},
    ),
    re_path(
        r"^domains/(?P<name>[^/]+)/rrsets/(?P<subname>[^/]*)\.\.\./(?P<type>[^/]+)/$",
        views.RRsetDetail.as_view(),
        name="rrset",
    ),
    path(
        "domains/<name>/rrsets/@/<type>/",
        views.RRsetDetail.as_view(),
        kwargs={"subname": ""},
    ),
    re_path(
        r"^domains/(?P<name>[^/]+)/rrsets/(?P<subname>[^/]*)@/(?P<type>[^/]+)/$",
        views.RRsetDetail.as_view(),
        name="rrset@",
    ),
    path("domains/<name>/rrsets/<subname>/<type>/", views.RRsetDetail.as_view()),
    # DynDNS update
    path("dyndns/update", views.DynDNS12UpdateView.as_view(), name="dyndns12update"),
    # Serials
    path("serials/", views.SerialListView.as_view(), name="serial"),
    # Donation
    path("donation/", views.DonationList.as_view(), name="donation"),
    # Authenticated Actions
    path(
        "v/activate-account/<code>/",
        views.AuthenticatedActivateUserActionView.as_view(),
        name="confirm-activate-account",
    ),
    path(
        "v/change-email/<code>/",
        views.AuthenticatedChangeEmailUserActionView.as_view(),
        name="confirm-change-email",
    ),
    path(
        "v/change-outreach-preference/<code>/",
        views.AuthenticatedChangeOutreachPreferenceUserActionView.as_view(),
        name="confirm-change-outreach-preference",
    ),
    path(
        "v/confirm-account/<code>/",
        views.AuthenticatedConfirmAccountUserActionView.as_view(),
        name="confirm-confirm-account",
    ),
    path(
        "v/create-totp/<code>/",
        views.AuthenticatedCreateTOTPFactorUserActionView.as_view(),
        name="confirm-create-totp",
    ),
    path(
        "v/reset-password/<code>/",
        views.AuthenticatedResetPasswordUserActionView.as_view(),
        name="confirm-reset-password",
    ),
    path(
        "v/delete-account/<code>/",
        views.AuthenticatedDeleteUserActionView.as_view(),
        name="confirm-delete-account",
    ),
    path(
        "v/renew-domain/<code>/",
        views.AuthenticatedRenewDomainBasicUserActionView.as_view(),
        name="confirm-renew-domain",
    ),
    path(
        "v/create-login-token/<code>/",
        views.AuthenticatedCreateLoginTokenActionView.as_view(),
        name="confirm-create-login-token",
    ),
    # CAPTCHA
    path("captcha/", views.CaptchaView.as_view(), name="captcha"),
]

app_name = "desecapi"
urlpatterns = [
    path("auth/", include(auth_urls)),
    path("", include(api_urls)),
]
