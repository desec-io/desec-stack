import random
import string

from rest_framework.authtoken.models import Token
from desecapi.models import Domain, User


class utils(object):
    @classmethod
    def generateRandomString(cls, size=6, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @classmethod
    def generateUsername(cls):
        return cls.generateRandomString() + '@desec.io'

    @classmethod
    def generateDomainname(cls):
        return random.choice(string.ascii_lowercase) + cls.generateRandomString() + '.de'

    @classmethod
    def generateDynDomainname(cls):
        return random.choice(string.ascii_lowercase) + cls.generateRandomString() + '.dedyn.io'

    """
    Creates a new user and saves it to the database.
    The user object is returned.
    """

    @classmethod
    def createUser(cls, username=None):
        if username is None:
            username = cls.generateUsername()
        user = User(email=username)
        user.plainPassword = cls.generateRandomString(size=12)
        user.set_password(user.plainPassword)
        user.save()
        return user

    """
    Creates a new domain and saves it to the database.
    The domain object is returned.
    """

    @classmethod
    def createDomain(cls, owner=None, port=80):
        if owner is None:
            owner = cls.createUser(username=None)
        domain = Domain(name=cls.generateDomainname(), owner=owner)
        domain.save()
        return domain

    @classmethod
    def createToken(cls, user):
        token = Token.objects.create(user=user)
        token.save();
        return token.key;

    """
    Returns a certificate for (www.)desec.io, signed by startssl.com,
    valid until 2015-11-15, serial number 0x1454C4 = 1332420 (base 10).
    SHA1 fingerprint is 8D:2E:F1:35:05:08:78:D3:FD:09:30:8A:A4:9C:D6:90:3E:04:8F:56
    SHA256 fingerprint is 8E:F3:F2:83:36:1C:F8:EC:8D:ED:4E:B8:05:82:4F:06:7D:47:86:05:B2:79:97:AB:FE:A7:64:60:4C:62:9D:6D
    """
    @classmethod
    def getDeSecCertificate(self):
        cert = ('-----BEGIN CERTIFICATE-----\n'
                'MIIGLzCCBRegAwIBAgIDFFTEMA0GCSqGSIb3DQEBCwUAMIGMMQswCQYDVQQGEwJJ\n'
                'TDEWMBQGA1UEChMNU3RhcnRDb20gTHRkLjErMCkGA1UECxMiU2VjdXJlIERpZ2l0\n'
                'YWwgQ2VydGlmaWNhdGUgU2lnbmluZzE4MDYGA1UEAxMvU3RhcnRDb20gQ2xhc3Mg\n'
                'MSBQcmltYXJ5IEludGVybWVkaWF0ZSBTZXJ2ZXIgQ0EwHhcNMTQxMTEzMjAzNDI1\n'
                'WhcNMTUxMTE1MDUwMzU2WjBIMQswCQYDVQQGEwJVUzEVMBMGA1UEAxMMd3d3LmRl\n'
                'c2VjLmlvMSIwIAYJKoZIhvcNAQkBFhNwb3N0bWFzdGVyQGRlc2VjLmlvMIIBIjAN\n'
                'BgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp+h4uKeIMvr0jpGc8DP55q3b2vWa\n'
                'wNFeneQgVyeO+b4MDRduOrlOrsid7da/qJxxTbbyI94npjWvu5GpayIK3xC3qpUm\n'
                'uVSo2CmMlqpWo62cURZe9NK8eXUmEjbStOtgFIZDOADHxe0RgEr+i7AWLQvIPgHi\n'
                '8P1N2zd5ujBfrBMd8sXsATXeBc4Ft4wMNOLotpL9uUxnMJiMUHFU+TeYcl2g+n0S\n'
                'DfNCVq6e0Bs5uIbrPr+RJMkHMVDBaEwC6X83bIRARTh+YwhI1ARThyR7/vBnx/9a\n'
                '/YD4B2SxomBDAx7iRF6XZ8QjHhl8Xo5bkPAa22BcRIukh4ByAaO0a9lMewIDAQAB\n'
                'o4IC2zCCAtcwCQYDVR0TBAIwADALBgNVHQ8EBAMCA6gwEwYDVR0lBAwwCgYIKwYB\n'
                'BQUHAwEwHQYDVR0OBBYEFBV7yHCr6j2KD+E4LIOcBMYuFMx1MB8GA1UdIwQYMBaA\n'
                'FOtCNNCYsKuf9BtrCPfMZC7vDixFMCEGA1UdEQQaMBiCDHd3dy5kZXNlYy5pb4II\n'
                'ZGVzZWMuaW8wggFWBgNVHSAEggFNMIIBSTAIBgZngQwBAgEwggE7BgsrBgEEAYG1\n'
                'NwECAzCCASowLgYIKwYBBQUHAgEWImh0dHA6Ly93d3cuc3RhcnRzc2wuY29tL3Bv\n'
                'bGljeS5wZGYwgfcGCCsGAQUFBwICMIHqMCcWIFN0YXJ0Q29tIENlcnRpZmljYXRp\n'
                'b24gQXV0aG9yaXR5MAMCAQEagb5UaGlzIGNlcnRpZmljYXRlIHdhcyBpc3N1ZWQg\n'
                'YWNjb3JkaW5nIHRvIHRoZSBDbGFzcyAxIFZhbGlkYXRpb24gcmVxdWlyZW1lbnRz\n'
                'IG9mIHRoZSBTdGFydENvbSBDQSBwb2xpY3ksIHJlbGlhbmNlIG9ubHkgZm9yIHRo\n'
                'ZSBpbnRlbmRlZCBwdXJwb3NlIGluIGNvbXBsaWFuY2Ugb2YgdGhlIHJlbHlpbmcg\n'
                'cGFydHkgb2JsaWdhdGlvbnMuMDUGA1UdHwQuMCwwKqAooCaGJGh0dHA6Ly9jcmwu\n'
                'c3RhcnRzc2wuY29tL2NydDEtY3JsLmNybDCBjgYIKwYBBQUHAQEEgYEwfzA5Bggr\n'
                'BgEFBQcwAYYtaHR0cDovL29jc3Auc3RhcnRzc2wuY29tL3N1Yi9jbGFzczEvc2Vy\n'
                'dmVyL2NhMEIGCCsGAQUFBzAChjZodHRwOi8vYWlhLnN0YXJ0c3NsLmNvbS9jZXJ0\n'
                'cy9zdWIuY2xhc3MxLnNlcnZlci5jYS5jcnQwIwYDVR0SBBwwGoYYaHR0cDovL3d3\n'
                'dy5zdGFydHNzbC5jb20vMA0GCSqGSIb3DQEBCwUAA4IBAQBSI82kiD0St0MnhQok\n'
                'NOTvYrF7kyMVEaVoJC08VocwBejaDVRUhazv1YBYy7WwdoQ+oYYZB37Vaa83xF3B\n'
                'aY59NR4UN8cPFjevt/Z9DDuslN1pWaBu/W+W2qn2t3suRuT+l4n+zEo9SwIBhn0x\n'
                'TRTDoj+kfvx+1CYIcagRMvB5TBUWs61OtFaYCp410axzZBo97P9DMsRqw0maFYGv\n'
                's93Bi+fJGHndo+E4Qei3MRadDZKjQnvErsmrFzlVSqHcPwWtUqSCVF5BXP9YsRZn\n'
                'hvehPEY+gPmclXFMi1FY3Z1gdhN4B1DjXfhlmKxC3GrM7CoKFjOutWWwZOIZGKdL\n'
                'g7Vp\n'
                '-----END CERTIFICATE-----\n')
        return cert.__str__()
