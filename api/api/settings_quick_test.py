# noinspection PyUnresolvedReferences
from api.settings import *

# noinspection PyUnresolvedReferences
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'desecapi.sqlite',
        'TEST': {
            'CHARSET': 'utf8mb4',
        },
    },

}

# abuse protection
ABUSE_BY_REMOTE_IP_LIMIT = 1
ABUSE_BY_REMOTE_IP_PERIOD_HRS = 48
ABUSE_BY_EMAIL_HOSTNAME_LIMIT = 1
ABUSE_BY_EMAIL_HOSTNAME_PERIOD_HRS = 24

# avoid computationally expensive password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
