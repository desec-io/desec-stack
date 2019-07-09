import datetime
import uuid
from collections import OrderedDict
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import asymmetric, hashes, serialization
from cryptography.x509.oid import NameOID


class PKI:
    key = None
    crt = None

    def __init__(self, ca_crt_pem, ca_key_pem, ca_key_password=None, key=None):
        self.ca_crt = x509.load_pem_x509_certificate(
            ca_crt_pem,
            default_backend(),
        )

        self.ca_pkey = serialization.load_pem_private_key(
            ca_key_pem,
            password=ca_key_password,
            backend=default_backend(),
        )

    def initialize_key(self, key=None):
        self.key = key or self._generate_key()

    @staticmethod
    def _generate_key():
        return asymmetric.rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend(),
        )

    @property
    def key_pem(self):
        assert self.key is not None, 'You must call `initialize_key()` before accessing the key.'

        return self.key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def crt_pem(self):
        assert self.crt is not None, 'You must call `create_certificate()` before accessing the certificate.'

        return self.crt.public_bytes(encoding=serialization.Encoding.PEM)

    @property
    def subject_attributes(self):
        assert self.crt is not None, 'You must call `create_certificate()` before accessing the certificate.'

        oids = OrderedDict()
        oids[NameOID.COMMON_NAME] = 'CN'
        oids[NameOID.X500_UNIQUE_IDENTIFIER] = 'x500UniqueIdentifier'

        attrs = OrderedDict()
        for oid, label in oids.items():
            assert label not in attrs
            attrs[label] = [attribute.value for attribute in self.crt.subject.get_attributes_for_oid(oid)]

        return attrs

    def _generate_csr(self, common_name):
        assert self.key is not None, 'You must call `initialize_key()` before requesting a certificate.'

        # Copy attributes from CA certificate, except for CN
        attributes = [
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.X500_UNIQUE_IDENTIFIER, str(uuid.uuid4())),
        ]

        # Initialize and set attributes
        csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name(attributes))

        # Sign and return
        return csr.sign(self.key, hashes.SHA256(), default_backend())

    def create_certificate(self, common_name, days):
        csr = self._generate_csr(common_name)

        self.crt = x509.CertificateBuilder().subject_name(
            csr.subject
        ).issuer_name(
            self.ca_crt.subject
        ).public_key(
            csr.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=days)
        ).sign(
            private_key=self.ca_pkey,
            algorithm=hashes.SHA256(),
            backend=default_backend()
        )

