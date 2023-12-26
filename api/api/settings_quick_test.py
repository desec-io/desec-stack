import os

# noinspection PyUnresolvedReferences
from api.settings import *

# noinspection PyUnresolvedReferences
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "desec",
        "USER": "desec",
        "HOST": "127.0.0.1"
        if os.environ.get("DESECSTACK_DJANGO_TEST", "") == "1"
        else "dbapi",
    },
}

# avoid computationally expensive password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
    PASSWORD_HASHER_TOKEN,
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

REST_FRAMEWORK["PAGE_SIZE"] = 20
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
    "rest_framework.throttling.UserRateThrottle"
]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"user": "1000/s"}

# Carry email backend connection over to test mail outbox
CELERY_EMAIL_MESSAGE_EXTRA_ATTRIBUTES = ["connection"]

LIMIT_USER_DOMAIN_COUNT_DEFAULT = 15

PCH_API = "http://api.invalid"
