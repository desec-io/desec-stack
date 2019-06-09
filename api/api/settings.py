"""
Django settings for desecapi project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['DESECSTACK_API_SECRETKEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False
if os.environ.get('DESECSTACK_API_DEBUG', "").upper() == "TRUE":
    DEBUG = True

ALLOWED_HOSTS = [
    'api',
    'desec.%s' % os.environ['DESECSTACK_DOMAIN'],
    'update.dedyn.%s' % os.environ['DESECSTACK_DOMAIN'],
    'update6.dedyn.%s' % os.environ['DESECSTACK_DOMAIN'],
]


# Application definition

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'djoser',
    'desecapi',
)

MIDDLEWARE = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
)

ROOT_URLCONF = 'api.urls'

WSGI_APPLICATION = 'desecapi.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'desec',
        'USER': 'desec',
        'PASSWORD': os.environ['DESECSTACK_DBAPI_PASSWORD_desec'],
        'HOST': 'dbapi',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_bin',
        },
    },

}

# This is necessary because the default is America/Chicago
TIME_ZONE = 'UTC'

USE_TZ = True

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'desecapi.authentication.TokenAuthentication',
    ),
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'EXCEPTION_HANDLER': 'desecapi.exception_handlers.exception_handler',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
}

# user management configuration
DJOSER = {
    'DOMAIN': 'desec.io',
    'SITE_NAME': 'deSEC',
    'LOGIN_AFTER_ACTIVATION': True,
    'SEND_ACTIVATION_EMAIL': False,
    'SERIALIZERS': {
        'current_user': 'desecapi.serializers.UserSerializer',
        'user': 'desecapi.serializers.UserSerializer',
        'user_create': 'desecapi.serializers.UserCreateSerializer',
    },
    'TOKEN_MODEL': 'desecapi.models.Token',
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# How and where to send mail
EMAIL_HOST = os.environ['DESECSTACK_API_EMAIL_HOST']
EMAIL_HOST_USER = os.environ['DESECSTACK_API_EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = os.environ['DESECSTACK_API_EMAIL_HOST_PASSWORD']
EMAIL_PORT = os.environ['DESECSTACK_API_EMAIL_PORT']
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'deSEC <support@desec.io>'
ADMINS = [(address.split("@")[0], address) for address in os.environ['DESECSTACK_API_ADMIN'].split()]

# use our own user model
AUTH_USER_MODEL = 'desecapi.User'

# default NS records
DEFAULT_NS = ['ns1.desec.io.', 'ns2.desec.io.']

# Public Suffix settings
PSL_RESOLVER = os.environ.get('DESECSTACK_API_PSL_RESOLVER')
LOCAL_PUBLIC_SUFFIXES = {'dedyn.io'}

# PowerDNS API access
NSLORD_PDNS_API = 'http://nslord:8081/api/v1/servers/localhost'
NSLORD_PDNS_API_TOKEN = os.environ['DESECSTACK_NSLORD_APIKEY']
NSMASTER_PDNS_API = 'http://nsmaster:8081/api/v1/servers/localhost'
NSMASTER_PDNS_API_TOKEN = os.environ['DESECSTACK_NSMASTER_APIKEY']

# pdns accepts request payloads of this size.
# This will hopefully soon be configurable: https://github.com/PowerDNS/pdns/pull/7550
PDNS_MAX_BODY_SIZE = 2 * 1024 * 1024

# SEPA direct debit settings
SEPA = {
    'CREDITOR_ID': os.environ['DESECSTACK_API_SEPA_CREDITOR_ID'],
    'CREDITOR_NAME': os.environ['DESECSTACK_API_SEPA_CREDITOR_NAME'],
}

# recaptcha
NORECAPTCHA_SITE_KEY = os.environ['DESECSTACK_NORECAPTCHA_SITE_KEY']
NORECAPTCHA_SECRET_KEY = os.environ['DESECSTACK_NORECAPTCHA_SECRET_KEY']
NORECAPTCHA_WIDGET_TEMPLATE = 'captcha-widget.html'

# abuse protection
ABUSE_BY_REMOTE_IP_LIMIT = 1
ABUSE_BY_REMOTE_IP_PERIOD_HRS = 48
ABUSE_BY_EMAIL_HOSTNAME_LIMIT = 1
ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS = 24
LIMIT_USER_DOMAIN_COUNT_DEFAULT = 5

if os.environ.get('DESECSTACK_E2E_TEST', "").upper() == "TRUE":
    DEBUG = True
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
    ABUSE_BY_REMOTE_IP_LIMIT = 100
    ABUSE_BY_REMOTE_IP_PERIOD_HRS = 0
    ABUSE_BY_EMAIL_HOSTNAME_LIMIT = 100
    ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS = 0
    LIMIT_USER_DOMAIN_COUNT_DEFAULT = 5000
