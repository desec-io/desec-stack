from base64 import urlsafe_b64encode

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.kbkdf import CounterLocation, KBKDFHMAC, Mode
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.utils.encoding import force_bytes

from desecapi import metrics


def _derive_urlsafe_key(*, label, context):
    backend = default_backend()
    kdf = KBKDFHMAC(algorithm=hashes.SHA256(), mode=Mode.CounterMode, length=32, rlen=4, llen=4,
                    location=CounterLocation.BeforeFixed, label=label, context=context, fixed=None, backend=backend)
    key = kdf.derive(settings.SECRET_KEY.encode())
    return urlsafe_b64encode(key)


def retrieve_key(*, label, context):
    # Keeping this function separate from key derivation gives us freedom to implement look-ups later, e.g. from cache
    label = force_bytes(label, strings_only=True)
    context = force_bytes(context, strings_only=True)
    return _derive_urlsafe_key(label=label, context=context)


def encrypt(data, *, context):
    key = retrieve_key(label=b'crypt', context=context)
    value = Fernet(key=key).encrypt(data)
    metrics.get('desecapi_key_encryption_success').labels(context).inc()
    return value


def decrypt(token, *, context, ttl=None):
    key = retrieve_key(label=b'crypt', context=context)
    f = Fernet(key=key)
    try:
        ret = f.extract_timestamp(token), f.decrypt(token, ttl=ttl)
        metrics.get('desecapi_key_decryption_success').labels(context).inc()
        return ret
    except InvalidToken:
        raise ValueError
