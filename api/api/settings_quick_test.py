from api.settings import *

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
]
