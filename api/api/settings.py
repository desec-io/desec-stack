"""
Django settings for desecapi project.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
from datetime import timedelta

from django.conf.global_settings import PASSWORD_HASHERS as DEFAULT_PASSWORD_HASHERS

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["DESECSTACK_API_SECRETKEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
if os.environ.get("DESECSTACK_API_DEBUG", "").upper() == "TRUE":
    DEBUG = True

ALLOWED_HOSTS = [
    "api",
    "desec.%s" % os.environ["DESECSTACK_DOMAIN"],
    "update.dedyn.%s" % os.environ["DESECSTACK_DOMAIN"],
    "update6.dedyn.%s" % os.environ["DESECSTACK_DOMAIN"],
]

DEFAULT_EXCEPTION_REPORTER = "desecapi.debug.PayloadExceptionReporter"


# Application definition

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "desecapi.apps.AppConfig",
    "corsheaders",
    "django_prometheus",
    "netfields",
    "pgtrigger",
)

MIDDLEWARE = (
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
)

ROOT_URLCONF = "api.urls"

WSGI_APPLICATION = "desecapi.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": "desec",
        "USER": "desec",
        "PASSWORD": os.environ["DESECSTACK_DBAPI_PASSWORD_desec"],
        "HOST": "dbapi",
        "CONN_MAX_AGE": 3600,  # don't reconnect to database on each request
    },
}

CACHES = {
    "default": {
        # TODO 'BACKEND': 'django_prometheus.cache.backends.memcached.PyLibMCCache' not supported
        "BACKEND": "django.core.cache.backends.memcached.PyLibMCCache",
        "LOCATION": "memcached:11211",
    }
}

# This is necessary because the default is America/Chicago
TIME_ZONE = "UTC"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    "DEFAULT_AUTHENTICATION_CLASSES": ("desecapi.authentication.TokenAuthentication",),
    "DEFAULT_PAGINATION_CLASS": "desecapi.pagination.LinkHeaderCursorPagination",
    "PAGE_SIZE": 500,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "EXCEPTION_HANDLER": "desecapi.exception_handlers.exception_handler",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "ALLOWED_VERSIONS": ["v1", "v2"],
    "DEFAULT_THROTTLE_CLASSES": [
        "desecapi.throttling.ScopedRatesThrottle",
        "desecapi.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {  # When changing rate limits, make sure to keep docs/rate-limits.rst consistent
        # ScopedRatesThrottle
        "account_management_active": [
            "3/min"
        ],  # things with side effect, e.g. sending mail or zone creation on signup
        "account_management_passive": [
            "10/min"
        ],  # things like GET'ing v/* or auth/* URLs, or creating/deleting tokens
        "dyndns": [
            "1/min"
        ],  # dynDNS updates, domain-scoped; anything above 1/min is a client misconfiguration
        "dns_api_cheap": [
            "10/s",
            "50/min",
        ],  # DNS API requests that do not involve pdns
        "dns_api_expensive": [
            "10/s",
            "300/min",
            "1000/h",
        ],  # DNS API requests affecting domains as a whole
        "dns_api_per_domain_expensive": [
            "2/s",
            "15/min",
            "100/h",
            "300/d",
        ],  # DNS API requests affecting RRset(s) of a single domain
        # UserRateThrottle
        "user": "2000/d",  # hard limit on requests by a) an authenticated user, b) an unauthenticated IP address
    },
    "NUM_PROXIES": 0,  # Do not use X-Forwarded-For header when determining IP for throttling
}

PASSWORD_HASHER_TOKEN = "desecapi.authentication.TokenHasher"
PASSWORD_HASHERS = DEFAULT_PASSWORD_HASHERS + [PASSWORD_HASHER_TOKEN]

# CORS
# No need to add Authorization to CORS_ALLOW_HEADERS (included by default)
CORS_ALLOW_ALL_ORIGINS = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# How and where to send mail
EMAIL_BACKEND = "desecapi.mail_backends.MultiLaneEmailBackend"
EMAIL_HOST = os.environ["DESECSTACK_API_EMAIL_HOST"]
EMAIL_HOST_USER = os.environ["DESECSTACK_API_EMAIL_HOST_USER"]
EMAIL_HOST_PASSWORD = os.environ["DESECSTACK_API_EMAIL_HOST_PASSWORD"]
EMAIL_PORT = os.environ["DESECSTACK_API_EMAIL_PORT"]
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "deSEC <support@desec.io>"
ADMINS = [
    (address.split("@")[0], address)
    for address in os.environ["DESECSTACK_API_ADMIN"].split()
]

DESECSTACK_DOMAIN = os.environ["DESECSTACK_DOMAIN"]

# default NS records
DEFAULT_NS = [name + "." for name in os.environ["DESECSTACK_NS"].strip().split()]
DEFAULT_NS_TTL = int(os.environ["DESECSTACK_NSLORD_DEFAULT_TTL"])

# Public Suffix settings
PSL_RESOLVER = os.environ.get("DESECSTACK_API_PSL_RESOLVER")
LOCAL_PUBLIC_SUFFIXES = {"dedyn.%s" % os.environ["DESECSTACK_DOMAIN"]}

# PowerDNS-related
NSLORD_PDNS_API = "http://nslord:8081/api/v1/servers/localhost"
NSLORD_PDNS_API_TOKEN = os.environ["DESECSTACK_NSLORD_APIKEY"]
NSMASTER_PDNS_API = "http://nsmaster:8081/api/v1/servers/localhost"
NSMASTER_PDNS_API_TOKEN = os.environ["DESECSTACK_NSMASTER_APIKEY"]
CATALOG_ZONE = "catalog.internal"

# Celery
# see https://docs.celeryproject.org/en/stable/history/whatsnew-4.0.html#latentcall-django-admonition
CELERY_BROKER_URL = "amqp://rabbitmq"
CELERY_EMAIL_MESSAGE_EXTRA_ATTRIBUTES = (
    []
)  # required because djcelery_email.utils accesses it
CELERY_TASK_TIME_LIMIT = (
    300  # as zones become larger, AXFR takes longer, this needs to be increased
)
TASK_CONFIG = {  # The first entry is the default queue
    "email_slow_lane": {"rate_limit": "3/m"},
    "email_fast_lane": {"rate_limit": "1/s"},
    "email_immediate_lane": {"rate_limit": None},
}

# pdns accepts request payloads of this size.
# This will hopefully soon be configurable: https://github.com/PowerDNS/pdns/pull/7550
PDNS_MAX_BODY_SIZE = 16 * 1024 * 1024

# SEPA direct debit settings
SEPA = {
    "CREDITOR_ID": os.environ["DESECSTACK_API_SEPA_CREDITOR_ID"],
    "CREDITOR_NAME": os.environ["DESECSTACK_API_SEPA_CREDITOR_NAME"],
}

# user management
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
]
MINIMUM_TTL_DEFAULT = int(os.environ["DESECSTACK_MINIMUM_TTL_DEFAULT"])
MAXIMUM_TTL = 86400
AUTH_USER_MODEL = "desecapi.User"
LIMIT_USER_DOMAIN_COUNT_DEFAULT = int(
    os.environ.get("DESECSTACK_API_LIMIT_USER_DOMAIN_COUNT_DEFAULT", "1")
)
USER_ACTIVATION_REQUIRED = True
VALIDITY_PERIOD_VERIFICATION_SIGNATURE = timedelta(
    hours=int(os.environ.get("DESECSTACK_API_AUTHACTION_VALIDITY", "0"))
)
REGISTER_LPS = bool(int(os.environ.get("DESECSTACK_API_REGISTER_LPS", "1")))

# CAPTCHA
CAPTCHA_VALIDITY_PERIOD = timedelta(hours=24)

# Watchdog
WATCHDOG_SECONDARIES = os.environ.get("DESECSTACK_WATCHDOG_SECONDARIES", "").split()

# PCH
PCH_API = os.environ.get("DESECSTACK_API_PCH_API", "")
PCH_API_TOKEN = os.environ.get("DESECSTACK_API_PCH_API_TOKEN", "")

# Prometheus (see https://github.com/korfuri/django-prometheus/blob/master/documentation/exports.md)
#  TODO Switch to PROMETHEUS_METRICS_EXPORT_PORT_RANGE instead of this workaround, which currently necessary to due
#  https://github.com/korfuri/django-prometheus/issues/215
try:
    import uwsgi
except ImportError:
    pass  # not running in uwsgi, e.g. management command
else:
    import prometheus_client

    prometheus_client.values.ValueClass = prometheus_client.values.MultiProcessValue(
        process_identifier=uwsgi.worker_id
    )

if DEBUG and not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"

if os.environ.get("DESECSTACK_E2E_TEST", "").upper() == "TRUE":
    DEBUG = True
    LIMIT_USER_DOMAIN_COUNT_DEFAULT = 5000
    USER_ACTIVATION_REQUIRED = False
    EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
