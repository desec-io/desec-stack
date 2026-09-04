import os

# noinspection PyUnresolvedReferences
from api.settings import *

# noinspection PyUnresolvedReferences
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "desec",
        "USER": "desec",
        "HOST": (
            "127.0.0.1"
            if os.environ.get("DESECSTACK_DJANGO_TEST", "") == "1"
            else "dbapi"
        ),
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
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ["desecapi.throttling.UserRateThrottle"]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"user": "1000/s"}

# Carry email backend connection over to test mail outbox
CELERY_EMAIL_MESSAGE_EXTRA_ATTRIBUTES = ["connection"]

# In-process broker: tasks may be enqueued without a rabbitmq to talk to, and
# without running (which would perform real checks). Tests that care about a
# task being scheduled assert on .delay() instead.
CELERY_BROKER_URL = "memory://"

DOMAIN_LIMIT_INSECURE_HEADROOM = 15

PCH_API = "http://api.invalid"
GATEKEEPER_API = "http://gatekeeper.invalid/"
