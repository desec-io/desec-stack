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

# avoid computationally expensive password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
    PASSWORD_HASHER_TOKEN,
]

REST_FRAMEWORK['PAGE_SIZE'] = 20

# Carry email backend connection over to test mail outbox
CELERY_EMAIL_MESSAGE_EXTRA_ATTRIBUTES = ['connection']
